# Changelog

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
