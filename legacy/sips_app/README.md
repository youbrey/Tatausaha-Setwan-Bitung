# SIPS — Sistem Informasi Persuratan Sekretariat DPRD Kota Bitung

Aplikasi desktop (CustomTkinter) untuk membuat Surat Tugas, Surat
Pemberitahuan, SPD/SPPD, Daftar Hadir, dan Undangan Paripurna DPRD/ASN.

Versi ini adalah hasil **restrukturisasi** dari `app_v6.py` (monolit ±2.900
baris) menjadi struktur modular berbasis tanggung jawab (separation of
concerns), supaya setiap bagian bisa diubah tanpa membongkar file lain.

## Struktur Folder

```
sips_app/
├── main.py                      # Entry point — jalankan ini
├── requirements.txt
├── build.spec                   # Konfigurasi PyInstaller
├── resources/                   # SEMUA aset & data statis
│   ├── templates/               # Template .docx (docxtpl)
│   ├── data/                    # database_dprd_asn.xlsx (master data)
│   └── icons/                   # app_icon.ico (icon utk build .exe)
├── user_data/                   # Dibuat otomatis saat runtime
│   ├── sips_data.json           # Cache database DPRD/ASN
│   ├── sips_history.json        # Riwayat isian formulir
│   └── sips_accounts.json       # Akun login (hashed password)
└── app/
    ├── config/
    │   ├── settings.py          # Path file, judul app, ukuran window, tema
    │   └── constants.py         # Daftar kota, kategori DPRD, kata kunci zona waktu
    ├── core/                    # LOGIKA BISNIS MURNI (tanpa kode UI)
    │   ├── auth.py               # Hash & verifikasi password, load/save akun
    │   ├── text_utils.py         # Deteksi zona waktu, nomor surat, periode tanggal
    │   ├── docx_utils.py         # Operasi level python-docx (tabel, page break, gabung dok)
    │   ├── document_generators.py # Generator Surat Tugas & Pemberitahuan
    │   └── sppd_generators.py    # Generator SPD/SPPD
    ├── data/                    # AKSES DATA (file I/O)
    │   ├── database_repository.py # Baca Excel/CSV, load/save database DPRD/ASN
    │   └── history_repository.py  # Load/save riwayat formulir
    └── ui/                      # TAMPILAN & ORKESTRASI
        ├── login_window.py        # Window login
        ├── account_window.py      # Window manajemen akun (superadmin)
        ├── main_window.py         # Window utama (SIPSApp): semua panel & form
        └── components/            # (disiapkan untuk komponen UI re-usable, lihat Roadmap)
```

## Mengapa dibagi seperti ini?

| Folder        | Isi                                   | Boleh import dari               | Alasan |
|---------------|----------------------------------------|----------------------------------|--------|
| `app/config`  | Konstanta & path                       | -                                | Satu sumber kebenaran lokasi file/setting. Ganti nama folder template? Cukup edit di sini. |
| `app/core`    | Fungsi murni (input → output, tanpa widget) | `app/config`                | Bisa dites tanpa membuka GUI. Bisa dipakai ulang (mis. nanti dibuat versi CLI/batch). |
| `app/data`    | Baca/tulis file (json, xlsx, csv)      | `app/config`                    | Kalau nanti pindah dari JSON ke database SQLite/PostgreSQL, hanya folder ini yang disentuh. |
| `app/ui`      | Window, layout, event handler          | `app/config`, `app/core`, `app/data` | Tempat satu-satunya yang "boleh" berisi kode Tkinter/CustomTkinter. |

Aturan dependensi: **config → core/data → ui** (satu arah). `core` dan
`data` tidak pernah mengimpor apa pun dari `ui`.

## Menjalankan aplikasi

```bash
pip install -r requirements.txt
python main.py
```

Login default (super admin): `tatausaha` / `tatausahayesyesyes`
(ubah lewat menu "Kelola Akun Pengguna" setelah login pertama kali —
disarankan langsung diganti).

## Build menjadi .exe (PyInstaller)

PyInstaller dipilih karena paling umum & stabil dipakai untuk aplikasi
Tkinter/CustomTkinter, dokumentasinya luas, dan mendukung baik mode
`--onedir` (start lebih cepat, disarankan) maupun `--onefile`.

```bash
pip install pyinstaller
pyinstaller build.spec
```

Hasil ada di `dist/SIPS/SIPS.exe` beserta folder `resources/` di
sampingnya (sudah ikut dibundel otomatis oleh `build.spec`). Folder
`user_data/` akan dibuat otomatis di sebelah file `.exe` saat aplikasi
pertama kali dijalankan.

Icon aplikasi (`resources/icons/app_icon.ico`) sudah dipasang otomatis
ke `.exe` lewat `build.spec` (parameter `icon=`) dan juga dipasang sebagai
icon title-bar window lewat `app/ui/main_window.py`
(`self.iconbitmap(APP_ICON_PATH)`).

> Catatan: fitur Live Preview PDF (`docx2pdf`) memerlukan Microsoft Word
> terpasang di komputer (Windows/Mac). Di komputer tanpa Word, sediakan
> LibreOffice — kode sudah punya fallback `soffice` (`_convert_with_soffice`
> di `main_window.py`).

## Apa yang berubah secara perilaku?

Tidak ada — ini murni pemindahan kode (refactor struktural), bukan
penulisan ulang logika. Satu-satunya perubahan teknis:

- Path file (`database_dprd_asn.xlsx`, template `.docx`, `sips_data.json`,
  dst.) sekarang terpusat di `app/config/settings.py` dan menunjuk ke folder
  `resources/` / `user_data/`, bukan lagi nama file polos di direktori kerja
  saat ini. Ini supaya aplikasi tetap berfungsi benar setelah dibekukan
  jadi `.exe` (PyInstaller mengekstrak resource ke folder sementara).

## Roadmap Refactor Lanjutan (opsional, untuk iterasi berikutnya)

`app/ui/main_window.py` saat ini masih berisi satu kelas besar `SIPSApp`
yang menangani sidebar, 3 form (Perjalanan Dinas / Undangan Paripurna /
Undangan Biasa), checklist personel, dan live preview — karena
widget-widget itu saling berbagi banyak state lewat `self.*`. Pemisahan
yang aman butuh diperkenalkan pola "Controller" terlebih dahulu. Saran
langkah berikutnya, satu per satu (boleh dilakukan kapan saja tanpa
mendesak):

1. Pindahkan blok `setup_perjalanan_dinas_form` + `build_context` +
   `generate_documents_action` ke `app/ui/views/perjalanan_dinas_view.py`
   sebagai `CTkFrame` mandiri yang menerima referensi ke `app` (window
   utama) lewat constructor.
2. Pindahkan blok `setup_undangan_paripurna_form` + `generate_undangan_paripurna`
   ke `app/ui/views/undangan_paripurna_view.py` dengan pola yang sama.
3. Pindahkan panel kanan (filter kategori + checklist personel) ke
   `app/ui/components/personnel_panel.py`.
4. Pindahkan seluruh logika `_preview_worker` & konversi PDF ke
   `app/ui/components/preview_panel.py` (atau `app/core/preview_engine.py`
   untuk bagian konversi PDF-nya, karena itu murni proses file, bukan UI).

Folder `app/ui/components/` sudah disiapkan kosong untuk langkah ini.
