# Persediaan Barang

Modul ini merupakan migrasi fungsi inti aplikasi Persediaan Java ke dalam
aplikasi desktop PySide6 Sekretariat DPRD Kota Bitung. Seluruh proses berjalan
lokal dan menyimpan data pada database SQLite aplikasi.

## Alur kerja

1. Periksa atau tambahkan data pada **Referensi Barang**.
2. Catat pengadaan atau saldo awal melalui **Persediaan Masuk**. Setiap catatan
   membentuk lapisan stok FIFO berdasarkan tanggal buku dan urutan penyimpanan.
3. Buat surat pada **Persediaan Keluar**, pilih salah satu bagian tujuan, lalu
   tambahkan satu atau beberapa barang ke daftar surat.
4. Saat surat disimpan, aplikasi memeriksa saldo seluruh barang terlebih dahulu.
   Jika satu barang tidak mencukupi, surat, detail, dan pengurangan saldo tidak
   disimpan. Jika valid, stok tertua dikonsumsi lebih dahulu.
5. Gunakan **Kategori Laporan** untuk Kartu Persediaan, Laporan Mutasi, atau
   Rekap Barang Keluar per bagian dan rentang tanggal.

## Bagian tujuan

- Bagian Umum dan Keuangan
- Bagian Perundang-Undangan Persidangan dan Humas
- Bagian Fasilitasi Penganggaran dan Pengawasan

Bagian bersifat wajib pada transaksi keluar. Nilai ini tampil pada Surat
Perintah, uraian Kartu Persediaan, dan Rekap Barang Keluar.

## Format dokumen

### Surat Perintah Pengeluaran/Penyaluran Barang

PDF A4 portrait memuat kop Sekretariat DPRD, nomor surat, Dari/Kepada/Alamat,
dasar permintaan, bagian tujuan, tabel No Urut/Banyaknya/Nama Barang/Harga
Satuan/Jumlah/Keterangan, serta dua blok penandatangan. Satu surat dapat memuat
banyak barang. Jumlah baris kosong dapat diatur.

### Kartu Persediaan Barang

PDF A4 portrait mengikuti format Lampiran 13. Header memuat SKPD, Kabupaten/Kota,
Provinsi, Gudang, Nama Barang, Satuan, harga standar, nomor kartu, dan
spesifikasi. Tabel bertingkat memuat jumlah dan nilai masuk, keluar, serta saldo
berjalan. Kartu dapat difilter berdasarkan tanggal.

### Laporan Mutasi Barang

PDF A4 portrait memuat kop, periode sampai tanggal pilihan, pengelompokan
kategori barang, saldo awal tahun, mutasi tambah/kurang, saldo akhir, harga
satuan, nilai rupiah, dan dua blok penandatangan.

### Rekap Barang Keluar per Bagian

Laporan dapat difilter untuk semua bagian atau satu bagian, serta tanggal awal
dan akhir. Kolomnya mencakup tanggal, nomor surat, kode dan nama barang, jumlah,
satuan, harga satuan FIFO, nilai, bagian, dan keterangan. Hasil dapat diekspor
ke PDF atau Excel.

## Format fleksibel

Tab **Pengaturan Dokumen** menyimpan perubahan tanpa mengubah source code:

- nama pemerintah dan perangkat daerah;
- alamat, situs web, kode pos, kota, provinsi, gudang, dan logo;
- judul ketiga dokumen;
- identitas dan NIP kedua penandatangan;
- nilai default Dari/Kepada/Alamat Surat Perintah;
- margin kiri/kanan, ukuran font tabel, ketebalan garis, dan baris kosong.

Pengaturan baru berlaku pada dokumen yang dibuat setelah disimpan. File PDF
lama tidak diubah.

## Database dan konsistensi

Tabel modul memakai awalan `inventory_` sehingga tidak bercampur dengan tabel
akun, SIPS, maupun Rekap TPP. Relasi utama:

- `inventory_items`: referensi barang;
- `inventory_receipts`: batch masuk dan sisa per batch;
- `inventory_issue_headers`: kepala Surat Perintah;
- `inventory_issues`: detail barang keluar;
- `inventory_fifo_consumptions`: hubungan detail keluar dengan batch masuk;
- `inventory_settings`: pengaturan format dokumen.

Tanggal buku satu barang tidak boleh lebih awal daripada transaksi terakhir
barang tersebut. Barang yang sudah mempunyai riwayat tidak dapat dihapus dan
harus dinonaktifkan agar audit stok tetap utuh.

## Cetak langsung

Aplikasi membaca daftar printer dari Windows. PDF laporan dirender ke halaman
A4 dan dikirim melalui dialog printer native. Pengguna tetap dapat mengganti
printer pada dialog sebelum mencetak. Bila printer tidak terdeteksi, pencetakan
ditolak tanpa mengubah transaksi atau dokumen.
