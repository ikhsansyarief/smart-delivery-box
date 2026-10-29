"""Pembungkus paho-mqtt: TLS, auto-reconnect, LWT, resubscribe."""
import uuid

import paho.mqtt.client as mqtt


class MqttNode:
    def __init__(self, cfg, name: str, will: tuple | None = None):
        self.cfg = cfg
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{cfg.project_id}-{name}-{uuid.uuid4().hex[:6]}",
        )
        if cfg.mqtt_tls:
            self.client.tls_set()  # CA bawaan sistem
        if will:
            topic, payload = will
            self.client.will_set(topic, payload, qos=1, retain=True)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self._subs: list[tuple[str, object, int]] = []
        self._on_connect_cbs = []

    # ---- API ----
    def subscribe(self, topic_filter: str, handler, qos: int = 1):
        self._subs.append((topic_filter, handler, qos))
        if self.client.is_connected():
            self.client.subscribe(topic_filter, qos)

    def add_on_connect(self, fn):
        self._on_connect_cbs.append(fn)

    def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False):
        self.client.publish(topic, payload, qos=qos, retain=retain)

    def start(self):
        self.client.connect_async(self.cfg.mqtt_host, self.cfg.mqtt_port, keepalive=30)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    # ---- callback paho ----
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            print(f"[MQTT] Gagal connect: {reason_code}")
            return
        print(f"[MQTT] Terhubung ke {self.cfg.mqtt_host}:{self.cfg.mqtt_port}"
              f" (TLS={self.cfg.mqtt_tls})")
        for flt, _, qos in self._subs:
            client.subscribe(flt, qos)
        for fn in self._on_connect_cbs:
            fn()

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        print(f"[MQTT] Terputus ({reason_code}), mencoba menyambung ulang...")

    def _on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", "replace")
        for flt, handler, _ in self._subs:
            if mqtt.topic_matches_sub(flt, msg.topic):
                try:
                    handler(msg.topic, payload)
                except Exception as exc:  # jangan matikan loop MQTT
                    print(f"[MQTT] Error handler {msg.topic}: {exc!r}")
