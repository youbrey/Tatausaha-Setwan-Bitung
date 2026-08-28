from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from tpp_finger_scan.application.services import RecapSession


class SQLiteRepository:
    """Penyimpanan audit lokal. Setiap impor disimpan sebagai snapshot baru."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    imported_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attendance_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
                    finger_id TEXT NOT NULL,
                    employee_name TEXT NOT NULL,
                    work_date TEXT NOT NULL,
                    raw_cell TEXT NOT NULL,
                    in_time TEXT,
                    out_time TEXT,
                    attendance_state TEXT NOT NULL,
                    special_code TEXT NOT NULL,
                    inpatient INTEGER NOT NULL DEFAULT 0,
                    late_pct TEXT NOT NULL,
                    early_pct TEXT NOT NULL,
                    absence_pct TEXT NOT NULL,
                    total_pct TEXT NOT NULL,
                    status TEXT NOT NULL,
                    issues TEXT NOT NULL,
                    UNIQUE(import_id, finger_id, work_date)
                );
                CREATE INDEX IF NOT EXISTS ix_results_import
                    ON attendance_results(import_id);
                CREATE INDEX IF NOT EXISTS ix_results_employee_date
                    ON attendance_results(finger_id, work_date);
                CREATE TABLE IF NOT EXISTS employee_master (
                    finger_id TEXT PRIMARY KEY,
                    employee_name TEXT NOT NULL,
                    position TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                """
            )

    def employee_positions(self, finger_ids: list[str]) -> dict[str, str]:
        if not finger_ids:
            return {}
        placeholders = ",".join("?" for _ in finger_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT finger_id, position FROM employee_master WHERE finger_id IN ({placeholders})",
                finger_ids,
            ).fetchall()
        return {str(finger_id): str(position) for finger_id, position in rows if position}

    def save_employee_position(self, finger_id: str, employee_name: str, position: str) -> None:
        updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO employee_master(finger_id, employee_name, position, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(finger_id) DO UPDATE SET
                    employee_name = excluded.employee_name,
                    position = excluded.position,
                    updated_at = excluded.updated_at
                """,
                (finger_id, employee_name, position.strip(), updated_at),
            )

    def save_session(self, session: RecapSession) -> int:
        imported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        result = session.import_result
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO imports(
                    source_path, source_sha256, period_start, period_end, imported_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(result.source_path),
                    result.source_sha256,
                    result.period_start.isoformat(),
                    result.period_end.isoformat(),
                    imported_at,
                ),
            )
            import_id = int(cursor.lastrowid)
            rows = []
            for calculation in session.calculations:
                entry = calculation.entry
                override = session.overrides.get((entry.employee.finger_id, entry.work_date))
                rows.append((
                    import_id,
                    entry.employee.finger_id,
                    entry.employee.name,
                    entry.work_date.isoformat(),
                    entry.raw_cell,
                    entry.in_time.strftime("%H:%M") if entry.in_time else None,
                    entry.out_time.strftime("%H:%M") if entry.out_time else None,
                    entry.state.value,
                    override.code.value if override else "",
                    int(bool(override and override.inpatient)),
                    str(calculation.deductions.late),
                    str(calculation.deductions.early),
                    str(calculation.deductions.absence),
                    str(calculation.deductions.total),
                    calculation.status,
                    " | ".join(issue.message for issue in calculation.issues),
                ))
            connection.executemany(
                """
                INSERT INTO attendance_results(
                    import_id, finger_id, employee_name, work_date, raw_cell,
                    in_time, out_time, attendance_state, special_code, inpatient,
                    late_pct, early_pct, absence_pct, total_pct, status, issues
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return import_id
