# SIPS Terpadu — Sekretariat DPRD Kota Bitung

Aplikasi desktop Windows berbasis Python dan PySide6 yang menyatukan navigasi
SIPS, Rekapitulasi TPP, Dokumentasi Foto, Edit PDF, serta Persediaan Barang dalam satu shell modern. Semua
data utama diproses dan disimpan secara lokal; aplikasi tidak mengunggah
dokumen, foto, atau data pegawai ke internet.

Versi source saat ini: **0.16.3 — format surat Pendamping ASN sesuai master, termasuk Surat Izin baru dan live preview**.

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
8. Edit PDF
9. Persediaan Barang
10. Kelola User
11. Logout

Menu **Dokumentasi Foto** berada tepat setelah **Rekapitulasi TPP**. Seluruh
workspace tampil pada halaman utama di samping sidebar, bukan pada jendela atau
browser terpisah.

## Persediaan Barang

Menu **Persediaan Barang** memakai database SQLite aplikasi yang sama melalui
tabel khusus berawalan `inventory_`. Fitur yang tersedia:

- dashboard saldo, nilai persediaan, barang aktif, stok rendah, dan jumlah
  surat pengeluaran;
- referensi barang lengkap dengan kode, satuan, kategori, spesifikasi, nomor
  kartu, harga standar, serta status aktif;
- transaksi barang masuk dengan tanggal buku, nomor bukti, jenis transaksi,
  harga satuan, uraian, dan keterangan;
- transaksi barang keluar multi-item dalam satu Surat Perintah dengan metode
  FIFO dan validasi stok atomik;
- ComboBox bagian tujuan: Bagian Umum dan Keuangan, Bagian Perundang-Undangan
  Persidangan dan Humas, serta Bagian Fasilitasi Penganggaran dan Pengawasan;
- PDF **Surat Perintah Pengeluaran/Penyaluran Barang**, **Kartu Persediaan
  Barang**, dan **Laporan Mutasi Barang**;
- laporan/ekspor `.xlsx` Rekapan Barang Keluar per bagian dan rentang tanggal;
- deteksi printer Windows, cetak langsung, serta pengaturan kop, logo,
  penandatangan, margin, font tabel, dan jumlah baris kosong.

Lihat [rancangan dan aturan modul Persediaan Barang](docs/PERSEDIAAN_BARANG.md).

## Surat Pendamping ASN versi 0.16.3

- Surat Tugas Pendamping memakai susunan identitas tanpa penomoran, redaksi
  rombongan DPRD lengkap, serta pangkat dan NIP penandatangan dari master ASN.
- SPD Pendamping menampilkan nama beserta NIP dan memakai maksud perjalanan
  lengkap yang diawali `Mendampingi`, tanpa kembali ke redaksi generik.
- Dokumen **Surat Izin Pendamping ASN** dibuat otomatis untuk setiap pendamping,
  memiliki nomor tersendiri, dan tersedia sebagai pilihan Live Preview.
- Template Surat Izin memakai kop Sekretariat DPRD yang stabil pada Word dan
  LibreOffice, dengan penerima, isi, identitas, dan blok tanda tangan sesuai
  dokumen hasil seharusnya.

## Penyempurnaan surat Perjalanan Dinas versi 0.16.2

- Materi kegiatan dibentuk satu kali dari kedua kolom form, lalu dipakai
  konsisten oleh Surat Tugas, Surat Pemberitahuan, Daftar Hadir, dan SPD.
- Surat Pemberitahuan dan Daftar Hadir tidak lagi berhenti pada nama tempat;
  frasa `dalam rangka` beserta materi sesudahnya selalu dipertahankan.
- Kolom Maksud Perjalanan Dinas pada SPD tidak lagi berhenti pada frasa
  `dalam rangka` ketika pola input form berbeda atau salah satu kolom hanya
  berisi rute.
- Input materi pendek dan kalimat perjalanan lengkap sama-sama didukung,
  termasuk fallback aman dari kolom Surat Pemberitahuan ke kolom Surat
  Tugas/SPD dan sebaliknya.

## Penyempurnaan format surat Perjalanan Dinas versi 0.16.1

- Surat Tugas tabel memakai kembali proporsi kolom dan tinggi baris master
  yang benar.
- Surat Pemberitahuan multi-tujuan menyebut hanya tujuan pada halaman aktif,
  tanpa mengulang seluruh rute atau menghasilkan teks `DPRD DPRD`.
- SPD depan selalu satu halaman per pelaksana untuk struktur contoh lima
  pelaksana, dengan kapitalisasi tujuan formal, tiga slot pengikut, dan kolom
  yang tidak mendorong tanda tangan ke halaman berikutnya.
- Daftar Hadir selalu dua halaman per tujuan: lembar keberangkatan berisi
  peserta dan lembar tempat tugas tetap kosong untuk tanda tangan manual.
- Materi kegiatan dipisahkan dari jenis/rute perjalanan sebelum ditempatkan
  pada SPD dan Daftar Hadir, sehingga tujuan tidak tercetak dua kali.

## Edit PDF dan optimasi versi 0.16.0

Menu **Edit PDF** berada setelah Dokumentasi Foto. Tersedia merge/split,
pengurutan/duplikasi/penghapusan/rotasi halaman, sisip halaman kosong, tambah
atau ganti blok teks, sisip gambar, proteksi AES-256, serta konversi
PDF ↔ Word, PDF ↔ Excel, dan gambar ↔ PDF. Sumber tidak ditimpa; perubahan
disimpan sebagai salinan. Lihat [panduan dan batas fitur](docs/EDIT_PDF.md).

**Batas kemampuan:** editor teks belum setara seluruh Adobe Acrobat; reflow
paragraf kompleks dan pemeliharaan semua font khusus belum tersedia.
PDF → Word editable mengekstrak teks, PDF → Excel mengekstrak tabel.
Word/Excel → PDF memerlukan Microsoft Office atau LibreOffice lokal.
Unprotect memerlukan password pemilik yang benar.

Rekap TPP dapat membaca PDF teks maupun PDF hasil scan memakai OCR lokal
PyMuPDF/Tesseract. Untuk PDF CamScanner/image-only, aplikasi merekonstruksi
garis tabel dan kolom tanggal, lalu membaca identitas serta sel kehadiran
per-area. Kode tulisan tangan `W`/`TL` dibaca dengan mode goresan terpisah dan
konsensus terbatas pada sel bertinta besar tanpa angka di kolom tanggal yang
sama; nilai waktu tidak ditebak menjadi kode. Agar OCR scan tersedia pada executable, instal Tesseract OCR
dengan data bahasa Inggris (`eng.traineddata`) sebelum menjalankan
`build_windows.bat`. Script build akan menemukan data pada instalasi standar
Windows dan menyertakannya ke folder hasil build. OCR tetap bekerja 100% lokal
tanpa mengunggah dokumen.

Perubahan untuk mengurangi beban:

- Halaman dan impor modul berat dibuat saat menu pertama kali dibuka.
- Pekerjaan Edit PDF berjalan satu per satu pada proses terpisah; hasil preview
  maksimal 2 megapiksel dan hanya halaman aktif yang dirender.
- Cache preview surat menghindari render ulang pada halaman/skala yang sama;
  penyalinan buffer gambar berulang dikurangi.
- Thumbnail Media dimuat bertahap hanya di sekitar area yang terlihat, dengan
  cache maksimal 96 gambar; cache foto dilepas saat menu disembunyikan.
- Resolusi foto untuk layar dibatasi terpisah dari ekspor/cetak, debounce kop
  surat memakai satu timer, dan history foto dibatasi jumlah serta ukurannya.
- Logout menutup workspace dan membersihkan resource halaman yang telah dibuka.

Regresi otomatis mencakup worker Edit PDF, operasi halaman/edit/konversi,
rekonstruksi tabel scan, aturan TPP, ekspor, dan migrasi SIPS. Contoh PDF
CamScanner juga diuji langsung; verifikasi visual final pada build Windows tetap
disarankan karena lingkungan pengujian source bukan Windows.

## Kemampuan Dokumentasi Foto

- Canvas WYSIWYG asli Qt berbasis `QGraphicsScene`/`QGraphicsView`.
- Ukuran kertas A4, F4, Letter, Legal, serta ukuran kustom.
- Orientasi portrait/landscape dan pengaturan empat sisi margin.
- Sebelas template kolase 1, 2, 3, 4, 5, 6, dan 8 foto.
- Kisi kustom sampai 6 × 6.
- Studio auto-kolase dengan preview foto nyata sebelum diterapkan.
- Mini-preview visual untuk setiap gaya kisi, bukan daftar nama berbentuk teks.
- Pengaturan lebar/tinggi seluruh kumpulan foto dan jarak antar-foto dalam mm.
- Kolase otomatis dari foto yang dipilih di panel Media menjadi beberapa halaman.
- Impor satu atau banyak foto, impor folder, dan drag-and-drop dari Explorer.
- Media tray lokal dengan thumbnail.
- Seleksi media fleksibel dengan drag kotak, Ctrl+klik, dan Ctrl+A; auto-kolase
  hanya memproses foto yang sedang dipilih, sedangkan foto lain tetap tersimpan.
- Resize setiap frame melalui delapan pegangan sisi/sudut atau ukuran presisi
  lebar dan tinggi dalam mm, dengan opsi mempertahankan rasio.
- Seleksi dua atau lebih foto otomatis berubah menjadi satu bingkai kolase;
  pemindahan dan resize bingkai berlaku pada seluruh foto serta mempertahankan
  posisi dan jarak relatifnya. Tahan Shift untuk mempertahankan rasio kolase.
- Lembar kertas putih, rasio ukuran A4/F4/Letter/Legal, margin, dan area kolase
  ditampilkan nyata di kanvas sesuai dengan pratinjau dan hasil ekspor.
- Crop langsung bergaya Canva: area luar frame diredupkan, garis bantu sepertiga
  ditampilkan, foto dapat diseret, di-zoom dengan roda/slider, dirotasi, direset,
  dibatalkan, atau diterapkan tanpa membuka dialog terpisah.
- Border, warna border, sudut bulat, serta keterangan foto.
- Teks bebas yang dapat dipindah, diedit langsung, dirotasi, dan dikunci.
- Resize teks langsung di kanvas: pegangan sudut mengubah ukuran huruf dan frame
  secara proporsional, sementara pegangan kiri/kanan mengatur lebar teks.
- Font, ukuran, lebar kotak, bold, italic, underline, alignment, jarak huruf,
  tinggi baris, warna, background, opacity, shadow, dan glow.
- Kop surat opsional pada halaman pertama, dua logo, informasi instansi, alamat,
  kontak, dan pilihan garis kop.
- Tambah, duplikat, pindah, dan hapus halaman.
- Undo/redo berbasis snapshot serta autosave lokal.
- Simpan/muat `.dokufoto.json` dan ekspor/impor arsip `.zip` beserta foto.
- Deteksi printer Windows langsung pada toolbar, pilihan printer aktif, dan
  pencetakan native tanpa membuka Word. Canvas dirender ke ukuran kertas fisik
  penuh tanpa diperkecil ke area cetak driver.
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
- Simpan draft dan tombol **Muat Draft** langsung pada form Perjalanan Dinas,
  muat/edit formulir dari rekap, pencarian/filter status, dan
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
│   │   ├── inventory/        # SQLite FIFO dan laporan persediaan
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
