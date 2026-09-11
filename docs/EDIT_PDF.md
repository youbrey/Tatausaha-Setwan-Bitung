# Edit PDF — versi 0.16.0

Workspace desktop offline di sidebar setelah Dokumentasi Foto. Tidak ada
layanan konversi internet. Instalasi dependency saat setup dilakukan sebelum
aplikasi digunakan offline.

## Kemampuan dan batasnya

| Fitur | Cara kerja |
| --- | --- |
| Merge | Pilih beberapa PDF, tentukan urutan nomor file; PDF aktif ditempatkan pertama. Hasil menjadi salinan kerja yang dapat disimpan. Bookmark antarfile tidak digabungkan. |
| Split | Kosongkan kelompok untuk satu file per halaman, atau tulis `1-3;4-6;7`. Setiap kelompok menjadi PDF tersendiri di folder hasil baru. |
| Organize | Urutan eksplisit seperti `3,1-2,2` memindahkan sekaligus menduplikasi halaman. Halaman yang tidak disebut dikeluarkan. Hapus/putar memakai rentang halaman; kosong berarti halaman aktif. |
| Halaman kosong | Sisipkan setelah halaman aktif dengan ukuran halaman yang sama. |
| Ganti teks | Pilih blok pada kertas, ubah teks, ukuran, font standar, warna, tebal/miring, lalu Terapkan. Teks lama dihapus, bukan ditutup kotak putih. Kosongkan isinya untuk menghapus blok. |
| Tambah teks | Pilih mode Tambah teks, tarik kotak pada kertas, isi teks dan format, lalu Terapkan. |
| Sisip gambar | Pilih gambar, tarik kotak, lalu Terapkan. Rasio gambar dan transparansi dipertahankan. |
| PDF → Word editable | DOCX berisi teks menurut urutan blok dan pemisah halaman. Gambar, tabel, kolom, semua gaya/font, dan tata letak kompleks tidak direkonstruksi identik. |
| PDF → Word tampilan | Setiap halaman dijadikan gambar dengan ukuran halaman asal. Posisi visual dipertahankan, teks di Word tidak editable; kualitas raster dibatasi untuk menghemat memori. |
| Word → PDF | Dokumen `.doc`/`.docx` dirender Microsoft Word lokal atau LibreOffice. |
| PDF → Excel | Tabel PDF berbasis teks diekstrak ke worksheet `.xlsx` per tabel. Sel ditulis sebagai teks, bukan rumus. PDF scan tidak diproses dengan OCR. |
| Excel → PDF | Workbook `.xls`/`.xlsx` dirender Microsoft Excel lokal atau LibreOffice, mengikuti pengaturan area cetak workbook. |
| Gambar → PDF | Gambar terpilih diurutkan menurut nama, satu gambar per halaman A4 portrait dengan margin 10 mm. |
| PDF → gambar | Ekspor PNG 72–300 DPI, rentang di tab Halaman atau seluruh halaman bila kosong. |
| Protect | Salinan AES-256 dengan password buka dan password pemilik berbeda; pilihan izin cetak/salin. Simpan kedua password sendiri. |
| Unprotect | Buka PDF memakai password pemilik yang benar, lalu Simpan tanpa proteksi. Tidak ada pemulihan atau pembobolan password. |

Pengeditan teks **belum setara seluruh Adobe Acrobat**. Blok memakai font
standar pengganti; gaya campuran dalam satu blok menjadi satu gaya. Belum ada
OCR, pemindahan/reflow paragraf lintas halaman, penambahan font khusus,
penyuntingan form interaktif, atau pengelolaan tanda tangan digital.
Teks miring/bertumpuk dengan blok lain ditolak agar teks sekitarnya tidak
terhapus. Jika teks pengganti tidak muat, operasi dibatalkan tanpa menyimpan
perubahan. Kurangi ukuran huruf atau gunakan Tambah teks pada area yang cukup.
Mengedit lapisan OCR tidak mengubah tulisan yang sudah menjadi bagian gambar.

## Alur penggunaan

1. Buka menu **Edit PDF → Buka PDF**. Untuk PDF terlindungi, masukkan password
   pemilik. Aplikasi membuat salinan kerja tanpa menimpa file sumber.
2. Gunakan tab **Halaman**, **Edit**, **Konversi**, atau **Kunci** di kanan.
   Pilihan halaman untuk rotate/delete/split memakai nomor mulai dari 1.
3. Gunakan **Urungkan/Ulangi** untuk perubahan salinan kerja. History disimpan
   di disk, maksimal delapan revisi dan sekitar 300 MB; satu revisi besar tetap
   dipertahankan. Revisi lama dapat dikeluarkan saat batas tercapai.
4. **Simpan Salinan** menghasilkan PDF. Protect/unprotect menghasilkan salinan
   PDF tersendiri. Konversi dan split tidak mengubah PDF yang sedang dibuka.
5. Tunggu pekerjaan selesai sebelum keluar. Batalkan meminta penghentian pada
   batas operasi berikutnya; konversi Office yang sedang aktif dapat perlu
   waktu sampai selesai/timeout. Hasil parsial tidak diterbitkan.

Perubahan yang belum disimpan tetap ada saat berpindah menu dalam satu sesi.
Tidak ada pemulihan salinan kerja PDF setelah aplikasi berhenti mendadak;
simpan salinan secara berkala. Nama file sumber tidak boleh dipakai sebagai
target Simpan Salinan. Hasil baru ditulis ke file sementara di folder tujuan,
kemudian dipindahkan setelah proses berhasil.

## Resource dan arsitektur

- Shell hanya membangun Dashboard saat login; modul lain dimuat saat diperlukan.
- `PDFJobs` memakai `QProcess`, satu pekerjaan aktif per workspace. Worker
  menerima request JSON lokal, menghapus request setelah dibaca, dan menulis
  hasil/status ke file lokal agar juga bekerja pada executable `--windowed`.
  Output proses dibaca langsung melalui kanal Qt—tidak dialihkan ke perangkat
  `nul`—agar worker dapat dimulai dengan konsisten pada build Windows.
- Worker mengimpor PyMuPDF dan library konversi sesuai kebutuhan. Proses keluar
  setelah pekerjaan selesai untuk melepaskan alokasi native. Di Windows,
  prioritas worker dibuat lebih rendah dari UI.
- Preview hanya menyimpan raster halaman aktif maksimal 2 megapiksel.
  Zoom layar memakai raster ini; tidak mengubah resolusi dokumen sumber.
  Berpindah menu melepaskan raster. Tombol Muat ulang preview dapat dipakai
  setelah pembatalan atau kegagalan render.
- Tidak ada dokumen penuh atau semua raster halaman di cache RAM untuk undo.
  Ekstraksi Excel memakai worksheet streaming. DOCX tetap memerlukan objek
  dokumen di RAM; gambar tertanam dibatasi 96 MB, teks dua juta karakter.
  Pecah PDF terlebih dahulu jika batas tersebut tercapai. Ekspor PNG dibatasi
  40 megapiksel per halaman.
- Gambar yang disisipkan dibatasi sisi 4096 piksel; gambar ke PDF A4 memakai
  maksimum 2560 × 3508 piksel dengan rasio asal. Foto sumber tidak diubah.
- Render/konversi kompleks masih menggunakan CPU dan RAM selama proses aktif.
  Operasi lama di modul lain tidak seluruhnya dipindahkan ke proses ini.
  Belum ada benchmark penggunaan resource pada Windows.

PyMuPDF dijalankan di proses terpisah, mengikuti batas penggunaan library:
[dokumentasi multiprocessing PyMuPDF](https://pymupdf.readthedocs.io/en/latest/recipes-multiprocessing.html).
Penggantian teks memakai operasi redaksi teks dan penyisipan HTML terbatas:
[API halaman PyMuPDF](https://pymupdf.readthedocs.io/en/latest/page.html).

## Memperbarui instalasi Windows

Tutup aplikasi, perbarui source dari repository atau ekstrak ZIP terbaru ke
folder baru. Folder unduhan ZIP tidak mempunyai metadata Git, sehingga
`git pull` hanya berlaku untuk folder hasil `git clone`.

Jalankan perintah berikut **satu per satu** di terminal VS Code, pada folder
project yang berisi `pyproject.toml`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\run_app.bat
```

Jika menggunakan executable, bangun ulang dengan `build_windows.bat` dan
salin seluruh folder `dist\SekretariatDPRDBitung`, bukan hanya `.exe`.
Konversi Word/Excel tetap memerlukan Office atau LibreOffice lokal pada PC
tujuan. Tidak diperlukan Node.js, server web, atau API konversi.

Worker dan operasi inti Edit PDF telah diuji dari source. Konversi Office tetap
bergantung pada instalasi Microsoft Office/LibreOffice, dan tampilan akhir perlu
diverifikasi kembali pada build Windows target.
