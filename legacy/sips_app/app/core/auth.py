"""
Manajemen akun pengguna: hashing password, verifikasi, dan load/save daftar
akun (termasuk pembuatan super admin default saat pertama kali dijalankan).
Murni logika data, tidak ada kode UI di sini.
"""
import hashlib
import secrets

from app.config.settings import ACCOUNTS_FILE, SUPERADMIN_USERNAME, SUPERADMIN_DEFAULT_PASSWORD
from app.core.app_logging import safe_log
from app.data.shared_store import locked_read_json, locked_write_json


def _hash_password(password: str, salt: str = None):
    """Hash password dengan SHA-256 + salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed, salt

def _verify_password(password: str, hashed: str, salt: str) -> bool:
    h, _ = _hash_password(password, salt)
    return h == hashed

def load_accounts() -> dict:
    """Muat daftar akun dari file BERSAMA (kalau mode jaringan aktif, satu
    daftar akun dipakai bareng semua komputer -- akun baru yang dibuat
    superadmin di komputer A langsung bisa dipakai login di komputer B/C).
    Buat super admin default jika file belum pernah ada sama sekali."""
    existing = locked_read_json(ACCOUNTS_FILE, None)
    if isinstance(existing, dict) and existing:
        return existing
    accounts = {}
    hashed, salt = _hash_password(SUPERADMIN_DEFAULT_PASSWORD)
    accounts[SUPERADMIN_USERNAME] = {
        "hashed": hashed,
        "salt": salt,
        "role": "superadmin",
        "nama_lengkap": "Super Admin (Tata Usaha)",
        "aktif": True,
    }
    save_accounts(accounts)
    return accounts

def save_accounts(accounts: dict):
    try:
        locked_write_json(ACCOUNTS_FILE, accounts)
    except Exception as e:
        safe_log(f"Gagal menyimpan akun: {e}")
