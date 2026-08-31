from __future__ import annotations


PELAKSANA_RAPAT_CUSTOM = "Masukkan Nama Pelaksana"
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
JENIS_RAPAT_OPTIONS = [
    "Rapat Kerja",
    "RDPU (Rapat Dengar Pendapat Umum)",
    "Rapat Internal",
    "Rapat Pansus",
]
JENIS_PERJALANAN_DPRD = ["Kunjungan Kerja", "Kunjungan Konsultasi", "Bimbingan Teknis"]
JENIS_PERJALANAN_SETWAN = ["Studi Komparasi", "Kunjungan Konsultasi", "Bimbingan Teknis"]

# Referensi autocomplete tujuan dari SIPS lama. Pengguna tetap dapat mengetik
# nama instansi/wilayah lain secara bebas.
DEFAULT_TRAVEL_DESTINATIONS = [
    "Kota Manado", "Kota Bitung", "Kota Tomohon", "Kota Kotamobagu",
    "Kabupaten Minahasa", "Kabupaten Minahasa Utara", "Kabupaten Minahasa Selatan",
    "Kabupaten Minahasa Tenggara", "Kabupaten Bolaang Mongondow",
    "Kabupaten Bolaang Mongondow Utara", "Kabupaten Bolaang Mongondow Selatan",
    "Kabupaten Bolaang Mongondow Timur", "Kabupaten Kepulauan Sangihe",
    "Kabupaten Kepulauan Talaud", "Kabupaten Kepulauan Sitaro",
    "DKI Jakarta", "Kota Surabaya", "Kota Bandung", "Kota Medan",
    "Kota Semarang", "Kota Makassar", "Kota Palembang", "Kota Tangerang",
    "Kota Tangerang Selatan", "Kota Bekasi", "Kota Depok", "Kota Yogyakarta",
    "Kota Surakarta (Solo)", "Kota Balikpapan", "Kota Samarinda",
    "Kota Banjarmasin", "Kota Pontianak", "Kota Denpasar", "Kota Mataram",
    "Kota Kupang", "Kota Ambon", "Kota Jayapura", "Kota Sorong",
    "Kota Palu", "Kota Kendari", "Kota Gorontalo", "Kota Palangkaraya",
    "Kota Tarakan", "Kota Banda Aceh", "Kota Padang", "Kota Pekanbaru",
    "Kota Jambi", "Kota Bengkulu", "Kota Bandar Lampung", "Kota Pangkalpinang",
    "Kota Tanjungpinang",
]

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

AKD_LAINNYA_DISPLAY_NAMES = {
    "Banggar": "Badan Anggaran",
    "Banmus": "Badan Musyawarah",
    "Bapemperda": "Badan Pembentukan Perda",
}
KATEGORI_DPRD_ORDER = [
    "Pimpinan DPRD", "Komisi I", "Komisi II", "Komisi III",
    "Banggar", "Bapemperda", "Banmus", "Badan Kehormatan",
    "Fraksi PDIP", "Fraksi Gerindra", "Fraksi Nasdem-PI", "Fraksi Golkar",
    "Fraksi Partai Demokrat", "Tenaga Ahli Fraksi DPRD",
]

SULAWESI_UTARA_CITIES = [
    "Sulawesi Utara", "Sulut", "Bitung", "Manado", "Tomohon", "Kotamobagu",
    "Minahasa Utara", "Minahasa Selatan", "Minahasa Tenggara", "Minahasa",
    "Bolaang Mongondow Utara", "Bolaang Mongondow Selatan", "Bolaang Mongondow Timur",
    "Bolaang Mongondow", "Kepulauan Sangihe", "Kepulauan Talaud", "Kepulauan Sitaro",
    "Tondano", "Airmadidi", "Amurang", "Ratahan", "Lolak", "Boroko", "Molibagu",
    "Tutuyan", "Tahuna", "Melonguane", "Ondong", "Siau",
]
JABODETABEK_CITIES = ["Jakarta", "Bekasi", "Tangerang", "Depok", "Bogor"]
WITA_KEYWORDS = [
    "Bali", "Denpasar", "Nusa Tenggara Barat", "NTB", "Mataram", "Lombok",
    "Nusa Tenggara Timur", "NTT", "Kupang", "Kalimantan Tengah", "Palangkaraya",
    "Palangka Raya", "Kalimantan Selatan", "Banjarmasin", "Banjarbaru",
    "Kalimantan Timur", "Samarinda", "Balikpapan", "Kalimantan Utara",
    "Tanjung Selor", "Tarakan", "Sulawesi", "Manado", "Bitung", "Tomohon",
    "Kotamobagu", "Minahasa", "Palu", "Makassar", "Kendari", "Mamuju", "Gorontalo",
]
WIT_KEYWORDS = [
    "Maluku Utara", "Ternate", "Sofifi", "Maluku", "Ambon", "Papua Barat",
    "Manokwari", "Papua Barat Daya", "Sorong", "Papua Tengah", "Nabire",
    "Papua Pegunungan", "Jayawijaya", "Wamena", "Papua Selatan", "Merauke",
    "Papua", "Jayapura",
]
JENIS_PERJALANAN_PREFIXES_FALLBACK = [
    "kunjungan konsultasi", "kunjungan kerja", "konsultasi", "bimbingan teknis",
    "studi komparasi", "studi banding",
]
