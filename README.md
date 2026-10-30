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
pkg install python git termux-api        
pip install -r requirements.txt
cp .env.example .env                   
```

## Jalankan 
```
python detector.py        # laptop → buka http://localhost:8000 
python owner_node.py      # HP pemilik
python box_node.py        # HP kotak 
```
(skenario: still | shake | open | demo).

## Logika status
| Kondisi | Status |
|---|---|
| DISARM | SAFE |
| ARM, tertutup, tenang | SECURE |
| ARM, tertutup, RMS ≥ ambang ×2 window | TAMPER_ALERT |
| ARM, tutup terbuka | ILLEGAL_OPEN (latch sampai DISARM/ARM) |

Alur penggunaan: kurir menaruh paket → tutup → ARM. Pemilik mengambil paket → DISARM → tutup → ARM lagi.
