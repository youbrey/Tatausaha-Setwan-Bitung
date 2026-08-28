from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class User:
    user_id: int
    username: str
    full_name: str
    role: str
    active: bool = True


class UserRepository:
    """Penyimpanan akun lokal dengan PBKDF2 dan salt per pengguna."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'operator',
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            exists = db.execute("SELECT 1 FROM users LIMIT 1").fetchone()
            if not exists:
                salt, password_hash = self._password_parts("admin123")
                now = datetime.now().isoformat(timespec="seconds")
                db.execute(
                    "INSERT INTO users(username, full_name, role, password_hash, salt, active, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                    ("admin", "Administrator", "superadmin", password_hash, salt, now, now),
                )

    @staticmethod
    def _password_parts(password: str, salt: str | None = None) -> tuple[str, str]:
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 240_000)
        return salt, digest.hex()

    def authenticate(self, username: str, password: str) -> User | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE AND active = 1",
                (username.strip(),),
            ).fetchone()
        if not row:
            return None
        _, candidate = self._password_parts(password, row["salt"])
        if not hmac.compare_digest(candidate, row["password_hash"]):
            return None
        user = self._to_user(row)
        self.log(user.username, "login", "Login berhasil")
        return user

    def list_users(self) -> list[User]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM users ORDER BY full_name COLLATE NOCASE").fetchall()
        return [self._to_user(row) for row in rows]

    def add_user(self, username: str, full_name: str, role: str, password: str) -> User:
        if len(password) < 6:
            raise ValueError("Kata sandi minimal 6 karakter.")
        salt, password_hash = self._password_parts(password)
        now = datetime.now().isoformat(timespec="seconds")
        try:
            with self._connect() as db:
                cursor = db.execute(
                    "INSERT INTO users(username, full_name, role, password_hash, salt, active, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                    (username.strip(), full_name.strip(), role, password_hash, salt, now, now),
                )
                user_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError("Username sudah digunakan.") from exc
        return User(user_id, username.strip(), full_name.strip(), role, True)

    def set_active(self, user_id: int, active: bool) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE users SET active = ?, updated_at = ? WHERE id = ?",
                (int(active), datetime.now().isoformat(timespec="seconds"), user_id),
            )

    def reset_password(self, user_id: int, password: str) -> None:
        if len(password) < 6:
            raise ValueError("Kata sandi minimal 6 karakter.")
        salt, password_hash = self._password_parts(password)
        with self._connect() as db:
            db.execute(
                "UPDATE users SET password_hash = ?, salt = ?, updated_at = ? WHERE id = ?",
                (password_hash, salt, datetime.now().isoformat(timespec="seconds"), user_id),
            )

    def log(self, username: str, action: str, detail: str = "") -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO activity_log(username, action, detail, created_at) VALUES (?, ?, ?, ?)",
                (username, action, detail, datetime.now().isoformat(timespec="seconds")),
            )

    @staticmethod
    def _to_user(row: sqlite3.Row) -> User:
        return User(int(row["id"]), row["username"], row["full_name"], row["role"], bool(row["active"]))
