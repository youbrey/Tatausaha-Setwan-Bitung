"""
Lapisan akses file BERSAMA (shared/network folder) untuk membuat SIPS di
beberapa komputer saling terhubung TANPA internet dan TANPA server
database terpisah -- cukup mengarahkan seluruh komputer ke satu folder
jaringan (mis. `\\\\SERVER-TU\\SIPS_DATA` di Windows, atau folder yang
sama lewat mapped drive `Z:\\SIPS_DATA`).

Kenapa pendekatan ini (bukan SQLite/DB server)?
- Aplikasi wajib tetap 100% offline & ringan (RAM/CPU rendah) -- menjalankan
  server database di salah satu komputer menambah kerumitan operasional
  (harus selalu menyala, firewall, dsb).
- File JSON yang sudah dipakai SIPS (sips_data.json, sips_history.json,
  sips_accounts.json) bisa "diobati" jadi multi-komputer hanya dengan:
    1. Menaruh file itu di folder yang bisa diakses semua komputer (Windows
       File Sharing / folder jaringan biasa).
    2. Mencegah dua proses menulis file itu di saat yang SAMA PERSIS
       (race condition) -- inilah tugas modul ini.
    3. Menulis secara ATOMIK (tulis ke file sementara lalu rename) supaya
       komputer lain tidak pernah membaca file yang "setengah tertulis".

Locking dibuat SENDIRI (tanpa library pihak ketiga tambahan) memakai pola
"lock file" klasik yang bekerja di Windows maupun di jaringan SMB:
- Untuk mendapat kunci, coba buat file `<target>.lock` memakai mode
  eksklusif `os.O_CREAT | os.O_EXCL` (gagal jika file itu sudah ada --
  artinya komputer lain sedang memegang kunci).
- Coba ulang (retry) dengan jeda pendek sampai batas waktu tercapai.
- Kunci yang "basi" (proses pemegang lock crash/komputer mati mendadak
  sebelum sempat melepas kunci) otomatis dianggap kadaluarsa setelah
  STALE_LOCK_SECONDS supaya folder bersama tidak "macet total" selamanya.
"""
import json
import os
import socket
import time
import uuid

STALE_LOCK_SECONDS = 20  # lock lebih tua dari ini dianggap basi (proses pemilik crash)
LOCK_RETRY_INTERVAL = 0.15
LOCK_TIMEOUT_SECONDS = 8


class SharedStoreError(Exception):
    """Dilempar kalau file bersama gagal diakses (mis. folder jaringan
    sedang terputus). Pemanggil disarankan menangkap ini dan fallback ke
    salinan lokal / memberi tahu pengguna, BUKAN membiarkan aplikasi crash."""


def _lock_path(path):
    return path + ".lock"


def _acquire_lock(path, timeout=LOCK_TIMEOUT_SECONDS):
    lock_file = _lock_path(path)
    deadline = time.time() + timeout
    owner_tag = f"{socket.gethostname()}|{os.getpid()}|{uuid.uuid4().hex[:8]}"

    while True:
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as f:
                f.write(f"{owner_tag}|{time.time()}")
            return owner_tag
        except FileExistsError:
            # Lock sedang dipegang komputer/proses lain -> cek apakah basi.
            try:
                age = time.time() - os.path.getmtime(lock_file)
                if age > STALE_LOCK_SECONDS:
                    os.remove(lock_file)  # lock basi, ambil alih
                    continue
            except OSError:
                pass  # lock sudah hilang duluan (dilepas proses lain), coba lagi

            if time.time() >= deadline:
                raise SharedStoreError(
                    f"Tidak bisa mendapatkan akses tulis ke '{os.path.basename(path)}' "
                    "(sedang dipakai komputer lain). Coba lagi beberapa detik lagi."
                )
            time.sleep(LOCK_RETRY_INTERVAL)


def _release_lock(path):
    lock_file = _lock_path(path)
    try:
        os.remove(lock_file)
    except OSError:
        pass


def locked_read_json(path, default):
    """Baca JSON dengan aman. Pembacaan tidak butuh lock eksklusif (JSON
    ditulis atomik lewat os.replace di locked_write_json, jadi pembaca
    tidak akan pernah melihat file setengah jadi) -- cukup try/except."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def locked_write_json(path, data):
    """Tulis JSON dengan lock eksklusif antar-komputer + tulis atomik
    (write-to-temp lalu os.replace) supaya tidak ada file korup/parsial
    walau listrik/koneksi jaringan putus di tengah proses tulis."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _acquire_lock(path)
    try:
        tmp_path = f"{path}.tmp-{uuid.uuid4().hex[:8]}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, path)  # atomik di Windows & Linux (termasuk share SMB umumnya)
    finally:
        _release_lock(path)


def update_json(path, default, mutate_fn):
    """Baca -> ubah -> tulis dalam SATU kunci (read-modify-write atomik),
    ini yang dipakai untuk cek+pakai nomor surat supaya dua komputer tidak
    bisa lolos memakai nomor yang sama meski mengeklik generate pada detik
    yang sama persis (mencegah race condition, bukan cuma cek lalu tulis
    terpisah).

    `mutate_fn(data) -> (data_baru, hasil)`. Fungsi ini mengembalikan
    `hasil` apa adanya ke pemanggil (mis. True/False berhasil pakai nomor).
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _acquire_lock(path)
    try:
        data = locked_read_json(path, default)
        new_data, hasil = mutate_fn(data)
        tmp_path = f"{path}.tmp-{uuid.uuid4().hex[:8]}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, path)
        return hasil
    finally:
        _release_lock(path)
