# BoxGuard — Smart Anti-Theft Delivery Box

Edge 1 (HP di kotak) → MQTT/TLS HiveMQ → Detector (laptop) → Edge 2 (HP pemilik) + Dashboard web.

| Komponen | File |
|---|---|
| Edge 1 kotak paket | `box_node.py` |
| Edge 2 HP pemilik (alarm) | `owner_node.py` |
| Detector + server dashboard | `detector.py`, `nodes/detector_service/rules.py` |
| Sensor / olah data | `shared/sensors.py`, `shared/processing.py` |
| Dashboard | `dashboard/index.html` |

## Setup
```
pkg install python git termux-api        # di Termux (kedua HP)
pip install -r requirements.txt
cp .env.example .env                     # lalu ganti PROJECT_ID (harus sama di semua perangkat)
```

## Jalankan (urutan)
```
python detector.py        # laptop → buka http://localhost:8000 (atau IP LAN yang tercetak)
python owner_node.py      # HP pemilik
python box_node.py        # HP kotak (letakkan layar menghadap tutup, TUTUP dulu baru jalankan)
```
Tanpa HP: `python box_node.py --source simulator --scenario demo`
(skenario: still | shake | open | demo).

## Logika status
| Kondisi | Status |
|---|---|
| DISARM | SAFE |
| ARM, tertutup, tenang | SECURE |
| ARM, tertutup, RMS ≥ ambang ×2 window | TAMPER_ALERT |
| ARM, tutup terbuka | ILLEGAL_OPEN (latch sampai DISARM/ARM) |

Alur penggunaan: kurir menaruh paket → tutup → ARM. Pemilik mengambil paket → DISARM → tutup → ARM lagi.

## Kalibrasi
Lihat nilai `lux` di log `box_node.py` saat tutup tertutup dan terbuka, lalu sesuaikan
`LIGHT_OPEN_LUX` / `LIGHT_CLOSE_LUX` dan `MOTION_RMS_THRESHOLD` di `.env`.

## Tes
`python -m unittest discover tests`
