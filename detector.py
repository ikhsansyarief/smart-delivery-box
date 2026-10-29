"""Layanan utama di laptop: subscribe telemetry Edge 1, jalankan rule-based
sensor fusion, publish status & alert, sajikan dashboard di jaringan lokal.

  python detector.py
"""
import argparse
import json
import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from nodes.detector_service.rules import ALERT_STATES, SAFE, SECURE, BoxRules, Decision
from shared.config import BOX_ID, OWNER_ID, ROOT, load_config
from shared.messages import Telemetry, now_ms
from shared.mqtt_client import MqttNode


class DetectorService:
    def __init__(self, cfg):
        self.cfg = cfg
        self.rules = BoxRules(cfg.motion_threshold, cfg.confirm_motion, cfg.confirm_open,
                              cfg.tamper_hold, armed=cfg.arm_on_start)
        self.lock = threading.RLock()
        self.node = MqttNode(cfg, "detector")
        self.decision = (Decision(SECURE, "Menunggu data dari kotak...") if cfg.arm_on_start
                         else Decision(SAFE, "Sistem DISARM"))
        self.prev_status = self.decision.status
        self.last_tele: Telemetry | None = None
        self.last_tele_at: float | None = None
        self.presence = {BOX_ID: False, OWNER_ID: False}
        self.alert_seq = 0
        self.last_alert_at = 0.0

    # ---------- MQTT ----------
    def start(self):
        c, n = self.cfg, self.node
        n.subscribe(c.topic(f"edge/{BOX_ID}/telemetry"), self.on_telemetry)
        n.subscribe(c.topic("edge/+/presence"), self.on_presence)
        n.subscribe(c.topic("control"), self.on_control)
        n.add_on_connect(self.publish_status)
        n.start()
        threading.Thread(target=self._tick, daemon=True).start()

    def on_telemetry(self, topic, raw):
        try:
            tele = Telemetry.from_json(raw)
        except (ValueError, TypeError) as exc:
            print(f"[DETECTOR] Telemetry tidak valid: {exc}")
            return
        with self.lock:
            self.last_tele, self.last_tele_at = tele, time.monotonic()
            self._apply(self.rules.evaluate(tele))
        self.publish_status()

    def on_presence(self, topic, raw):
        device = topic.split("/")[-2]
        try:
            online = bool(json.loads(raw).get("online"))
        except ValueError:
            return
        with self.lock:
            self.presence[device] = online
        print(f"[DETECTOR] {device}: {'online' if online else 'offline'}")
        self.publish_status()

    def on_control(self, topic, raw):
        try:
            msg = json.loads(raw)
        except ValueError:
            return
        if self.cfg.control_token and msg.get("token") != self.cfg.control_token:
            print("[DETECTOR] Perintah ditolak: token salah")
            return
        cmd = str(msg.get("command", "")).upper()
        with self.lock:
            if cmd == "ARM":
                self.rules.arm()
                self._apply(Decision(SECURE, "Sistem ARM: pemantauan aktif"))
            elif cmd == "DISARM":
                self.rules.disarm()
                self._apply(Decision(SAFE, "Sistem DISARM: pemantauan nonaktif"))
            elif cmd == "TEST_ALARM":
                self._send_alert("TEST", "Tes alarm dari dashboard", repeat=False)
            else:
                return
        print(f"[DETECTOR] Perintah: {cmd}")
        self.publish_status()

    # ---------- logika ----------
    def _apply(self, decision: Decision):
        """Dipanggil dalam lock. Kirim alert hanya saat masuk/naik ke status bahaya."""
        self.decision = decision
        if decision.status in ALERT_STATES and decision.status != self.prev_status:
            self._send_alert(decision.status, decision.reason, repeat=False)
        if decision.status != self.prev_status:
            print(f"[DETECTOR] {self.prev_status} -> {decision.status}: {decision.reason}")
        self.prev_status = decision.status

    def _send_alert(self, status, reason, repeat):
        self.alert_seq += 1
        self.last_alert_at = time.monotonic()
        t = self.last_tele
        payload = {"type": "ALERT", "alert_id": self.alert_seq, "status": status,
                   "reason": reason, "repeat": repeat, "sent_at_ms": now_ms(),
                   "motion_rms": t.motion_rms if t else None,
                   "lid_open": t.lid_open if t else None}
        self.node.publish(self.cfg.topic("alerts"), json.dumps(payload), qos=1)

    def publish_status(self):
        with self.lock:
            age = None if self.last_tele_at is None else time.monotonic() - self.last_tele_at
            t = self.last_tele
            payload = {
                "status": self.decision.status, "reason": self.decision.reason,
                "armed": self.rules.armed, "threshold": self.cfg.motion_threshold,
                "box_online": bool(self.presence[BOX_ID] and age is not None
                                   and age <= self.cfg.stale_seconds),
                "owner_online": self.presence[OWNER_ID],
                "last": None if t is None else {
                    "sequence": t.sequence, "motion_rms": t.motion_rms, "lid_open": t.lid_open,
                    "lux": t.lux, "proximity_cm": t.proximity_cm, "age_s": round(age, 1)},
                "sent_at_ms": now_ms(),
            }
        self.node.publish(self.cfg.topic("status"), json.dumps(payload), qos=1, retain=True)

    def _tick(self):
        """Heartbeat status + ulangi alert selama masih bahaya."""
        while True:
            time.sleep(2)
            with self.lock:
                if (self.decision.status in ALERT_STATES
                        and time.monotonic() - self.last_alert_at >= self.cfg.alert_repeat):
                    self._send_alert(self.decision.status, self.decision.reason, repeat=True)
            self.publish_status()


# ---------- dashboard lokal ----------
def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def start_dashboard(cfg):
    directory = str(ROOT / "dashboard")
    config_json = json.dumps({"project_id": cfg.project_id, "ws_url": cfg.mqtt_ws_url,
                              "box_id": BOX_ID, "threshold": cfg.motion_threshold,
                              "needs_token": bool(cfg.control_token)}).encode()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=directory, **kw)

        def do_GET(self):
            if self.path.split("?")[0] == "/config.json":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(config_json)))
                self.end_headers()
                self.wfile.write(config_json)
                return
            super().do_GET()

        def log_message(self, *args):
            pass

    try:
        server = ThreadingHTTPServer(("0.0.0.0", cfg.dashboard_port), Handler)
    except OSError as exc:
        print(f"[DASHBOARD] Gagal membuka port {cfg.dashboard_port}: {exc}")
        return
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[DASHBOARD] Laptop : http://localhost:{cfg.dashboard_port}")
    print(f"[DASHBOARD] HP/LAN : http://{lan_ip()}:{cfg.dashboard_port}  (satu WiFi/hotspot)")


def main():
    ap = argparse.ArgumentParser(description="BoxGuard detector & dashboard server")
    ap.add_argument("--no-dashboard", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    print(f"BoxGuard - NODE 3 / Laptop\n[CONFIG] PROJECT_ID: {cfg.project_id}")
    svc = DetectorService(cfg)
    if not args.no_dashboard:
        start_dashboard(cfg)
    svc.start()
    print("[DETECTOR] Menunggu Edge 1 (kotak) dari MQTT Cloud...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[DETECTOR] Berhenti.")
        svc.node.stop()


if __name__ == "__main__":
    main()
