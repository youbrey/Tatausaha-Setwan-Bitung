# Audit dan Refactor DokuFoto React

Tanggal audit awal: 26 Agustus 2026

Audit cetak dan DOCX: 27 Agustus 2026

## Temuan yang diperbaiki

| Prioritas | Temuan | Dampak | Perbaikan |
|---|---|---|---|
| Kritis | Foto Base64 disimpan di `localStorage` dan kegagalan kuota diabaikan | Autosave berhenti tanpa diketahui pengguna | Pindah ke IndexedDB, tambah debounce dan notifikasi kegagalan |
| Tinggi | Google Fonts, Unsplash, dan Tailwind CDN dipakai saat runtime/cetak | Aplikasi tidak benar-benar offline; hasil cetak berubah saat internet putus | Hapus seluruh dependensi runtime eksternal dan gunakan CSS/font lokal |
| Tinggi | Daftar printer adalah data contoh statis | Antarmuka memberi kesan printer benar-benar terdeteksi | Hapus daftar palsu; delegasikan pemilihan printer/copies ke dialog Windows |
| Tinggi | JSON proyek diterima tanpa validasi | Berkas rusak dapat membuat aplikasi crash | Tambah schema/version marker dan validasi struktur saat impor |
| Tinggi | ZIP dapat diekspor tetapi tidak dapat dimuat kembali | Cadangan tidak berfungsi sebagai pemulihan lengkap | Tambah impor ZIP dan rekonstruksi galeri media |
| Sedang | Crop hanya memperbarui `grids`, bukan `cells` kompatibilitas | Crop dapat hilang pada ekspor/perubahan template | Sinkronkan kedua representasi melalui satu helper |
| Sedang | “Kosongkan semua foto” hanya membersihkan `cells` | Foto pada grid aktif tetap tampil | Bersihkan `cells` dan seluruh `grids` |
| Sedang | FileReader tersebar, tanpa batas ukuran, dan batch upload tidak deterministik | File gagal dapat menggantung batch; penggunaan memori tak terkendali | Sentralisasi validasi/read, batas 30 MB, `Promise.allSettled` |
| Sedang | DOCX dan ZIP ikut masuk bundle awal | JavaScript awal terlalu besar | Gunakan dynamic import untuk modul ekspor |
| Sedang | Dependensi AI/server/UI tidak digunakan | Instalasi lebih berat dan membingungkan untuk mode offline | Hapus dependensi yang tidak dipakai |
| Rendah | Tes `.NET` merujuk project yang tidak ada | Folder tes tidak dapat dijalankan dan tidak relevan | Ganti dengan unit test TypeScript/Vitest |
| Rendah | Server dev bind ke `0.0.0.0` | Aplikasi lokal terekspos ke LAN tanpa sengaja | Default ke `127.0.0.1`; sediakan `dev:lan` eksplisit |
| Kritis | CSS cetak menyembunyikan seluruh `body`, tetapi ID yang seharusnya ditampilkan kembali tidak ikut disalin; halaman juga dibuat dalam iframe transparan di luar layar | Dialog printer menampilkan lembar putih meskipun pratinjau aplikasi berisi | Hapus aturan visibilitas lama; gunakan jendela cetak terlihat, tunggu gambar/font dan dua frame render, lalu panggil dialog Windows |
| Tinggi | Aturan `@page size` menggabungkan dua ukuran fisik dengan kata orientasi | Deklarasi CSS tidak valid dan ukuran dapat diabaikan browser | Gunakan pasangan ukuran fisik `width height` yang valid |
| Tinggi | Elemen teks bebas ditambahkan ke DOCX dua kali, sebelum dan sesudah tabel foto | Teks muncul di posisi atas dan bawah | Satu jalur ekspor teks, dengan tes yang membongkar `word/document.xml` dan menghitung kemunculan teks |
| Sedang | Halaman terakhir selalu memakai `break-after: page` | Browser dapat menambahkan lembar kosong di akhir | Nonaktifkan page break pada halaman terakhir |
| Sedang | Judul Dokumen Baku, Tabel Informasi, dan Blok Tanda Tangan tidak diperlukan | Antarmuka dan ekspor menjadi rumit serta memicu duplikasi judul | Hapus kontrol, renderer, model aktif, ekspor, dan bersihkan field lama saat proyek dimuat |
| Kritis | Kanvas, pratinjau cetak, dan DOCX memakai tiga renderer berbeda; DOCX membangun ulang kolase sebagai tabel Word 4:3 | Ukuran/crop/grid berubah, jarak membesar, dan posisi teks tidak sama dengan aplikasi | Jadikan satu renderer halaman sebagai sumber resmi; raster setiap halaman ke PNG 300 DPI untuk cetak dan DOCX |
| Tinggi | Pratinjau cetak memakai `clip-path`, sedangkan editor memakai posisi dan skala gambar berdasarkan `cropRect` | Foto yang sudah di-crop dapat menampilkan area berbeda pada hasil akhir | Satukan rumus crop, rotasi, tipografi, efek teks, margin, dan ukuran kertas dalam utilitas visual bersama |
| Tinggi | Ukuran kertas Custom tidak dipakai oleh kanvas editor | Kanvas Custom dan ukuran output dapat memiliki rasio berbeda | Gunakan satu perhitungan geometri dokumen untuk editor, pratinjau, raster, cetak, dan DOCX |

## Model data lokal

Proyek dan galeri foto disimpan sebagai satu `WorkspaceSnapshot` berversi. IndexedDB dipakai untuk autosave, sedangkan file JSON/ZIP menjadi cadangan portabel. Semua gambar pengguna disimpan sebagai Data URL lokal; URL gambar jaringan ditolak saat impor proyek.

## Batas platform

Web browser dapat membaca file yang dipilih pengguna dan menghasilkan download tanpa server. Browser tidak dapat mengakses daftar printer Windows secara langsung. Dialog `window.print()` adalah jalur yang aman dan didukung untuk mendeteksi serta memilih printer, ukuran, warna, dan jumlah salinan melalui Windows.

DOCX WYSIWYG sengaja berisi satu gambar halaman penuh per lembar, bukan tabel, paragraf, dan gambar Word terpisah. Pilihan ini mempertahankan tampilan akhir, tetapi elemen di dalam halaman tidak dapat diedit secara individual di Microsoft Word.
