"""Dua jenis data processing di Edge 1:
 A. Motion RMS (accelerometer)  -> intensitas guncangan kotak
 B. Threshold + State Transition Detection (light/proximity) -> status tutup
"""
import math
from dataclasses import dataclass
from typing import Optional

GRAVITY = 9.81


def motion_rms(samples) -> float:
    """A. magnitude = sqrt(x²+y²+z²); error = magnitude - g; RMS dari error."""
    if not samples:
        return 0.0
    errors = [math.sqrt(x * x + y * y + z * z) - GRAVITY
              for x, y, z in (s.acceleration for s in samples)]
    return math.sqrt(sum(e * e for e in errors) / len(errors))


class LidDetector:
    """B. Status tutup dengan histeresis supaya tidak 'berkedip'.
    Cahaya: >= open_lux => terbuka, <= close_lux => tertutup, di antaranya: tahan status.
    Proximity: jarak >= near_cm => menjauh (terbuka), < near_cm => dekat (tertutup).
    mode: light | proximity | any (salah satu bilang terbuka) | both (keduanya)."""

    def __init__(self, mode="light", open_lux=15.0, close_lux=5.0, near_cm=3.0):
        self.mode, self.open_lux, self.close_lux, self.near_cm = mode, open_lux, close_lux, near_cm
        self.is_open = False  # asumsi awal: kotak tertutup

    def _opinions(self, lux, prox):
        """True = bilang terbuka, False = bilang tertutup. Zona histeresis tidak menambah opini."""
        ops = []
        if self.mode in ("light", "any", "both") and lux is not None:
            if lux >= self.open_lux:
                ops.append(True)
            elif lux <= self.close_lux:
                ops.append(False)
        if self.mode in ("proximity", "any", "both") and prox is not None:
            ops.append(prox >= self.near_cm)
        return ops

    def update(self, lux: Optional[float], prox: Optional[float]) -> Optional[str]:
        """Perbarui status; kembalikan 'OPENED'/'CLOSED' bila terjadi transisi."""
        ops = self._opinions(lux, prox)
        new = self.is_open
        if ops:
            if self.mode == "both":
                new = all(ops)          # terbuka hanya jika semua sensor sepakat
            else:
                new = any(ops)          # salah satu bilang terbuka => terbuka
        if new == self.is_open:
            return None
        self.is_open = new
        return "OPENED" if new else "CLOSED"


@dataclass
class WindowResult:
    motion_rms: float
    lid_open: bool
    lid_event: Optional[str]
    lux: Optional[float]
    proximity_cm: Optional[float]


def process_window(samples, lid: LidDetector) -> WindowResult:
    last_event = None
    for s in samples:
        ev = lid.update(s.lux, s.proximity_cm)
        if ev:
            last_event = ev
    luxes = [s.lux for s in samples if s.lux is not None]
    prox = [s.proximity_cm for s in samples if s.proximity_cm is not None]
    return WindowResult(
        motion_rms=motion_rms(samples),
        lid_open=lid.is_open,
        lid_event=last_event,
        lux=sum(luxes) / len(luxes) if luxes else None,
        proximity_cm=prox[-1] if prox else None,
    )
