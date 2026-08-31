from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from sekretariat_app.sips.models import DocumentRecord, new_record_id, now_iso


class SIPSRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as database:
            database.executescript(
                """
                CREATE TABLE IF NOT EXISTS sips_documents (
                    id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    document_number TEXT NOT NULL DEFAULT '',
                    document_date TEXT NOT NULL DEFAULT '',
                    event_start TEXT NOT NULL DEFAULT '',
                    event_end TEXT NOT NULL DEFAULT '',
                    destination TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL CHECK(status IN ('draft', 'generated')),
                    author TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    files_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_sips_documents_type_date
                    ON sips_documents(record_type, document_date);
                CREATE INDEX IF NOT EXISTS ix_sips_documents_status
                    ON sips_documents(status);
                CREATE TABLE IF NOT EXISTS sips_document_numbers (
                    record_id TEXT NOT NULL REFERENCES sips_documents(id) ON DELETE CASCADE,
                    label TEXT NOT NULL,
                    number TEXT NOT NULL COLLATE NOCASE,
                    UNIQUE(number),
                    UNIQUE(record_id, label)
                );
                """
            )

    def save(
        self,
        *,
        record_type: str,
        title: str,
        document_number: str,
        document_date: str,
        event_start: str,
        event_end: str,
        destination: str,
        status: str,
        author: str,
        payload: dict,
        files: Iterable[str] = (),
        numbers: dict[str, str] | None = None,
        record_id: str | None = None,
    ) -> str:
        record_id = record_id or new_record_id()
        timestamp = now_iso()
        numbers = {label: value.strip() for label, value in (numbers or {}).items() if value and value.strip()}
        with self._connect() as database:
            existing = database.execute("SELECT created_at FROM sips_documents WHERE id = ?", (record_id,)).fetchone()
            created_at = existing["created_at"] if existing else timestamp
            database.execute(
                """
                INSERT INTO sips_documents(
                    id, record_type, title, document_number, document_date,
                    event_start, event_end, destination, status, author,
                    payload_json, files_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    record_type=excluded.record_type,
                    title=excluded.title,
                    document_number=excluded.document_number,
                    document_date=excluded.document_date,
                    event_start=excluded.event_start,
                    event_end=excluded.event_end,
                    destination=excluded.destination,
                    status=excluded.status,
                    author=excluded.author,
                    payload_json=excluded.payload_json,
                    files_json=excluded.files_json,
                    updated_at=excluded.updated_at
                """,
                (
                    record_id, record_type, title, document_number, document_date,
                    event_start, event_end, destination, status, author,
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps([str(path) for path in files], ensure_ascii=False),
                    created_at, timestamp,
                ),
            )
            database.execute("DELETE FROM sips_document_numbers WHERE record_id = ?", (record_id,))
            if status == "generated":
                try:
                    database.executemany(
                        "INSERT INTO sips_document_numbers(record_id, label, number) VALUES (?, ?, ?)",
                        [(record_id, label, number) for label, number in numbers.items()],
                    )
                except sqlite3.IntegrityError as exc:
                    conflict = next(
                        (
                            number for number in numbers.values()
                            if database.execute(
                                "SELECT 1 FROM sips_document_numbers WHERE number = ? AND record_id <> ?",
                                (number, record_id),
                            ).fetchone()
                        ),
                        "",
                    )
                    raise ValueError(f"Nomor surat '{conflict}' sudah digunakan pada dokumen lain.") from exc
        return record_id

    def validate_numbers(self, numbers: dict[str, str], record_id: str | None = None) -> None:
        clean = [value.strip() for value in numbers.values() if value and value.strip()]
        if len(clean) != len({value.casefold() for value in clean}):
            raise ValueError("Satu nomor surat tidak boleh dipakai untuk dua jenis dokumen pada formulir yang sama.")
        if not clean:
            return
        placeholders = ",".join("?" for _ in clean)
        parameters: list[str] = list(clean)
        query = f"SELECT number FROM sips_document_numbers WHERE number IN ({placeholders})"
        if record_id:
            query += " AND record_id <> ?"
            parameters.append(record_id)
        with self._connect() as database:
            row = database.execute(query, parameters).fetchone()
        if row:
            raise ValueError(f"Nomor surat '{row['number']}' sudah digunakan pada dokumen lain.")

    def find_duplicate_travel_title(
        self,
        title: str,
        record_id: str | None = None,
    ) -> DocumentRecord | None:
        """Cari materi perjalanan yang sama setelah kapital/spasi dinormalisasi."""
        normalized = " ".join(str(title or "").casefold().split())
        if len(normalized) < 6:
            return None
        clauses = ["record_type LIKE 'travel_%'"]
        parameters: list[str] = []
        if record_id:
            clauses.append("id <> ?")
            parameters.append(record_id)
        query = "SELECT * FROM sips_documents WHERE " + " AND ".join(clauses) + " ORDER BY updated_at DESC"
        with self._connect() as database:
            rows = database.execute(query, parameters).fetchall()
        for row in rows:
            if " ".join(str(row["title"] or "").casefold().split()) == normalized:
                return self._to_record(row)
        return None

    def get(self, record_id: str) -> DocumentRecord | None:
        with self._connect() as database:
            row = database.execute("SELECT * FROM sips_documents WHERE id = ?", (record_id,)).fetchone()
        return self._to_record(row) if row else None

    def list(self, *, category: str | None = None, record_type: str | None = None, search: str = "") -> list[DocumentRecord]:
        clauses: list[str] = []
        parameters: list[str] = []
        if category == "travel":
            clauses.append("record_type LIKE 'travel_%'")
        elif category == "invitation":
            clauses.append("record_type LIKE 'invitation_%'")
        if record_type:
            clauses.append("record_type = ?")
            parameters.append(record_type)
        if search.strip():
            clauses.append("(title LIKE ? OR document_number LIKE ? OR destination LIKE ? OR author LIKE ?)")
            value = f"%{search.strip()}%"
            parameters.extend([value, value, value, value])
        query = "SELECT * FROM sips_documents"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC"
        with self._connect() as database:
            rows = database.execute(query, parameters).fetchall()
        return [self._to_record(row) for row in rows]

    def delete_draft(self, record_id: str) -> bool:
        with self._connect() as database:
            cursor = database.execute(
                "DELETE FROM sips_documents WHERE id = ? AND status = 'draft'",
                (record_id,),
            )
        return cursor.rowcount > 0

    def dashboard_stats(self) -> dict[str, int]:
        with self._connect() as database:
            row = database.execute(
                """
                SELECT
                    SUM(record_type LIKE 'travel_%' AND status='generated') AS travel,
                    SUM(record_type='invitation_plenary' AND status='generated') AS plenary,
                    SUM(record_type='invitation_regular' AND status='generated') AS regular,
                    SUM(status='draft') AS drafts
                FROM sips_documents
                """
            ).fetchone()
        return {key: int(row[key] or 0) for key in ("travel", "plenary", "regular", "drafts")}

    @staticmethod
    def _to_record(row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            record_id=row["id"],
            record_type=row["record_type"],
            title=row["title"],
            document_number=row["document_number"],
            document_date=row["document_date"],
            event_start=row["event_start"],
            event_end=row["event_end"],
            destination=row["destination"],
            status=row["status"],
            author=row["author"],
            payload=json.loads(row["payload_json"]),
            files=json.loads(row["files_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
