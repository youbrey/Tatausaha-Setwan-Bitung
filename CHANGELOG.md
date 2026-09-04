# Changelog

## 0.11.0 — 2026-09-04

- Menambahkan delapan pegangan sisi dan sudut pada setiap frame foto agar lebar
  dan tinggi dapat diubah langsung seperti elemen pada Canva.
- Menambahkan ukuran frame presisi dalam milimeter serta pilihan untuk menjaga
  rasio saat ukuran diubah dari panel properti.
- Menambahkan mode khusus untuk memindahkan dan menskalakan seluruh kolase
  sebagai satu kesatuan, termasuk resize proporsional dengan tombol Shift.
- Memindahkan crop ke kanvas utama: area di luar frame diredupkan, gambar asli
  terlihat melewati frame, dan garis bantu sepertiga ditampilkan.
- Menambahkan drag posisi, wheel/slider zoom, rotasi, reset, batal, dan terapkan
  pada toolbar crop tanpa membuka dialog terpisah.
- Menjaga overlay editor agar tidak ikut masuk ke PDF, DOCX, atau hasil cetak.

## 0.10.0 — 2026-09-03

- Mengubah Live Preview SIPS menjadi lazy render: hanya dokumen yang sedang
  dipilih yang dibuat, bukan seluruh paket surat pada setiap perubahan form.
- Menambahkan sidik jari state untuk mencegah render duplikat dan pembatalan
  kooperatif agar request lama tidak meneruskan konversi PDF setelah usang.
- Mempertahankan pilihan jenis dokumen ketika nama file berubah serta membuka
  kembali PDF cache tanpa regenerasi saat halaman menu ditampilkan lagi.
- Menghapus tahap encode/decode PNG pada raster PDF, membatasi alokasi bitmap
  preview, dan merender ulang ukuran tampilan melalui debounce saat panel diubah.
- Mendecode foto sesuai kebutuhan resolusi kanvas/ekspor, menyimpan hasil
  rotasi, menggunakan thumbnail kecil, dan melepas bitmap setelah setiap
  halaman selesai diekspor.
- Merender PDF dan printer langsung dari scene dokumen tanpa membuat bitmap
  penuh per halaman, sehingga penggunaan RAM tetap stabil pada dokumen panjang.
- Mengurangi repaint kanvas Dokumentasi Foto, menyatukan request autosave dan
  preview kolase yang beruntun, serta membatasi riwayat undo menjadi 30 state.

## 0.9.0 — 2026-09-03

- Mengganti input tujuan surat lainnya pada Undangan Biasa menjadi editor
  dinamis per halaman; pengguna dapat menambah/menghapus tujuan dan halaman
  tanpa batas serta draft lama tetap dapat dimuat.
- Menyamakan penomoran setiap halaman Undangan Biasa dengan Undangan
  Paripurna: segmen ketiga nomor bertambah secara berurutan, termasuk seluruh
  halaman tujuan tambahan.
- Mengubah nama jenis rapat menjadi `Rapat Dengar Pendapat Umum (RDPU)` dan
  menormalisasi nilai lama ketika draft dibuka kembali.

## 0.8.0 — 2026-09-02

- Mengabaikan kolom kosong dan placeholder garis (`-`, en dash, em dash) pada
  validasi duplikasi nomor serta materi perjalanan.
- Membersihkan indeks nomor lama yang hanya berisi placeholder garis.
- Membuat form Perjalanan Dinas responsif tanpa scroll horizontal dan
  memperbesar daftar tujuan agar empat sampai lima tujuan terlihat sekaligus.
- Memisahkan batas kertas dari area kerja kanvas agar ukuran dan rasio A4/F4/
  Letter/Legal terlihat jelas melalui border serta bayangan halaman.
- Menambahkan Studio Auto Kolase dengan preview foto nyata, kartu mini-preview
  setiap template, dan estimasi jumlah halaman sebelum diterapkan.
- Menambahkan kontrol lebar, tinggi, serta jarak seluruh kumpulan foto dengan
  satuan persen dan milimeter.
- Mengganti crop berbasis slider menjadi crop interaktif bergaya Canva: frame
  tetap, drag posisi foto, wheel zoom, rotasi, reset, dan slider sinkron.
- Menjaga posisi relatif elemen ketika ukuran atau orientasi kertas berubah.

## 0.6.0 — 2026-08-31

- Menyelesaikan audit paritas engine surat terhadap source SIPS lama.
- Menambahkan validasi final per jenis peserta dan memisahkan validasi ringan
  untuk Live Preview.
- Mengembalikan hasil batch parsial beserta rincian kegagalan per dokumen.
- Mengembalikan pembuatan mandiri Naskah Dinas dan Daftar Hadir rapat.
- Memulihkan autocomplete tujuan, peringatan materi duplikat, dan perilaku input
  nama pelaksana rapat custom.
- Memperbaiki daftar hadir mode DPRD agar hanya berisi anggota DPRD, serta
  penamaan file Undangan Paripurna berdasarkan tanggal surat seperti SIPS lama.
- Menambah regression test cabang generator dan pemeriksaan placeholder DOCX.
- Mengganti kata sandi admin bawaan dengan kredensial acak per instalasi yang
  disimpan sementara dan dihapus setelah login pertama.

## 0.5.0 — 2026-08-31

- Menambahkan layout khusus tiga panel pada Perjalanan Dinas dan Surat
  Undangan: Sidebar, halaman formulir utama, dan Live Preview di sisi kanan.
- Mengganti tombol Pratinjau manual dengan preview otomatis setelah perubahan
  form berhenti selama 900 milidetik.
- Menjalankan pembuatan DOCX dan konversi PDF pada thread terpisah agar UI tetap
  responsif.
- Menambahkan pemilih dokumen untuk hasil perjalanan dinas/undangan yang
  menghasilkan beberapa file, navigasi halaman, zoom, dan buka DOCX di Word.
- Menunda proses preview pada halaman yang sedang tidak aktif dan mengabaikan
  hasil proses lama ketika pengguna kembali mengubah form.
- Menampilkan validasi kelengkapan formulir langsung di panel preview.

## 0.4.0 — 2026-08-28

- Memigrasikan generator SIPS dari controller CustomTkinter ke service Python
  yang digunakan langsung oleh form PySide6.
- Mengaktifkan Perjalanan Dinas DPRD dan Sekretariat DPRD: Surat Tugas,
  Pemberitahuan, SPD depan/belakang, serta Daftar Hadir.
- Mengaktifkan Undangan Paripurna dan Undangan Biasa, termasuk halaman tujuan
  tambahan, Pihak Terkait, Naskah Dinas, dan Daftar Hadir rapat.
- Memaketkan 21 template Word serta master 100 anggota DPRD dan 27 ASN ke dalam
  aplikasi.
- Menambahkan draft/revisi, rekap berbasis SQLite, pencarian, filter status,
  validasi nomor surat ganda, dan ekspor rekap `.xlsx`.
- Menambahkan pratinjau DOCX multipage, buka file/folder hasil, deteksi printer,
  dan cetak langsung ke printer Windows.
- Menghubungkan statistik Dashboard ke data SIPS aktual.
- Menghapus halaman placeholder migrasi SIPS lama.
- Menambahkan pengujian integritas template/generator dan repository SIPS.

## 0.3.0

- Menambahkan shell aplikasi terpadu PySide6 dengan dashboard dan sidebar final.
- Menempatkan menu Dokumentasi Foto tepat setelah Rekapitulasi TPP.
- Memigrasikan workspace inti DokuFoto-React menjadi canvas Qt asli.
- Menambahkan 11 template, kisi kustom, kolase otomatis, crop, teks, kop surat,
  multipage, autosave, proyek JSON/ZIP, ekspor DOCX/PDF, dan cetak.
- Menambahkan kompatibilitas impor proyek DokuFoto-React.
- Menanam modul Rekap TPP dan menambahkan aturan WFH/W tanpa potongan.
- Menambahkan referensi lokal 29 PNS dan pengisian jabatan otomatis saat PDF
  finger scan diimpor.
- Menambahkan autentikasi serta Kelola User berbasis SQLite/PBKDF2.

## 0.2.0 — 2026-08-28

### Perbaikan kritis

- Potongan keterlambatan tetap dihitung ketika finger pulang tidak ada.
- Potongan pulang cepat tetap dihitung ketika finger masuk tidak ada.
- Kolom Tidak Masuk hanya terisi 3% ketika finger masuk dan pulang sama-sama
  tidak ada.
- Menghapus status review lama yang menyatakan kombinasi potongan belum disahkan.

### Ekspor dan UI

- Menambahkan sheet `Rekap Per Pegawai` sesuai format 11 kolom pada lampiran.
- Setiap pegawai dipisahkan dengan page break dan disiapkan untuk A4 landscape.
- Menambahkan formula jumlah harian dan jumlah periode.
- Menambahkan sheet `Master Pegawai` dan tombol `Isi Jabatan`.
- Menambahkan tombol `Atur Hari Libur`; akhir pekan dan hari libur tidak muncul
  pada rekap cetak.
- Menyesuaikan periode cetak bagian dalam dokumen sumber (26–25 menjadi 27–24).
- `setup_windows.bat` memilih Python 3.11 atau lebih baru, termasuk Python 3.14.

### Pengujian

- Menambahkan regression test kasus 08.31 masuk dan finger pulang kosong.
- Menambahkan pengujian kombinasi finger masuk kosong dan pulang cepat.
- Menambahkan pengujian bahwa Tidak Masuk hanya berlaku untuk dua finger kosong.
- Menambahkan pengujian struktur dan formula rekap per pegawai.
