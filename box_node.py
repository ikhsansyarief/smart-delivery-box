"""Edge 1: HP di dalam/menempel pada kotak paket.
Sensor: accelerometer + light/proximity -> olah (Motion RMS, status tutup) -> publish MQTT.

  python box_node.py                      # otomatis: Termux bila ada, kalau tidak simulator
  python box_node.py --source simulator --scenario demo
"""
import argparse
import json
import time
import uuid

from shared.config import BOX_ID, load_config
from shared.messages import Telemetry
from shared.mqtt_client import MqttNode
from shared.processing import LidDetector, process_window
from shared.sensors import SensorError, make_sensor


def main():
    ap = argparse.ArgumentParser(description="BoxGuard Edge 1 (kotak paket)")
    ap.add_argument("--source", default="auto", choices=["auto", "termux", "simulator"])
    ap.add_argument("--scenario", default="demo", help="still|shake|open|demo (simulator)")
    args = ap.parse_args()

    cfg = load_config()
    try:
        sensor = make_sensor(args.source, cfg, args.scenario)
    except SensorError as exc:
        raise SystemExit(f"[EDGE1] {exc}")

    lid = LidDetector(cfg.lid_mode, cfg.light_open_lux, cfg.light_close_lux, cfg.proximity_near_cm)
    presence = cfg.topic(f"edge/{BOX_ID}/presence")
    telemetry_topic = cfg.topic(f"edge/{BOX_ID}/telemetry")

    node = MqttNode(cfg, BOX_ID, will=(presence, json.dumps({"online": False})))
    node.add_on_connect(lambda: node.publish(presence, json.dumps({"online": True}), retain=True))
    node.start()
    print(f"[EDGE1] Publishes to: {telemetry_topic}")

    boot_id, seq = uuid.uuid4().hex[:8], 0
    try:
        while True:
            samples = []
            for _ in range(cfg.sample_window):
                try:
                    samples.append(sensor.read())
                except SensorError as exc:
                    print(f"[EDGE1] {exc}")
                time.sleep(cfg.sample_interval)
            if not samples:
                continue

            res = process_window(samples, lid)
            seq += 1
            tele = Telemetry.make(BOX_ID, boot_id, seq, res.motion_rms, res.lid_open,
                                  res.lid_event, res.lux, res.proximity_cm)
            node.publish(telemetry_topic, tele.to_json(), qos=1)  # kirim hasil olahan, bukan data mentah
            lux = "-" if res.lux is None else f"{res.lux:.1f}"
            print(f"[EDGE1] #{seq} rms={res.motion_rms:.3f} lid={'OPEN' if res.lid_open else 'closed'}"
                  f" lux={lux} event={res.lid_event or '-'}")
    except KeyboardInterrupt:
        print("\n[EDGE1] Berhenti.")
    finally:
        node.publish(presence, json.dumps({"online": False}), retain=True)
        time.sleep(0.3)
        node.stop()


if __name__ == "__main__":
    main()
