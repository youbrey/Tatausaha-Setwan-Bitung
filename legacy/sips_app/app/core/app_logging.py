"""
Logging error yang AMAN dipakai di build .exe mode windowed (console=False).

Kenapa perlu file terpisah:
Sebelumnya banyak tempat di kode memakai `print(f"Gagal ...: {e}")` sebagai
penanganan error di dalam blok except. Ini bekerja normal saat dijalankan
lewat `python main.py` (ada konsol beneran), TAPI begitu dibungkus jadi .exe
dengan `console=False` (lihat build.spec), PyInstaller membuat sys.stdout /
sys.stderr bernilai None karena memang tidak ada konsol untuk ditulisi.
Memanggil print() saat sys.stdout None akan melempar exception BARU
("lost sys.stdout" / AttributeError) dari DALAM blok except -- artinya
error asli malah tertutup oleh error baru yang tidak tertangani, dan proses
pembuatan dokumen bisa gagal diam-diam tanpa jejak sama sekali bagi
pengguna. Inilah salah satu penyebab paling mungkin dari laporan "error
setelah build executable" yang tidak muncul sewaktu masih dijalankan lewat
python biasa.

safe_log() menggantikan semua print(...) itu: selalu menulis ke file log di
folder user_data (aman dibaca untuk diagnosa), dan tidak akan pernah ikut
melempar exception baru walau penulisan filenya sendiri gagal.
"""
import datetime
import os

try:
    from app.config.settings import USER_DATA_DIR
    LOG_FILE = os.path.join(USER_DATA_DIR, "sips_error.log")
except Exception:
    LOG_FILE = os.path.join(os.path.expanduser("~"), "sips_error.log")


def safe_log(msg):
    """Catat satu baris pesan error ke file log. TIDAK PERNAH memakai
    print()/sys.stdout, dan tidak pernah melempar exception ke pemanggil,
    supaya pemanggilnya (blok except di alur generate dokumen) tetap aman
    dijalankan di build .exe windowed."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass
