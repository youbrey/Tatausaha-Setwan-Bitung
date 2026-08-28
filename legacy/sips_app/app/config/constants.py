"""
Konstanta data referensi: daftar kota, kategori DPRD, kata kunci zona waktu,
dan daftar jenis surat untuk panel Live Preview. Pisahkan dari logika supaya
mudah ditambah/diubah tanpa menyentuh kode fungsi.
"""
from app.config.settings import (
    TEMPLATE_PEMBERITAHUAN,
    TEMPLATE_SPD_DEPAN,
    TEMPLATE_SPD_BELAKANG,
)

# Daftar jenis surat yang bisa dipilih pada panel Live Preview.
PREVIEW_TEMPLATES = [
    ("Surat Tugas (DPRD)",     "__surat_tugas_dprd__",    "ctx"),
    ("Surat Tugas (ASN)",      "__surat_tugas_asn__",     "ctx"),
    ("Surat Pemberitahuan",    TEMPLATE_PEMBERITAHUAN,    "ctx"),
    ("SPD DPRD - Halaman Depan",    TEMPLATE_SPD_DEPAN,        "person_dprd"),
    ("SPD DPRD - Halaman Belakang", TEMPLATE_SPD_BELAKANG,     "person_dprd"),
    ("SPD ASN - Halaman Depan",     TEMPLATE_SPD_DEPAN,        "person_asn"),
    ("SPD ASN - Halaman Belakang",  TEMPLATE_SPD_BELAKANG,     "person_asn"),
    ("Daftar Hadir",                "__daftar_hadir__",        "ctx"),
    ("Undangan Paripurna",          "__undangan_paripurna__",  "ctx"),
    ("Undangan Rapat Biasa",        "__undangan_biasa__",      "ctx"),
]

# Pilihan combobox "Pelaksana Rapat" untuk Undangan Rapat Biasa. Urutan sesuai
# permintaan pengguna. Key di sini dipakai juga sebagai lookup ke
# TUJUAN_SURAT_DPRD_MAP di bawah untuk mengisi {{tujuan_surat_dprd}} otomatis.
# Nilai khusus (bukan nama pelaksana rapat sungguhan) yang memicu textbox
# input manual muncul di UI -- lihat setup_undangan_biasa_form() &
# _on_pelaksana_rapat_change() di main_window.py. SENGAJA diletakkan di
# baris PALING BAWAH combobox supaya daftar pelaksana rapat "asli" tetap
# rapi berurutan di atas, baru opsi custom di paling akhir.
PELAKSANA_RAPAT_CUSTOM = "Masukan Nama Pelaksana"

PELAKSANA_RAPAT_OPTIONS = [
    "Pimpinan dan Anggota DPRD Kota Bitung",
    "Pimpinan dan Anggota Komisi I",
    "Pimpinan dan Anggota Komisi II",
    "Pimpinan dan Anggota Komisi III",
    "Pimpinan dan Anggota Badan Anggaran",
    "Pimpinan dan Anggota Badan Pembentukan Perda",
    "Pimpinan dan Anggota Badan Musyawarah",
    "Pimpinan dan Anggota Badan Kehormatan",
    PELAKSANA_RAPAT_CUSTOM,
]

# Pemetaan pilihan "Pelaksana Rapat" -> teks {{tujuan_surat_dprd}} yang akan
# dicetak (huruf besar semua + BOLD, lihat get_undangan_biasa_context()).
# Contoh dari pengguna: "Pimpinan dan Anggota Komisi III" ->
# "PIMPINAN DAN ANGGOTA KOMISI III DPRD KOTA BITUNG". Untuk AKD Lainnya,
# kata "Komisi" TIDAK dipakai dan singkatannya ditulis lengkap (Badan
# Anggaran, Badan Musyawarah, Badan Pembentukan Perda, Badan Kehormatan),
# karena badan-badan itu bukan komisi.
TUJUAN_SURAT_DPRD_MAP = {
    "Pimpinan dan Anggota DPRD Kota Bitung": "PIMPINAN DAN ANGGOTA DPRD KOTA BITUNG",
    "Pimpinan dan Anggota Komisi I": "PIMPINAN DAN ANGGOTA KOMISI I DPRD KOTA BITUNG",
    "Pimpinan dan Anggota Komisi II": "PIMPINAN DAN ANGGOTA KOMISI II DPRD KOTA BITUNG",
    "Pimpinan dan Anggota Komisi III": "PIMPINAN DAN ANGGOTA KOMISI III DPRD KOTA BITUNG",
    "Pimpinan dan Anggota Badan Anggaran": "PIMPINAN DAN ANGGOTA BADAN ANGGARAN DPRD KOTA BITUNG",
    "Pimpinan dan Anggota Badan Pembentukan Perda": "PIMPINAN DAN ANGGOTA BADAN PEMBENTUKAN PERDA DPRD KOTA BITUNG",
    "Pimpinan dan Anggota Badan Musyawarah": "PIMPINAN DAN ANGGOTA BADAN MUSYAWARAH DPRD KOTA BITUNG",
    "Pimpinan dan Anggota Badan Kehormatan": "PIMPINAN DAN ANGGOTA BADAN KEHORMATAN DPRD KOTA BITUNG",
}

# Nama tampilan (untuk dicetak di surat & UI) untuk kategori AKD Lainnya yang
# di database/Excel & logika internal masih memakai SINGKATAN sebagai key
# pencocokan kategori ("Banggar", "Bapemperda", "Banmus") supaya tidak perlu
# mengubah data master Excel yang sudah ada. "Badan Kehormatan" sudah berupa
# nama lengkap, jadi tidak perlu dipetakan ulang.
AKD_LAINNYA_DISPLAY_NAMES = {
    "Banggar": "Badan Anggaran",
    "Banmus": "Badan Musyawarah",
    "Bapemperda": "Badan Pembentukan Perda",
}

# Pilihan combobox "Jenis Rapat" untuk Undangan Rapat Biasa.
JENIS_RAPAT_OPTIONS = [
    "Rapat Kerja",
    "RDPU (Rapat Dengar Pendapat Umum)",
    "Rapat Internal",
    "Rapat Pansus",
]

# NB: path file template fisik ada di app/config/settings.py
# (TEMPLATE_ST_DPRD_BIASA, dst) supaya lokasi folder resources terpusat
# di satu tempat.

KATEGORI_DPRD_ORDER = [
    "Pimpinan DPRD", "Komisi I", "Komisi II", "Komisi III",
    "Banggar", "Bapemperda", "Banmus", "Badan Kehormatan",
    "Fraksi PDIP", "Fraksi Gerindra", "Fraksi Nasdem-PI", "Fraksi Golkar",
    "Fraksi Partai Demokrat",
    "Tenaga Ahli Fraksi DPRD",
]

# Struktur kategori calon pelaksana (dipakai untuk membangun checklist filter
# 2-level di panel kanan). "AKD" dan "AKD LAINNYA" adalah header grup saja
# (tidak checkable), sedangkan item di dalamnya adalah checkbox kategori
# sungguhan yang harus cocok dengan kolom "Kategori" di database Excel.
#
# "Pansus" sengaja TIDAK punya nama tetap: nama Pansus yang sedang berjalan
# berubah-ubah setiap kali dibentuk (mis. "Pansus RTRW", "Pansus LKPJ 2026"),
# jadi namanya dibuat lewat kotak isian (lihat setup_category_checkboxes)
# yang bisa diketik ulang oleh pengguna, bukan checkbox dengan teks tetap.
KATEGORI_STRUKTUR = {
    "AKD": {
        "items": ["Pimpinan DPRD", "Komisi I", "Komisi II", "Komisi III"],
        "subgroups": {
            "AKD Lainnya": {
                "items": ["Banggar", "Bapemperda", "Banmus", "Badan Kehormatan"],
                "custom_item": "Pansus",  # nama boleh diubah pengguna di UI
            },
        },
    },
    "Fraksi": {
        "items": ["Fraksi PDIP", "Fraksi Gerindra", "Fraksi Nasdem-PI", "Fraksi Golkar", "Fraksi Partai Demokrat"],
        "subgroups": {},
    },
    "Tenaga Ahli": {
        "items": ["Tenaga Ahli Fraksi DPRD"],
        "subgroups": {},
    },
}

# Semua kategori "AKD" (dipakai buat pengelompokan personel; Pimpinan +
# Komisi + AKD Lainnya, TIDAK termasuk Fraksi/Pansus/Pendamping ASN).
KATEGORI_AKD_INTI = ["Pimpinan DPRD", "Komisi I", "Komisi II", "Komisi III"]
KATEGORI_AKD_LAINNYA = ["Banggar", "Bapemperda", "Banmus", "Badan Kehormatan"]
KATEGORI_FRAKSI = ["Fraksi PDIP", "Fraksi Gerindra", "Fraksi Nasdem-PI", "Fraksi Golkar", "Fraksi Partai Demokrat"]
KATEGORI_TENAGA_AHLI = ["Tenaga Ahli Fraksi DPRD"]


SULAWESI_UTARA_CITIES = [
    # Nama provinsi (harus dicek duluan / termasuk, supaya "Provinsi Sulawesi
    # Utara" ikut terdeteksi, bukan cuma nama kabupaten/kota).
    "Sulawesi Utara", "Sulut",
    # 4 Kota resmi di Sulawesi Utara
    "Bitung", "Manado", "Tomohon", "Kotamobagu",
    # 11 Kabupaten resmi di Sulawesi Utara (nama administratif)
    "Minahasa Utara", "Minahasa Selatan", "Minahasa Tenggara", "Minahasa",
    "Bolaang Mongondow Utara", "Bolaang Mongondow Selatan", "Bolaang Mongondow Timur",
    "Bolaang Mongondow", "Kepulauan Sangihe", "Kepulauan Talaud", "Kepulauan Sitaro",
    # Nama ibu kota kabupaten yang sering dipakai orang sebagai sebutan kota
    # sehari-hari (mis. "Kota Tondano"), meskipun secara administratif bukan
    # "Kota" resmi -- tetap harus dikenali sebagai wilayah Sulawesi Utara.
    "Tondano", "Airmadidi", "Amurang", "Ratahan", "Lolak", "Boroko",
    "Molibagu", "Tutuyan", "Tahuna", "Melonguane", "Ondong", "Siau",
]

JABODETABEK_CITIES = ["Jakarta", "Bekasi", "Tangerang", "Depok", "Bogor"]

WITA_KEYWORDS = [
    # Bali, Nusa Tenggara
    "Bali", "Denpasar", "Nusa Tenggara Barat", "NTB", "Mataram", "Lombok",
    "Nusa Tenggara Timur", "NTT", "Kupang",
    # Kalimantan (Tengah/Selatan/Timur/Utara - bukan Kalimantan Barat)
    "Kalimantan Tengah", "Palangkaraya", "Palangka Raya",
    "Kalimantan Selatan", "Banjarmasin", "Banjarbaru",
    "Kalimantan Timur", "Samarinda", "Balikpapan",
    "Kalimantan Utara", "Tanjung Selor", "Tarakan",
    # Sulawesi (semua provinsi)
    "Sulawesi Utara", "Manado", "Bitung", "Tomohon", "Kotamobagu", "Minahasa",
    "Bolaang Mongondow", "Sangihe", "Talaud", "Sitaro",
    "Sulawesi Tengah", "Palu",
    "Sulawesi Selatan", "Makassar",
    "Sulawesi Tenggara", "Kendari",
    "Sulawesi Barat", "Mamuju",
    "Gorontalo",
]

WIT_KEYWORDS = [
    "Maluku Utara", "Ternate", "Sofifi",
    "Maluku", "Ambon",
    "Papua Barat", "Manokwari",
    "Papua Barat Daya", "Sorong",
    "Papua Tengah", "Nabire",
    "Papua Pegunungan", "Jayawijaya", "Wamena",
    "Papua Selatan", "Merauke",
    "Papua", "Jayapura",
]

# WIB tidak perlu daftar lengkap karena dipakai sebagai default/fallback
# (Sumatra, Jawa, Kalimantan Barat, Banten, DKI Jakarta, dll).


JENIS_PERJALANAN_PREFIXES_FALLBACK = [
    "kunjungan konsultasi", "kunjungan kerja", "konsultasi",
    "bimbingan teknis", "studi komparasi", "studi banding",
]

