from __future__ import annotations

import argparse
import json
from pathlib import Path

from tpp_finger_scan.application.services import AttendanceApplicationService
from tpp_finger_scan.config import database_path
from tpp_finger_scan.infrastructure.excel_exporter import ExcelExporter
from tpp_finger_scan.infrastructure.pdf_parser import PdfParseError
from tpp_finger_scan.infrastructure.repository import SQLiteRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tpp-finger-cli",
        description="Validasi dan ekspor PDF finger scan tanpa membuka UI.",
    )
    parser.add_argument("pdf", type=Path, help="Path PDF hasil finger scan")
    parser.add_argument("--export", type=Path, help="Simpan rekap ke .xlsx")
    parser.add_argument("--save-db", action="store_true", help="Simpan snapshot ke SQLite")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        session = AttendanceApplicationService().import_pdf(args.pdf)
    except PdfParseError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    export_path = None
    if args.export:
        export_path = ExcelExporter().export(session, args.export)
    import_id = None
    if args.save_db:
        import_id = SQLiteRepository(database_path()).save_session(session)

    result = session.import_result
    print(json.dumps({
        "ok": True,
        "source": str(result.source_path),
        "period_start": result.period_start.isoformat(),
        "period_end": result.period_end.isoformat(),
        "employees": len(result.employees),
        "attendance_entries": len(result.entries),
        "blocking_reviews": session.blocking_count,
        "total_deduction_percentage_points": str(session.total_deduction),
        "export": str(export_path) if export_path else None,
        "database_import_id": import_id,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

