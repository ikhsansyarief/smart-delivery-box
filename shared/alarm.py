"""Aksi alarm di HP Pemilik via Termux:API (getar, notifikasi, suara TTS)."""
import shutil
import subprocess

MESSAGES = {
    "TAMPER_ALERT": ("Kotak paket diguncang!", "Ada percobaan pembongkaran paksa pada kotak paket."),
    "ILLEGAL_OPEN": ("Kotak paket dibuka paksa!", "Tutup kotak terbuka saat sistem aktif."),
    "TEST": ("Tes alarm", "Ini hanya tes alarm dari dashboard."),
}


def _run(cmd):
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        print(f"[ALARM] gagal menjalankan {cmd[0]}: {exc}")


def trigger(alert: dict):
    title, text = MESSAGES.get(alert.get("status"), ("Peringatan kotak paket", alert.get("reason", "")))
    title = f"BoxGuard: {title}"
    print(f"\n!!! {title} | {alert.get('reason', text)}\a\n")
    if shutil.which("termux-vibrate"):
        _run(["termux-vibrate", "-d", "1500", "-f"])
    if shutil.which("termux-notification"):
        _run(["termux-notification", "--id", "boxguard", "--title", title,
              "--content", alert.get("reason", text), "--priority", "max"])
    if shutil.which("termux-tts-speak"):
        _run(["termux-tts-speak", f"Peringatan. {title}"])
