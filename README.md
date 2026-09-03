# SIPS Terpadu — Sekretariat DPRD Kota Bitung

Aplikasi desktop Windows berbasis Python dan PySide6 yang menyatukan navigasi
SIPS, Rekapitulasi TPP, serta Dokumentasi Foto dalam satu shell modern. Semua
data utama diproses dan disimpan secara lokal; aplikasi tidak mengunggah
dokumen, foto, atau data pegawai ke internet.

Versi source saat ini: **0.9.0 — Tujuan dinamis dan penomoran Undangan Biasa**.

## Menu aplikasi

1. Dashboard
2. Perjalanan Dinas
   - DPRD
   - Sekretariat DPRD
3. Rekapitulasi Surat Perjalanan Dinas
4. Surat Undangan
   - Undangan Paripurna
   - Undangan Biasa
5. Rekapitulasi Surat Undangan
6. Rekapitulasi TPP
7. Dokumentasi Foto
8. Kelola User
9. Logout

Menu **Dokumentasi Foto** berada tepat setelah **Rekapitulasi TPP**. Seluruh
workspace tampil pada halaman utama di samping sidebar, bukan pada jendela atau
browser terpisah.

## Kemampuan Dokumentasi Foto

- Canvas WYSIWYG asli Qt berbasis `QGraphicsScene`/`QGraphicsView`.
- Ukuran kertas A4, F4, Letter, Legal, serta ukuran kustom.
- Orientasi portrait/landscape dan pengaturan empat sisi margin.
- Sebelas template kolase 1, 2, 3, 4, 5, 6, dan 8 foto.
- Kisi kustom sampai 6 × 6.
- Studio auto-kolase dengan preview foto nyata sebelum diterapkan.
- Mini-preview visual untuk setiap gaya kisi, bukan daftar nama berbentuk teks.
- Pengaturan lebar/tinggi seluruh kumpulan foto dan jarak antar-foto dalam mm.
- Kolase otomatis dari seluruh foto di panel Media menjadi beberapa halaman.
- Impor satu atau banyak foto, impor folder, dan drag-and-drop dari Explorer.
- Media tray lokal dengan thumbnail.
- Pindah dan resize elemen secara langsung pada kanvas.
- Crop interaktif bergaya Canva: frame tetap, foto dapat diseret dan di-zoom
  langsung di dalam frame, disertai fit cover/contain/fill dan rotasi.
- Border, warna border, sudut bulat, serta keterangan foto.
- Teks bebas yang dapat dipindah, diedit langsung, dirotasi, dan dikunci.
- Font, ukuran, lebar kotak, bold, italic, underline, alignment, jarak huruf,
  tinggi baris, warna, background, opacity, shadow, dan glow.
- Kop surat opsional pada halaman pertama, dua logo, informasi instansi, alamat,
  kontak, dan pilihan garis kop.
- Tambah, duplikat, pindah, dan hapus halaman.
- Undo/redo berbasis snapshot serta autosave lokal.
- Simpan/muat `.dokufoto.json` dan ekspor/impor arsip `.zip` beserta foto.
- Impor kompatibel dengan proyek JSON dan arsip ZIP dari DokuFoto-React.
- Ekspor WYSIWYG ke DOCX dan PDF menggunakan render halaman 300 DPI.
- Pratinjau multipage dan cetak langsung melalui dialog printer Windows.

Hasil DOCX sengaja menggunakan gambar halaman 300 DPI penuh agar posisi,
ukuran, crop, teks, dan elemen lain sama dengan tampilan kanvas. Elemen di dalam
DOCX karena itu tidak diedit satu per satu; perubahan dilakukan pada proyek
Dokumentasi Foto lalu diekspor kembali.

## Rekapitulasi TPP

Modul Rekap TPP versi 0.2 telah ditanam sebagai halaman aplikasi, termasuk:

- impor PDF finger scan berbasis teks;
- deteksi otomatis periode, tanggal, pegawai, dan jam;
- potongan terlambat, pulang cepat, finger tidak lengkap, dan tidak masuk;
- perbaikan kasus masuk 08.31 + finger pulang kosong menjadi 1,25% + 1,55%;
- kode TL, I, S, WFH, dan W;
- WFH/W dianggap hadir dan tidak dikenakan potongan;
- jabatan otomatis dari daftar referensi 29 PNS Sekretariat DPRD, dengan
  penyimpanan koreksi manual berdasarkan ID finger;
- ekspor Excel per pegawai; dan
- deteksi serta pencetakan ke printer Windows.

## Persuratan SIPS yang telah dimigrasikan

Form dan generator SIPS telah tersambung langsung ke UI PySide6. Tombol pada
menu Perjalanan Dinas dan Surat Undangan bukan lagi placeholder. Kemampuannya:

- Perjalanan Dinas DPRD dan Sekretariat DPRD pada form terpisah.
- Form perjalanan responsif tanpa scroll horizontal, dengan daftar tujuan yang
  dapat menampilkan empat sampai lima tujuan sekaligus.
- Validasi duplikasi hanya memeriksa nomor/materi yang benar-benar diisi;
  kolom kosong dan placeholder `-` tidak dimasukkan ke indeks duplikasi.
- Filter kategori DPRD berbentuk chip yang dapat dipilih beberapa sekaligus;
  daftar nama hanya menampilkan kategori aktif, disertai pencarian dan pilihan
  beberapa nama dari master resmi lokal (100 baris anggota DPRD dan 27 ASN).
- Surat Tugas DPRD/ASN dengan pilihan template biasa atau tabel secara
  otomatis sesuai jumlah pelaksana.
- Surat Pemberitahuan, SPD halaman depan dan belakang, serta Daftar Hadir.
- Beberapa tujuan perjalanan, deteksi nama kabupaten/kota dari nama instansi,
  zona waktu WIB/WITA/WIT per tujuan, serta transportasi otomatis.
- Surat Pemberitahuan menentukan pelaksana dari kategori DPRD yang benar-benar
  dipilih, melengkapi jabatan penerima (Ketua/Kepala/Sekretaris), dan memulai
  nomor daftar pelaksana dari 1 pada setiap halaman.
- SPD menuliskan seluruh tujuan pada maksud perjalanan dan hanya nama wilayah
  administratif pada kolom tempat tujuan.
- Undangan Paripurna delapan tujuan sesuai template resmi, hingga tujuh
  skenario rapat, serta penomoran halaman otomatis.
- Undangan Biasa dengan pelaksana/jenis rapat, jumlah Pihak Terkait tanpa batas,
  dan halaman tambahan tujuan surat.
- Pembuatan opsional Naskah Dinas dan Daftar Hadir rapat, termasuk lembar Pihak
  Terkait, Sekretariat, dan Tenaga Ahli Fraksi.
- Naskah Dinas dan Daftar Hadir juga dapat dibuat secara mandiri, sama seperti
  tombol dokumen pendukung pada SIPS lama.
- Validasi final mengikuti cabang dokumen yang benar-benar dipilih: DPRD,
  pendamping ASN, pelaksana Setwan, dan/atau pendamping Setwan.
- Jika satu jenis dokumen gagal, file lain yang berhasil tetap dipertahankan dan
  aplikasi menampilkan rincian cabang yang gagal.
- Autocomplete tujuan perjalanan dan peringatan materi perjalanan yang pernah
  dibuat sebelumnya.
- Simpan draft, muat/edit formulir dari rekap, pencarian/filter status, dan
  validasi nomor surat ganda tanpa membedakan huruf besar-kecil.
- Ekspor rekap perjalanan dinas dan surat undangan ke `.xlsx`.
- Deteksi printer Windows, buka dokumen/folder hasil, dan kirim dokumen langsung
  ke printer terpilih.
- Layout tiga panel khusus Persuratan SIPS: Sidebar, formulir utama, dan Live
  Preview di sisi paling kanan.
- Live Preview diperbarui otomatis tanpa tombol Pratinjau, dengan debounce agar
  dokumen tidak dibuat ulang pada setiap karakter yang sedang diketik.
- Pemilih hasil dokumen, preview multipage, navigasi halaman, zoom, dan tombol
  membuka DOCX di Word. Konversi lokal menggunakan Microsoft Word atau
  LibreOffice.
- Statistik perjalanan, undangan, dan draft pada Dashboard.

Seluruh 21 template Word dan master personel telah menjadi resource paket
`sekretariat_app.sips`; aplikasi tidak lagi bergantung pada proses atau UI
CustomTkinter lama. Source SIPS lama tetap disertakan di `legacy/sips_app`
sebagai arsip pembanding template.

Matriks audit fungsi lama dan penggantinya tersedia di
`docs/SIPS_ENGINE_PARITY.md`.

## Menjalankan melalui VS Code di Windows

Prasyarat: Windows 10/11 64-bit, Python 3.11 atau lebih baru, dan VS Code.

1. Ekstrak ZIP source.
2. Buka folder hasil ekstrak di VS Code melalui **File > Open Folder**.
3. Jalankan `setup_windows.bat` satu kali. Script ini membuat `.venv` secara
   otomatis menggunakan Python 3.11+ yang terpasang (termasuk Python 3.14) dan
   memasang seluruh dependency.
4. Setelah selesai, jalankan `run_app.bat` atau tekan `F5` dan pilih
   **Jalankan SIPS Terpadu**.

Pada pemasangan baru, aplikasi membuat akun `admin` dengan kata sandi acak.
Kredensial awal disimpan sementara di file `KREDENSIAL_ADMIN_AWAL.txt` pada
folder data aplikasi dan ditampilkan lokasinya di halaman login. File tersebut
dihapus otomatis setelah login pertama berhasil. Segera ubah kata sandi melalui
menu **Kelola User**. Kata sandi disimpan sebagai hash PBKDF2 dengan salt unik
di database SQLite lokal.

Jika ingin menjalankan manual melalui PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m sekretariat_app.main
```

## Menjalankan pengujian

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Membuat executable Windows

Jalankan:

```powershell
.\build_windows.bat
```

Hasil build:

```text
dist\SekretariatDPRDBitung\SekretariatDPRDBitung.exe
```

Mode folder (`onedir`) digunakan karena waktu startup lebih cepat dan lebih
stabil untuk PySide6, QtPrintSupport, template Word, serta library PDF.

Microsoft Word direkomendasikan pada komputer Windows untuk pratinjau dan cetak
langsung dokumen `.docx`. Pembuatan dokumen Word tetap bekerja tanpa internet.

## Struktur penting

```text
SekretariatDPRD/
├── src/
│   ├── sekretariat_app/
│   │   ├── documentation/    # model, canvas, migrasi proyek, export/cetak
│   │   ├── sips/             # model, SQLite, generator dan template persuratan
│   │   ├── ui/               # login, shell, dashboard, seluruh halaman
│   │   ├── resources/        # tema dan icon aplikasi
│   │   ├── auth.py           # akun lokal dan audit login
│   │   ├── config.py
│   │   └── main.py
│   └── tpp_finger_scan/      # domain dan UI Rekap TPP
├── legacy/sips_app/          # source dan template SIPS asli
├── tests/
├── setup_windows.bat
├── run_app.bat
└── build_windows.bat
```
