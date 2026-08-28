from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tpp_finger_scan.application.services import AttendanceApplicationService  # noqa: E402
from tpp_finger_scan.infrastructure.excel_exporter import ExcelExporter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--xlsx", type=Path)
    args = parser.parse_args()

    session = AttendanceApplicationService().import_pdf(args.pdf)
    states = Counter(entry.state.value for entry in session.import_result.entries)
    print(f"Periode  : {session.import_result.period_start} s/d {session.import_result.period_end}")
    print(f"Pegawai  : {len(session.import_result.employees)}")
    print(f"Sel       : {len(session.import_result.entries)}")
    print(f"Status    : {dict(states)}")
    print(f"Review    : {session.blocking_count}")
    if args.xlsx:
        print(f"Excel     : {ExcelExporter().export(session, args.xlsx)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

