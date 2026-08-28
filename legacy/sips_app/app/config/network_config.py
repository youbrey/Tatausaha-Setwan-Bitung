"""
Pengaturan folder BERSAMA (network share) supaya beberapa komputer bisa
saling terhubung. Berbeda dari data lain (sips_data.json dkk yang memang
harus dipakai bersama), pengaturan INI justru harus LOKAL per-komputer
(supaya masing-masing komputer bisa menunjuk ke UNC path yang mungkin
berbeda cara penulisannya, dan supaya salah satu komputer tidak sengaja
"mematikan" mode jaringan komputer lain).

File konfigurasi ini sengaja disimpan berdampingan dengan folder
resources/ (BASE_DIR), BUKAN di user_data/, karena beberapa build tools
lain menghapus user_data/ saat "reset data" -- pengaturan sambungan
jaringan sebaiknya tidak ikut hilang saat itu.

Cara pakai di lapangan (3 komputer contoh):
1. Siapkan SATU folder di jaringan lokal (LAN) yang bisa dibaca-tulis dari
   ketiga komputer, misalnya folder "SIPS_DATA" yang di-share dari salah
   satu komputer lewat Windows File Sharing, atau dari NAS.
2. Di SETIAP komputer, buka menu "Pengaturan Jaringan" di aplikasi (atau
   panggil `set_shared_dir(...)` sekali), isi path folder tsb, contoh:
       \\\\KOMPUTER-TU\\SIPS_DATA        (folder share Windows)
       Z:\\SIPS_DATA                     (kalau sudah di-map jadi drive Z:)
3. Setelah diisi, sips_data.json / sips_history.json / sips_accounts.json
   otomatis dibaca-tulis dari folder itu (lihat app/config/settings.py),
   bukan lagi dari folder user_data/ lokal komputer masing-masing.
4. Kalau folder jaringan sedang tidak terjangkau (mis. LAN putus), aplikasi
   TIDAK ikut error -- otomatis memakai salinan lokal terakhir sebagai
   cadangan (lihat resolve_data_path()) supaya tetap bisa dipakai offline,
   dan akan menyambung lagi otomatis begitu folder bisa diakses lagi.
"""
import json
import os

from app.config.settings import BASE_DIR

_CONFIG_FILE = os.path.join(BASE_DIR, "network_config.json")


def _load_raw():
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def get_shared_dir():
    """Kembalikan path folder bersama yang dikonfigurasi, atau None kalau
    komputer ini belum diatur untuk mode jaringan (berarti tetap memakai
    folder user_data/ lokal seperti sebelumnya -- aman untuk instalasi
    tunggal / komputer yang sengaja berdiri sendiri)."""
    raw = _load_raw()
    path = raw.get("shared_dir", "").strip()
    return path or None


def is_network_mode_enabled():
    raw = _load_raw()
    return bool(raw.get("shared_dir", "").strip()) and raw.get("enabled", True)


def set_shared_dir(path, enabled=True):
    """Simpan path folder bersama untuk KOMPUTER INI SAJA. Dipanggil dari
    menu Pengaturan Jaringan (superadmin)."""
    data = _load_raw()
    data["shared_dir"] = (path or "").strip()
    data["enabled"] = enabled
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def is_shared_dir_reachable(path=None):
    """Cek cepat apakah folder jaringan sedang bisa diakses (mis. LAN
    tersambung, folder share masih ada). Dipakai untuk menampilkan
    indikator status koneksi di UI dan untuk fallback otomatis."""
    path = path or get_shared_dir()
    if not path:
        return False
    try:
        return os.path.isdir(path) and os.access(path, os.W_OK)
    except Exception:
        return False
