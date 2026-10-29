"""Konfigurasi dari .env (pola sama dengan contoh-project-iot1)."""
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BOX_ID = "box1"      # Edge 1: HP di kotak paket
OWNER_ID = "owner"   # Edge 2: HP pemilik

load_dotenv(ROOT / ".env")


def _str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _bool(name: str, default: bool) -> bool:
    raw = _str(name)
    return default if not raw else raw.lower() in ("1", "true", "yes", "y", "on")


def _num(name: str, default, cast):
    raw = _str(name)
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        raise SystemExit(f"[CONFIG] {name} harus berupa angka, bukan '{raw}'")


@dataclass(frozen=True)
class Config:
    project_id: str
    mqtt_host: str
    mqtt_port: int
    mqtt_tls: bool
    mqtt_ws_url: str
    control_token: str
    dashboard_port: int
    sample_window: int
    sample_interval: float
    motion_threshold: float
    lid_mode: str
    light_open_lux: float
    light_close_lux: float
    proximity_near_cm: float
    accel_name: str
    light_name: str
    proximity_name: str
    confirm_motion: int
    confirm_open: int
    tamper_hold: float
    alert_repeat: float
    stale_seconds: float
    arm_on_start: bool

    def topic(self, suffix: str) -> str:
        """Alamat MQTT: deliverybox/<PROJECT_ID>/<suffix>"""
        return f"deliverybox/{self.project_id}/{suffix}"


def load_config() -> Config:
    project_id = _str("PROJECT_ID", "boxguard_demo")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project_id):
        raise SystemExit("[CONFIG] PROJECT_ID hanya boleh huruf, angka, - dan _")
    if "XX" in project_id:
        print("[CONFIG] PERINGATAN: ganti PROJECT_ID di .env dengan nama unik kelompokmu")

    lid_mode = _str("LID_MODE", "light").lower()
    if lid_mode not in ("light", "proximity", "any", "both"):
        raise SystemExit("[CONFIG] LID_MODE harus light/proximity/any/both")

    cfg = Config(
        project_id=project_id,
        mqtt_host=_str("MQTT_HOST", "broker.hivemq.com"),
        mqtt_port=_num("MQTT_PORT", 1883, int),
        mqtt_tls=_bool("MQTT_TLS", False),
        mqtt_ws_url=_str("MQTT_WS_URL", "wss://broker.hivemq.com:8884/mqtt"),
        control_token=_str("CONTROL_TOKEN"),
        dashboard_port=_num("DASHBOARD_PORT", 8000, int),
        sample_window=max(2, _num("SAMPLE_WINDOW", 5, int)),
        sample_interval=_num("SAMPLE_INTERVAL", 0.2, float),
        motion_threshold=_num("MOTION_RMS_THRESHOLD", 0.7, float),
        lid_mode=lid_mode,
        light_open_lux=_num("LIGHT_OPEN_LUX", 15.0, float),
        light_close_lux=_num("LIGHT_CLOSE_LUX", 5.0, float),
        proximity_near_cm=_num("PROXIMITY_NEAR_CM", 3.0, float),
        accel_name=_str("ACCEL_NAME"),
        light_name=_str("LIGHT_NAME"),
        proximity_name=_str("PROXIMITY_NAME"),
        confirm_motion=max(1, _num("CONFIRM_MOTION", 2, int)),
        confirm_open=max(1, _num("CONFIRM_OPEN", 1, int)),
        tamper_hold=_num("TAMPER_HOLD_SECONDS", 10.0, float),
        alert_repeat=_num("ALERT_REPEAT_SECONDS", 15.0, float),
        stale_seconds=_num("STALE_SECONDS", 8.0, float),
        arm_on_start=_bool("ARM_ON_START", True),
    )
    if cfg.light_close_lux >= cfg.light_open_lux:
        raise SystemExit("[CONFIG] LIGHT_CLOSE_LUX harus lebih kecil dari LIGHT_OPEN_LUX")
    return cfg
