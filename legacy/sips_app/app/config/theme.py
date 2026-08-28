"""
Tema visual aplikasi, diadaptasi dari palet warna & tipografi template
Adminator (HTML5 Bootstrap Admin Dashboard) agar tampilan SIPS konsisten
dengan referensi desain yang diberikan: sidebar terang, kartu/panel putih
dengan border tipis, aksen warna ungu-indigo, dan font sans-serif modern.

Pakai konstanta di sini untuk SEMUA warna & font baru di app/ui/*, supaya
perubahan tema cukup dilakukan di satu tempat.
"""

# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------
# Adminator memakai "Roboto" (web font). Di desktop kita pakai font sistem
# yang tersedia secara native dan tampilannya paling dekat: Segoe UI di
# Windows, fallback ke Arial/Helvetica di OS lain (CustomTkinter/Tk akan
# otomatis fallback ke font default jika nama font tidak ditemukan).
FONT_FAMILY = "Segoe UI"


def font(size: int, weight: str = "normal"):
    """Helper supaya pemanggilan font seragam: font(14, 'bold')."""
    if weight == "normal":
        return (FONT_FAMILY, size)
    return (FONT_FAMILY, size, weight)


# ---------------------------------------------------------------------------
# Palet warna (diturunkan dari src/assets/styles/spec/settings/baseColors.scss
# pada template Adminator)
# ---------------------------------------------------------------------------
COLOR_PRIMARY        = "#7774E7"   # $default-primary
COLOR_PRIMARY_HOVER  = "#5F5BD0"
COLOR_PRIMARY_SOFT   = "#EEEDFC"   # versi pucat untuk highlight/selected state

COLOR_SECONDARY      = "#9C99EF"   # turunan lebih muda dari primary, dipakai utk aksen ke-2
COLOR_SECONDARY_HOVER = "#7774E7"

COLOR_SUCCESS        = "#37C936"
COLOR_SUCCESS_HOVER  = "#2BA62A"
COLOR_SUCCESS_SOFT   = "#E7F9E6"   # versi pucat, dipakai utk latar ikon kartu Dashboard
COLOR_DANGER         = "#FF3C7E"
COLOR_DANGER_HOVER   = "#E22F69"
COLOR_DANGER_SOFT    = "#FFE7EF"
COLOR_WARNING        = "#FFCC00"
COLOR_WARNING_HOVER  = "#E0B400"
COLOR_WARNING_SOFT   = "#FFF8E0"
COLOR_INFO           = "#0F9AEE"
COLOR_INFO_HOVER     = "#0C7FC4"
COLOR_INFO_SOFT      = "#E5F4FE"

COLOR_GREY_DARK       = "#64748B"   # tombol netral (logout, kembali, dll)
COLOR_GREY_DARK_HOVER = "#475569"

# Latar & permukaan
COLOR_BODY_BG   = "#F2F3F5"   # latar belakang utama jendela (di luar sidebar)
COLOR_SIDEBAR_BG = "#FFFFFF"  # sidebar Adminator: putih, bukan gelap
COLOR_CARD_BG   = "#FFFFFF"   # kartu/panel: putih bersih
COLOR_BORDER    = "#E6ECF5"   # border tipis antar elemen, khas Adminator
COLOR_SOFT_BG   = "#F9FAFB"   # latar elemen sekunder di dalam kartu (mis. kotak filter)

# Teks
COLOR_TEXT_DARK = "#313435"   # judul / heading
COLOR_TEXT_BODY = "#72777A"   # teks isi / label biasa
COLOR_TEXT_MUTED = "#9AA3AF"  # teks kecil (versi, footer)

CARD_CORNER_RADIUS = 8
SIDEBAR_ITEM_PADY = 6   # jarak vertikal seragam antar item di sidebar
