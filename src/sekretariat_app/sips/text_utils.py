"""
Fungsi-fungsi pengolahan teks & tanggal yang murni (tanpa state UI):
deteksi zona waktu, normalisasi nama kota, penomoran surat otomatis,
dan pembuatan daftar periode tanggal per tujuan perjalanan dinas.
"""
import re

_ROMAN_TOKENS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}


def slugify_filename(text):
    """Ubah teks bebas jadi token slug huruf-kecil-dengan-dash, KECUALI
    angka romawi (I, II, III, ...) yang dipertahankan huruf besar supaya
    'Komisi III' -> 'komisi-III', bukan 'komisi-iii'."""
    if not text:
        return ""
    tokens = re.split(r"[\s/_,.-]+", str(text).strip())
    out = []
    for tok in tokens:
        if not tok:
            continue
        if tok.upper() in _ROMAN_TOKENS:
            out.append(tok.upper())
            continue
        clean = re.sub(r"[^0-9a-zA-Z]+", "", tok)
        if clean:
            out.append(clean.lower())
    return "-".join(out)

from datetime import datetime, timedelta

from sekretariat_app.sips.constants import (
    WITA_KEYWORDS,
    WIT_KEYWORDS,
    JENIS_PERJALANAN_PREFIXES_FALLBACK,
    SULAWESI_UTARA_CITIES,
    JABODETABEK_CITIES,
)


def detect_zona_waktu(tempat_text):
    """Deteksi zona waktu (WIB/WITA/WIT) berdasarkan teks tempat/tujuan tugas.

    Urutan pengecekan: WIT -> WITA -> default WIB.
    """
    if not tempat_text:
        return "WIB"
    text_lower = tempat_text.lower()
    for kw in WIT_KEYWORDS:
        if kw.lower() in text_lower:
            return "WIT"
    for kw in WITA_KEYWORDS:
        if kw.lower() in text_lower:
            return "WITA"
    return "WIB"


def strip_jenis_perjalanan_prefix(materi_text, jenis_perjalanan=""):
    """Hilangkan kata jenis perjalanan (mis. "Kunjungan Kerja", "Konsultasi")
    jika ia muncul di awal teks materi_tugas, sehingga sisa teks dimulai dari
    kata "tentang ..." atau kata berikutnya."""
    text = (materi_text or "").strip()
    if not text:
        return text
    text_lower = text.lower()

    # 1) Coba cocokkan dengan jenis_perjalanan yang benar-benar dipilih pengguna
    #    (paling akurat karena sesuai pilihan combo box di aplikasi).
    jp = (jenis_perjalanan or "").strip().lower()
    if jp and text_lower.startswith(jp):
        return text[len(jp):].strip()

    # 2) Fallback: cocokkan dengan daftar kata kunci umum, terpanjang dulu
    #    supaya "kunjungan konsultasi" tidak salah cocok jadi "konsultasi" saja.
    for prefix in sorted(JENIS_PERJALANAN_PREFIXES_FALLBACK, key=len, reverse=True):
        if text_lower.startswith(prefix):
            return text[len(prefix):].strip()

    return text


def increment_nomor(nomor_base, increment=0):
    if increment == 0:
        return nomor_base
    parts = nomor_base.split('/')
    try:
        raw = parts[0].strip()
        lebar = len(raw)  # simpan lebar asli, mis. "01" -> 2 digit
        angka = int(raw)
        parts[0] = str(angka + increment).zfill(lebar)
        return '/'.join(parts)
    except (ValueError, IndexError):
        return nomor_base

def increment_nomor_paripurna(nomor_base, increment=0):
    """Khusus format baku surat Undangan Paripurna: '005/DPRD/XXX/VII/2026'.
    Bagian '005/DPRD' (segmen index 0 dan 1) TIDAK BOLEH berubah -- yang
    harus naik berurutan tiap halaman adalah segmen index 2 (posisi XXX).
    Lebar digit asli (mis. '003' -> 3 digit) dipertahankan dengan zfill,
    sama seperti perilaku increment_nomor untuk segmen lain.
    """
    if increment == 0:
        return nomor_base
    parts = nomor_base.split('/')
    try:
        raw = parts[2].strip()
        lebar = len(raw)
        angka = int(raw)
        parts[2] = str(angka + increment).zfill(lebar)
        return '/'.join(parts)
    except (ValueError, IndexError):
        return nomor_base

def increment_nomor_spd(nomor_base, increment=0):
    if increment == 0:
        return nomor_base
    parts = nomor_base.split('/')
    try:
        raw = parts[0].strip()
        lebar = len(raw)
        angka = int(raw)
        parts[0] = str(angka + increment).zfill(lebar)
        return '/'.join(parts)
    except (ValueError, IndexError):
        return nomor_base

def extract_city_name(text):
    text = text.strip()
    match = re.search(r'(Kota|Kabupaten|Provinsi)\s+([\w\s]+)', text)
    if match:
        return f"{match.group(1)} {match.group(2).strip()}"
    if "DKI Jakarta" in text:
        return "Kota Jakarta"
    if "Jakarta" in text:
        return "Kota Jakarta"
    return text

def is_plain_region_name(text):
    """True hanya jika SELURUH teks tujuan murni nama wilayah administratif
    (Kota/Kabupaten/Provinsi ... atau "DKI Jakarta"), TANPA nama instansi
    lain menempel di depan/belakangnya.

    Dipakai untuk memutuskan apakah kata "DPRD " perlu ditambahkan di depan
    tujuan (mis. "Kota Bekasi" -> "DPRD Kota Bekasi"). Kalau tujuan sudah
    berupa nama instansi spesifik (mis. "BPBD Provinsi DKI Jakarta",
    "Universitas Sam Ratulangi", "Kantor Gubernur Sulut") maka fungsi ini
    HARUS mengembalikan False supaya kata "DPRD" tidak nempel salah tempat
    di depan nama instansi yang bukan DPRD.
    """
    t = text.strip()
    if not t:
        return False
    if re.fullmatch(r'(Kota|Kabupaten|Provinsi)\s+[\w\s.\-()]+', t, flags=re.IGNORECASE):
        return True
    if t.upper() in ("DKI JAKARTA", "JAKARTA"):
        return True
    return False

def is_in_sulawesi_utara(city_name):
    for c in SULAWESI_UTARA_CITIES:
        if c in city_name:
            return True
    return False

def is_in_jabodetabek(city_name):
    for c in JABODETABEK_CITIES:
        if c in city_name:
            return True
    return False

def generate_periods(tanggal_mulai_str, destinations):
    bulan_map = {
        "Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
        "Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
        "September": 9, "Oktober": 10, "November": 11, "Desember": 12
    }
    parts = tanggal_mulai_str.split()
    if len(parts) == 3:
        day = int(parts[0])
        month = bulan_map.get(parts[1], 1)
        year = int(parts[2])
        start_date = datetime(year, month, day)
    else:
        start_date = datetime.now()

    first_city = extract_city_name(destinations[0]) if destinations else ""
    offset = 0 if is_in_sulawesi_utara(first_city) else 1
    base_date = start_date + timedelta(days=offset)

    periods = []
    for idx, dest in enumerate(destinations):
        current_date = base_date + timedelta(days=idx)
        hari_indonesia = {
            "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
            "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
        }
        hari_eng = current_date.strftime("%A")
        hari = hari_indonesia.get(hari_eng, hari_eng)
        bulan_indo = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                      "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        tanggal_str = f"{current_date.day} {bulan_indo[current_date.month]} {current_date.year}"
        periods.append({
            "tujuan": dest,
            "hari": hari,
            "tanggal": tanggal_str
        })
    return periods


_BULAN_INDO = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
               "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
_BULAN_INDO_KE_ANGKA = {b.lower(): i for i, b in enumerate(_BULAN_INDO) if b}


def _parse_tanggal_indo(value):
    """Terima objek date/datetime ATAU string 'D Bulan YYYY' (format yang
    dipakai format_indonesian_date di main_window), kembalikan tuple
    (hari, bulan, tahun) atau None kalau gagal diparsing."""
    if value is None or value == "":
        return None
    if hasattr(value, "day") and hasattr(value, "month") and hasattr(value, "year"):
        return value.day, value.month, value.year
    parts = str(value).strip().split()
    if len(parts) != 3:
        return None
    try:
        hari = int(parts[0])
        bulan = _BULAN_INDO_KE_ANGKA.get(parts[1].lower())
        tahun = int(parts[2])
        if bulan is None:
            return None
        return hari, bulan, tahun
    except (ValueError, IndexError):
        return None


def format_rentang_tanggal(tanggal_mulai, tanggal_akhir):
    """Format rentang tanggal pelaksanaan jadi bentuk ringkas ala
    '06-10 Juli 2026' (dipakai di menu 'Judul Perjadin'). Menerima objek
    date/datetime maupun string 'D Bulan YYYY'. Aturan:
    - Bulan & tahun sama          -> '06-10 Juli 2026'
    - Bulan beda, tahun sama      -> '28 Juni - 03 Juli 2026'
    - Tahun beda                  -> '30 Desember 2026 - 02 Januari 2027'
    - Kalau salah satu tak valid / hanya satu tanggal terisi -> tampilkan
      apa adanya (fallback), supaya tidak pernah melempar error ke UI.
    """
    mulai = _parse_tanggal_indo(tanggal_mulai)
    akhir = _parse_tanggal_indo(tanggal_akhir)

    if not mulai and not akhir:
        return "-"
    if not mulai:
        return str(tanggal_akhir)
    if not akhir:
        return str(tanggal_mulai)

    h1, b1, t1 = mulai
    h2, b2, t2 = akhir

    if (h1, b1, t1) == (h2, b2, t2):
        return f"{h1:02d} {_BULAN_INDO[b1]} {t1}"
    if t1 == t2 and b1 == b2:
        return f"{h1:02d}-{h2:02d} {_BULAN_INDO[b1]} {t1}"
    if t1 == t2:
        return f"{h1:02d} {_BULAN_INDO[b1]} - {h2:02d} {_BULAN_INDO[b2]} {t1}"
    return f"{h1:02d} {_BULAN_INDO[b1]} {t1} - {h2:02d} {_BULAN_INDO[b2]} {t2}"


def format_jabatan_penandatanganan(jabatan_raw):
    """Format jabatan untuk baris tanda tangan surat: kalau jabatannya Ketua
    atau Wakil Ketua (DPRD), cukup ditulis 'Ketua' / 'Wakil Ketua' TANPA
    embel-embel 'DPRD Kota Bitung' di belakangnya -- sesuai instruksi. Untuk
    jabatan lain (mis. Sekretaris DPRD, Ketua Banggar, dst) dibiarkan APA
    ADANYA, tidak disentuh, karena instruksi ini spesifik untuk Ketua/Wakil
    Ketua saja.

    Pemanggil TETAP bertanggung jawab menambahkan tanda koma sendiri di
    template/output (mis. f"{jabatan}," ) -- fungsi ini hanya mengurus
    teks jabatannya, bukan tanda bacanya.
    """
    if not jabatan_raw:
        return jabatan_raw
    txt = jabatan_raw.strip()
    # Hilangkan akhiran "DPRD KOTA BITUNG" (varian spasi/kapitalisasi apa pun)
    # HANYA untuk keperluan pengecekan pola, teks asli tidak diubah kalau
    # ternyata bukan pola Ketua/Wakil Ketua.
    stripped = re.sub(r"\s*DPRD\s+KOTA\s+BITUNG\s*$", "", txt, flags=re.IGNORECASE).strip()
    normalized = stripped.upper()

    if normalized == "KETUA":
        return "Ketua"

    m = re.match(r"^WAKIL\s+KETUA(?:\s+([IVX]+))?$", normalized)
    if m:
        romawi = m.group(1)
        if romawi and romawi in _ROMAN_TOKENS:
            return f"Wakil Ketua {romawi}"
        return "Wakil Ketua"

    return txt  # jabatan lain (Sekretaris DPRD, Ketua Banggar, dst): apa adanya
