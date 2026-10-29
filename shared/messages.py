"""Format pesan MQTT (payload JSON)."""
import json
import time
from dataclasses import asdict, dataclass, fields
from typing import Optional


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class Telemetry:
    device_id: str
    boot_id: str
    sequence: int
    motion_rms: float            # hasil olah A: intensitas guncangan
    lid_open: bool               # hasil olah B: status tutup (setelah histeresis)
    sent_at_ms: int
    lid_event: Optional[str] = None      # "OPENED" / "CLOSED" bila ada transisi di window ini
    lux: Optional[float] = None
    proximity_cm: Optional[float] = None

    @classmethod
    def make(cls, device_id, boot_id, sequence, motion_rms, lid_open,
             lid_event=None, lux=None, proximity_cm=None) -> "Telemetry":
        return cls(device_id, boot_id, sequence, round(motion_rms, 4), bool(lid_open),
                   now_ms(), lid_event,
                   None if lux is None else round(lux, 2),
                   None if proximity_cm is None else round(proximity_cm, 2))

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "Telemetry":
        data = json.loads(raw)
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
