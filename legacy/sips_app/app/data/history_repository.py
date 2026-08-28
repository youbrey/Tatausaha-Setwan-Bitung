"""
Repository untuk riwayat pengisian formulir surat (sips_history.json),
supaya pengguna bisa memuat ulang isian sebelumnya tanpa mengetik ulang.

Struktur data: dua kategori terpisah supaya jendela "Riwayat Surat" bisa
menampilkan 2 tabel independen (Surat Perjalanan Dinas & Surat Undangan
Rapat):

    {
        "perjalanan_dinas": { "<nomor_surat>": {...}, ... },
        "undangan_rapat":   { "<kunci_unik>":  {...}, ... },
    }

PERUBAHAN (mode multi-komputer): file ini sekarang dibaca/ditulis lewat
app.data.shared_store, yang menambahkan:
1. File lock antar-proses/antar-komputer supaya dua komputer yang
   menyimpan surat di detik yang sama tidak saling menimpa data
   (read-modify-write yang aman), bukan cuma "siapa cepat dia menang".
2. Tulis atomik (temp file + rename) supaya komputer lain tidak pernah
   membaca file riwayat yang sedang setengah tertulis.

Selama HISTORY_FILE menunjuk ke folder jaringan bersama (lihat
app/config/network_config.py), otomatis SEMUA komputer melihat riwayat
surat, database, dan nomor surat yang sama.
"""
from app.config.settings import HISTORY_FILE
from app.data.shared_store import locked_read_json, locked_write_json, SharedStoreError

_KOSONG = {"perjalanan_dinas": {}, "undangan_rapat": {}}


def _normalisasi(data):
    if not isinstance(data, dict):
        return {"perjalanan_dinas": {}, "undangan_rapat": {}}
    # Migrasi format lama: dulu file ini flat -> {"<nomor_surat>": {...}}
    # tanpa kategori. Supaya riwayat lama tidak hilang, bungkus jadi
    # kategori "perjalanan_dinas" (satu-satunya kategori yang direkam
    # oleh versi sebelumnya).
    if "perjalanan_dinas" not in data and "undangan_rapat" not in data:
        return {"perjalanan_dinas": data, "undangan_rapat": {}}
    data.setdefault("perjalanan_dinas", {})
    data.setdefault("undangan_rapat", {})
    return data


def load_history():
    return _normalisasi(locked_read_json(HISTORY_FILE, dict(_KOSONG)))


def save_history(history_data):
    try:
        locked_write_json(HISTORY_FILE, history_data)
    except SharedStoreError:
        # Jangan biarkan aplikasi crash kalau folder jaringan sedang sibuk/
        # putus di momen ini -- pengguna sudah dapat file surat-nya (docx)
        # walau riwayat gagal tersimpan sekali ini. UI pemanggil sebaiknya
        # tetap memberi tahu lewat toast/messagebox (lihat main_window).
        raise
    except Exception:
        pass


# ----------------------------------------------------------------------
# CEK NOMOR SURAT (dipakai supaya nomor yang sudah dipakai di komputer A
# tidak bisa dipakai LAGI untuk surat BARU di komputer B/C -- kecuali
# memang sedang meng-edit/merevisi surat dengan nomor yang sama).
# ----------------------------------------------------------------------
def _semua_nomor_terpakai(history_data):
    nomor_set = set()
    for key, entry in history_data.get("perjalanan_dinas", {}).items():
        for field in ("nomor_surat", "nomor_surat_asn", "nomor_pemberitahuan_dprd",
                      "nomor_pemberitahuan_asn", "nomor_spd_dprd", "nomor_spd_asn"):
            nilai = str(entry.get(field, "")).strip()
            if nilai:
                nomor_set.add(nilai)
    for key, entry in history_data.get("undangan_rapat", {}).items():
        nilai = str(entry.get("nomor_surat", "")).strip()
        if nilai:
            nomor_set.add(nilai)
    return nomor_set


def nomor_surat_sudah_dipakai(nomor, kecuali_nomor_induk=None):
    """True kalau `nomor` sudah tercatat di riwayat MANA PUN (termasuk yang
    dibuat komputer lain, karena membaca langsung dari file bersama
    ter-update). `kecuali_nomor_induk`: nomor surat induk perjalanan dinas
    yang SEDANG diedit -- supaya proses edit/revisi surat yang sama tidak
    ditolak sebagai "sudah dipakai" oleh dirinya sendiri."""
    nomor = str(nomor or "").strip()
    if not nomor:
        return False
    history_data = load_history()
    if kecuali_nomor_induk and str(kecuali_nomor_induk).strip() in history_data.get("perjalanan_dinas", {}):
        # Jangan hitung nomor-nomor milik surat yang sedang diedit itu sendiri.
        entry_lama = history_data["perjalanan_dinas"][str(kecuali_nomor_induk).strip()]
        nomor_lama = {str(entry_lama.get(f, "")).strip() for f in (
            "nomor_surat", "nomor_surat_asn", "nomor_pemberitahuan_dprd",
            "nomor_pemberitahuan_asn", "nomor_spd_dprd", "nomor_spd_asn")}
        if nomor in nomor_lama:
            return False
    return nomor in _semua_nomor_terpakai(history_data)


# ----------------------------------------------------------------------
# CEK JUDUL/MATERI DUPLIKAT (untuk toast peringatan di formulir)
# ----------------------------------------------------------------------
def cari_judul_serupa(materi_text, kecuali_nomor_induk=None):
    """Kembalikan entri riwayat perjalanan dinas yang materi/agenda-nya
    SAMA PERSIS (setelah dirapikan: huruf kecil semua & spasi berlebih
    dibuang) dengan `materi_text`, atau None kalau belum pernah ada.
    Dipakai untuk menampilkan toast peringatan saat pengguna mengetik
    ulang judul yang sudah pernah dibuat sebelumnya (baik oleh komputer
    ini maupun komputer lain, karena riwayat dibaca dari file bersama)."""
    target = " ".join(str(materi_text or "").strip().lower().split())
    if len(target) < 6:  # judul terlalu pendek -> jangan bandingkan (banyak false-positive)
        return None
    history_data = load_history()
    for nomor, entry in history_data.get("perjalanan_dinas", {}).items():
        if kecuali_nomor_induk and nomor == str(kecuali_nomor_induk).strip():
            continue
        judul_lama = " ".join(str(entry.get("materi_tugas", "")).strip().lower().split())
        if judul_lama and judul_lama == target:
            return entry
    return None


# ----------------------------------------------------------------------
# DATA UNTUK MENU "JUDUL PERJADIN"
# ----------------------------------------------------------------------
def daftar_judul_perjadin():
    """Ringkas riwayat perjalanan dinas jadi baris-baris untuk tabel menu
    'Judul Perjadin': Judul/Materi, Kategori Pelaksana, Tanggal Pelaksanaan
    (rentang), dan Tempat Tujuan. Diurutkan dari yang terbaru dibuat."""
    history_data = load_history()
    rows = []
    for nomor, entry in history_data.get("perjalanan_dinas", {}).items():
        rows.append({
            "nomor_surat": nomor,
            "judul": entry.get("materi_tugas", "-") or "-",
            "kategori_pelaksana": entry.get("kategori_pelaksana_display", "-") or "-",
            "tanggal_pelaksanaan": entry.get("tanggal_pelaksanaan_display", "-") or "-",
            "tempat_tujuan": entry.get("tujuan_bertugas", "-") or "-",
            "tanggal_dibuat": entry.get("tanggal_dibuat", ""),
        })
    rows.sort(key=lambda r: r["tanggal_dibuat"], reverse=True)
    return rows
