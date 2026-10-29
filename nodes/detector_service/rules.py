"""Rule-based sensor fusion untuk status keamanan kotak.

Status:
  SAFE          sistem DISARM (pemilik sedang mengambil paket / nonaktif)
  SECURE        ARM, tutup tertutup, tidak ada guncangan
  TAMPER_ALERT  ARM, tutup tertutup, tetapi ada guncangan (percobaan bongkar)
  ILLEGAL_OPEN  ARM, tutup terbuka (latch: bertahan sampai DISARM/ARM ulang)
"""
import time
from dataclasses import dataclass
from typing import Optional

from shared.messages import Telemetry

SECURE, SAFE = "SECURE", "SAFE"
TAMPER_ALERT, ILLEGAL_OPEN = "TAMPER_ALERT", "ILLEGAL_OPEN"
ALERT_STATES = (TAMPER_ALERT, ILLEGAL_OPEN)


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    score: float = 0.0   # motion_rms / ambang


class BoxRules:
    def __init__(self, motion_threshold=0.7, confirm_motion=2, confirm_open=1,
                 tamper_hold=10.0, armed=True):
        self.motion_threshold = motion_threshold
        self.confirm_motion = confirm_motion
        self.confirm_open = confirm_open
        self.tamper_hold = tamper_hold
        self.armed = armed
        self._reset()

    def _reset(self):
        self._motion_count = 0
        self._open_count = 0
        self._last_tamper: Optional[float] = None
        self._illegal = False

    def arm(self):
        self.armed = True
        self._reset()

    def disarm(self):
        self.armed = False
        self._reset()

    def evaluate(self, t: Telemetry, now: Optional[float] = None) -> Decision:
        now = time.monotonic() if now is None else now
        score = t.motion_rms / self.motion_threshold if self.motion_threshold else 0.0

        if not self.armed:
            return Decision(SAFE, "Sistem DISARM: pemantauan nonaktif", score)

        moving = t.motion_rms >= self.motion_threshold
        self._motion_count = self._motion_count + 1 if moving else 0
        self._open_count = self._open_count + 1 if t.lid_open else 0

        if self._open_count >= self.confirm_open:
            self._illegal = True
        if self._motion_count >= self.confirm_motion:
            self._last_tamper = now

        if self._illegal:
            if t.lid_open:
                return Decision(ILLEGAL_OPEN, "Tutup kotak terbuka saat sistem ARM", score)
            return Decision(ILLEGAL_OPEN,
                            "Tutup sempat terbuka lalu tertutup lagi; DISARM/ARM untuk reset", score)

        if self._last_tamper is not None and now - self._last_tamper <= self.tamper_hold:
            return Decision(TAMPER_ALERT,
                            f"Guncangan saat tertutup (RMS {t.motion_rms:.2f} >= {self.motion_threshold})",
                            score)

        return Decision(SECURE, "Tertutup dan tenang", score)
