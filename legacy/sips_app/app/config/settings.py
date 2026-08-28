"""
Konfigurasi umum aplikasi: lokasi file data, file resource (template/icon),
dan pengaturan tema UI. Satu-satunya tempat yang perlu diubah jika lokasi
file/folder data ingin dipindah.
"""
import os
import sys
import customtkinter as ctk


def _base_dir():
    """Direktori dasar aplikasi. Saat dibekukan jadi .exe (PyInstaller),
    file resource dibaca dari folder sementara (_MEIPASS) jika --onefile,
    atau folder yang sama dengan executable jika --onedir."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _resource_dir():
    """Lokasi folder resources/, mendukung mode PyInstaller --onefile
    (resource diekstrak ke sys._MEIPASS) maupun development biasa."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "resources")
    return os.path.join(_base_dir(), "resources")


BASE_DIR = _base_dir()
RESOURCE_DIR = _resource_dir()
TEMPLATES_DIR = os.path.join(RESOURCE_DIR, "templates")
DATA_RESOURCE_DIR = os.path.join(RESOURCE_DIR, "data")
ICONS_DIR = os.path.join(RESOURCE_DIR, "icons")

# File data aplikasi (dibuat/diubah saat runtime, disimpan di luar resources
# supaya tidak ikut tertimpa saat aplikasi di-update/dibangun ulang).
USER_DATA_DIR = os.path.join(BASE_DIR, "user_data")
os.makedirs(USER_DATA_DIR, exist_ok=True)

def _resolve_shared_or_local(filename):
    """Kembalikan path folder BERSAMA (network share) untuk `filename` jika
    komputer ini sudah diatur memakai mode jaringan (lihat
    app/config/network_config.py) DAN folder itu sedang terjangkau saat
    aplikasi start. Kalau tidak diatur / sedang tidak terjangkau (mis. LAN
    putus), otomatis kembali ke folder user_data/ lokal supaya aplikasi
    tetap bisa dipakai offline tanpa error."""
    try:
        from app.config.network_config import get_shared_dir, is_shared_dir_reachable
        shared_dir = get_shared_dir()
        if shared_dir and is_shared_dir_reachable(shared_dir):
            return os.path.join(shared_dir, filename)
    except Exception:
        pass
    return os.path.join(USER_DATA_DIR, filename)


DATA_FILE = _resolve_shared_or_local("sips_data.json")
HISTORY_FILE = _resolve_shared_or_local("sips_history.json")
ACCOUNTS_FILE = _resolve_shared_or_local("sips_accounts.json")
IS_NETWORK_MODE = DATA_FILE != os.path.join(USER_DATA_DIR, "sips_data.json")

# Database master Excel (dipakai sebagai sumber awal/import data DPRD & ASN)
DATABASE_XLSX = os.path.join(DATA_RESOURCE_DIR, "database_dprd_asn.xlsx")

# Template-template dokumen Word
TEMPLATE_ST_DPRD_BIASA = os.path.join(TEMPLATES_DIR, "surat_tugas_dprd_biasa.docx")
TEMPLATE_ST_DPRD_TABEL = os.path.join(TEMPLATES_DIR, "surat_tugas_dprd_tabel.docx")
TEMPLATE_ST_ASN_BIASA = os.path.join(TEMPLATES_DIR, "surat_tugas_asn_biasa.docx")
TEMPLATE_ST_ASN_TABEL = os.path.join(TEMPLATES_DIR, "surat_tugas_asn_tabel.docx")
TEMPLATE_PEMBERITAHUAN = os.path.join(TEMPLATES_DIR, "pemberitahuan_dprd.docx")
TEMPLATE_PARIPURNA = os.path.join(TEMPLATES_DIR, "rapat_paripurna.docx")
TEMPLATE_RAPAT_BIASA = os.path.join(TEMPLATES_DIR, "rapat_biasa.docx")
TEMPLATE_SPD_DEPAN = os.path.join(TEMPLATES_DIR, "SPD_DPRD.docx")
TEMPLATE_SPD_BELAKANG = os.path.join(TEMPLATES_DIR, "SPD_BELAKANG.docx")
TEMPLATE_DAFTAR_HADIR = os.path.join(TEMPLATES_DIR, "DAFTAR_HADIR_DPRD.docx")

# --- Naskah Dinas & Daftar Hadir untuk Undangan Rapat (Biasa/Paripurna) ---
# Ditambahkan atas permintaan pengguna: template Word yang dipakai adalah
# template ASLI kantor (nama & susunan anggota per Komisi/AKD sudah
# tertulis TETAP di dalam tabel Word-nya, BUKAN diisi otomatis dari
# database/roster) -- hanya 3-4 variabel header (isi/perihal rapat, hari,
# tanggal, jam) yang diisi otomatis oleh aplikasi. Lihat
# app/core/daftar_hadir_rapat_generator.py & app/core/naskah_dinas_generator.py.
TEMPLATE_NASKAH_DINAS_RAPAT = os.path.join(TEMPLATES_DIR, "naskah_dinas_rapat.docx")

# Peta "Pelaksana Rapat" (nilai combobox di Undangan Biasa, lihat
# constants.PELAKSANA_RAPAT_OPTIONS) -> file Daftar Hadir yang sesuai.
# CATATAN: tidak ada template utk "Pimpinan dan Anggota Badan Kehormatan"
# maupun utk pilihan "Masukan Nama Pelaksana" (custom) -- lihat penanganan
# gap ini di generate_daftar_hadir_rapat_action() (main_window.py).
TEMPLATE_DAFTAR_HADIR_RAPAT_MAP = {
    "Pimpinan dan Anggota DPRD Kota Bitung": os.path.join(TEMPLATES_DIR, "daftar_hadir_rapat_paripurna_dprd.docx"),
    "Pimpinan dan Anggota Komisi I": os.path.join(TEMPLATES_DIR, "daftar_hadir_rapat_komisi_1.docx"),
    "Pimpinan dan Anggota Komisi II": os.path.join(TEMPLATES_DIR, "daftar_hadir_rapat_komisi_2.docx"),
    "Pimpinan dan Anggota Komisi III": os.path.join(TEMPLATES_DIR, "daftar_hadir_rapat_komisi_3.docx"),
    "Pimpinan dan Anggota Badan Anggaran": os.path.join(TEMPLATES_DIR, "daftar_hadir_rapat_banggar.docx"),
    "Pimpinan dan Anggota Badan Pembentukan Perda": os.path.join(TEMPLATES_DIR, "daftar_hadir_rapat_bapemperda.docx"),
    "Pimpinan dan Anggota Badan Musyawarah": os.path.join(TEMPLATES_DIR, "daftar_hadir_rapat_banmus.docx"),
}
# Template untuk Undangan Paripurna (Dewan Lengkap) -- selalu sama,
# tidak tergantung pilihan combobox (Undangan Paripurna tidak punya
# combobox Pelaksana Rapat).
TEMPLATE_DAFTAR_HADIR_PARIPURNA = os.path.join(TEMPLATES_DIR, "daftar_hadir_rapat_paripurna_dprd.docx")
# Lembar tambahan (opsional, bisa disertakan sebagai halaman berikutnya):
TEMPLATE_DAFTAR_HADIR_PIHAK_TERKAIT = os.path.join(TEMPLATES_DIR, "daftar_hadir_rapat_pihak_terkait.docx")
TEMPLATE_DAFTAR_HADIR_SEKRETARIAT = os.path.join(TEMPLATES_DIR, "daftar_hadir_rapat_sekretariat.docx")
TEMPLATE_DAFTAR_HADIR_TAF = os.path.join(TEMPLATES_DIR, "daftar_hadir_rapat_taf.docx")

APP_ICON_PATH = os.path.join(ICONS_DIR, "app_icon.ico")

APP_TITLE = "SIPS - Aplikasi Pembuat Surat Perjalanan Dinas DPRD Bitung"
APP_VERSION = "v7.0"
APP_GEOMETRY = "1900x900"
APP_MIN_SIZE = (1500, 800)

SUPERADMIN_USERNAME = "tatausaha"
SUPERADMIN_DEFAULT_PASSWORD = "tatausahayesyesyes"


def configure_theme():
    """Panggil sekali di awal (sebelum membuat window apa pun).

    Skema warna & font detail (sidebar, kartu, tombol) didefinisikan di
    app/config/theme.py mengikuti palet template Adminator; di sini hanya
    diatur mode dasar CustomTkinter.
    """
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
