# Audit Paritas Engine SIPS

Dokumen ini memetakan logika pembuatan surat pada source lama
`legacy/sips_app` ke implementasi PySide6 di `sekretariat_app/sips`.

| Kemampuan SIPS lama | Implementasi baru | Status |
|---|---|---|
| Context perjalanan dinas | `SIPSService.build_travel_context` | Setara |
| Surat Tugas DPRD biasa/tabel | `buat_surat_tugas_dprd` | Kode inti identik |
| Surat Tugas ASN biasa/tabel | `buat_surat_tugas_asn` | Kode inti identik |
| Pemberitahuan multi-tujuan | `buat_surat_pemberitahuan_multi` | Ditingkatkan: pelaksana, jabatan penerima, zona per tujuan, dan reset nomor per halaman |
| SPD depan/belakang DPRD dan ASN | `buat_sppd_dprd`, `buat_sppd_asn` | Ditingkatkan: seluruh tujuan dan ekstraksi kabupaten/kota |
| Nomor SPD ASN berurutan | `increment_nomor_spd` | Setara |
| Transportasi otomatis | `build_travel_context` | Setara |
| Zona waktu dan periode tiap tujuan | `text_utils` | Resolver offline WIB/WITA/WIT dari nama instansi dan kabupaten/kota |
| Filter kategori pelaksana DPRD | `PersonnelCheckList` | Multi-pilih kategori; hanya nama kategori aktif yang ditampilkan |
| Daftar hadir perjalanan | `generate_travel_attendance` | Setara; peserta DPRD diperbaiki sesuai source lama |
| Undangan Paripurna delapan halaman | `_generate_plenary` | Setara |
| Nomor Paripurna pada segmen ketiga | `increment_nomor_paripurna` | Setara |
| Undangan Biasa dan pihak tanpa batas | `_generate_regular` | Setara |
| Tujuan tambahan tanpa batas | `_generate_regular` | Setara |
| Penyaringan Tenaga Ahli Fraksi | `_is_taf` | Setara |
| Naskah Dinas | `generate_official_note` | Setara dan dapat dibuat mandiri |
| Daftar Hadir rapat + lembar tambahan | `generate_meeting_attendance` | Setara dan dapat dibuat mandiri |
| Validasi nomor surat ganda | `SIPSRepository.validate_numbers` | Setara, memakai SQLite lokal |
| Peringatan materi yang sama | `find_duplicate_travel_title` | Setara |
| Tetap lanjut bila satu dokumen gagal | `GenerationReport` | Setara dengan laporan error lebih jelas |
| Autocomplete tujuan | `DEFAULT_TRAVEL_DESTINATIONS` + `QCompleter` | Setara |
| Live Preview | `LiveDocumentPreview` | Diganti implementasi PySide6; hasil memakai engine final yang sama |

Seluruh 21 template `.docx` pada paket baru telah dibandingkan SHA-256 dengan
template source SIPS lama dan identik. Komponen CustomTkinter, JSON bersama,
dan login lama tidak dipindahkan karena sudah digantikan oleh shell PySide6,
SQLite, serta modul autentikasi aplikasi terpadu; hal tersebut tidak mengubah
isi atau aturan pembuatan surat.

Regression test berada di `tests/test_sips.py` dan mencakup semua kelompok
dokumen utama, hasil parsial, dokumen pendukung mandiri, peserta ASN tanpa DPRD,
duplikasi materi, penamaan file, serta pemeriksaan bahwa placeholder Jinja tidak
tersisa di hasil DOCX.
