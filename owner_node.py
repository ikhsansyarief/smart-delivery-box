"""Edge 2: HP Pemilik di dalam rumah. Menerima alert dari detector lalu
membunyikan alarm (getar + notifikasi + suara) lewat Termux:API.

  python owner_node.py
"""
import json
import time

from shared import alarm
from shared.config import OWNER_ID, load_config
from shared.mqtt_client import MqttNode


def main():
    cfg = load_config()
    presence = cfg.topic(f"edge/{OWNER_ID}/presence")
    node = MqttNode(cfg, OWNER_ID, will=(presence, json.dumps({"online": False})))
    node.add_on_connect(lambda: node.publish(presence, json.dumps({"online": True}), retain=True))

    last = {"status": None}

    def on_alert(topic, raw):
        data = json.loads(raw)
        if data.get("type") != "ALERT":
            return
        print(f"[OWNER] ALERT {data.get('status')}: {data.get('reason')}"
              f"{' (ulang)' if data.get('repeat') else ''}")
        alarm.trigger(data)

    def on_status(topic, raw):
        data = json.loads(raw)
        if data.get("status") != last["status"]:
            last["status"] = data.get("status")
            print(f"[OWNER] Status kotak: {last['status']} - {data.get('reason')}")

    node.subscribe(cfg.topic("alerts"), on_alert)
    node.subscribe(cfg.topic("status"), on_status)
    node.start()
    print(f"[OWNER] Subscribed to {cfg.topic('alerts')}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[OWNER] Berhenti.")
    finally:
        node.publish(presence, json.dumps({"online": False}), retain=True)
        time.sleep(0.3)
        node.stop()


if __name__ == "__main__":
    main()
