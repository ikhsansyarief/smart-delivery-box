"""Pembacaan sensor: Termux:API (HP asli) atau simulator (laptop)."""
import json
import random
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Optional


class SensorError(Exception):
    pass


@dataclass
class SensorSample:
    seconds: float
    acceleration: tuple          # (x, y, z) m/s^2
    lux: Optional[float] = None  # cahaya sekitar
    proximity_cm: Optional[float] = None


def _pick(names, keyword, exclude=()):
    cands = [n for n in names
             if keyword in n.lower() and not any(e in n.lower() for e in exclude)]
    non_wake = [n for n in cands if "non-wakeup" in n.lower()]
    pool = non_wake or cands
    return pool[0] if pool else None


def _parse_objects(text: str) -> dict:
    """termux-sensor bisa mencetak beberapa objek JSON berurutan; gabungkan."""
    dec, idx, merged = json.JSONDecoder(), 0, {}
    text = text.strip()
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        obj, idx = dec.raw_decode(text, idx)
        merged.update(obj)
    return merged


class TermuxSensors:
    """Accelerometer + Light + Proximity lewat `termux-sensor`."""

    def __init__(self, accel_name="", light_name="", proximity_name=""):
        if not shutil.which("termux-sensor"):
            raise SensorError("termux-sensor tidak ditemukan. Jalankan: pkg install termux-api "
                              "(atau pakai --source simulator)")
        try:
            out = subprocess.run(["termux-sensor", "-l"], capture_output=True, text=True,
                                 timeout=12, check=True).stdout
            names = json.loads(out)["sensors"]
        except (subprocess.SubprocessError, ValueError, KeyError) as exc:
            raise SensorError(f"Gagal membaca daftar sensor: {exc}") from exc

        self.accel = accel_name or _pick(names, "accelerometer", exclude=("uncalibrated",))
        self.light = light_name or _pick(names, "light")
        self.prox = proximity_name or _pick(names, "proximity")
        if not self.accel:
            raise SensorError("Accelerometer tidak ditemukan di HP ini")
        if not (self.light or self.prox):
            raise SensorError("Butuh minimal sensor Light atau Proximity untuk status tutup")
        print(f"[SENSOR] accel={self.accel} | light={self.light} | proximity={self.prox}")

    def read(self) -> SensorSample:
        wanted = [n for n in (self.accel, self.light, self.prox) if n]
        try:
            out = subprocess.run(["termux-sensor", "-s", ",".join(wanted), "-n", "1"],
                                 capture_output=True, text=True, timeout=12, check=True).stdout
            data = _parse_objects(out)
        except (subprocess.SubprocessError, ValueError) as exc:
            raise SensorError(f"Gagal membaca sensor: {exc}") from exc

        def vals(name):
            return data.get(name, {}).get("values") if name else None

        a = vals(self.accel)
        if not a or len(a) < 3:
            raise SensorError("Data accelerometer kosong (izinkan Termux:API di pengaturan Android)")
        l, p = vals(self.light), vals(self.prox)
        return SensorSample(
            time.monotonic(),
            tuple(float(v) for v in a[:3]),
            float(l[0]) if l else None,
            float(p[0]) if p else None,
        )


class SimulatedSensors:
    """Simulator untuk latihan tanpa HP.
    Skenario: still | shake | open | demo (siklus 40 detik)."""

    SCENARIOS = ("still", "shake", "open", "demo")

    def __init__(self, scenario="demo"):
        if scenario not in self.SCENARIOS:
            raise SensorError(f"Skenario harus salah satu dari {self.SCENARIOS}")
        self.scenario = scenario
        self.t0 = time.monotonic()
        print(f"[SENSOR] Simulator, skenario: {scenario}")

    def _phase(self) -> str:
        if self.scenario != "demo":
            return self.scenario
        t = (time.monotonic() - self.t0) % 40
        if t < 10:
            return "still"
        if t < 16:
            return "shake"
        if t < 22:
            return "still"
        if t < 30:
            return "open"
        return "still"

    def read(self) -> SensorSample:
        phase = self._phase()
        g = random.gauss
        x, y, z = g(0, 0.04), g(0, 0.04), 9.81 + g(0, 0.04)
        if phase == "shake":
            x, y, z = x + g(0, 2.5), y + g(0, 2.5), z + g(0, 2.5)
        if phase == "open":
            lux, prox = 250 + random.random() * 50, 5.0
        else:
            lux, prox = 0.5 + random.random(), 0.0
        return SensorSample(time.monotonic(), (x, y, z), lux, prox)


def make_sensor(source: str, cfg, scenario: str = "demo"):
    if source == "auto":
        source = "termux" if shutil.which("termux-sensor") else "simulator"
    if source == "termux":
        return TermuxSensors(cfg.accel_name, cfg.light_name, cfg.proximity_name)
    if source == "simulator":
        return SimulatedSensors(scenario)
    raise SensorError("--source harus auto, termux, atau simulator")
