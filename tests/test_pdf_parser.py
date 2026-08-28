from __future__ import annotations

import unittest
from datetime import date, time

from tpp_finger_scan.domain.models import AttendanceState, Employee
from tpp_finger_scan.infrastructure.pdf_parser import FingerScanPdfParser, PdfParseError


class PdfParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.employee = Employee("7", "PEGAWAI UJI")

    def parse_cell(self, raw: str):
        return FingerScanPdfParser._to_entry(
            self.employee, date(2026, 8, 24), raw, page_number=2,
        )

    def test_complete_cell(self) -> None:
        entry = self.parse_cell("07:35-16:48")
        self.assertEqual(entry.state, AttendanceState.COMPLETE)
        self.assertEqual(entry.in_time, time(7, 35))
        self.assertEqual(entry.out_time, time(16, 48))

    def test_missing_cells(self) -> None:
        self.assertEqual(self.parse_cell("-").state, AttendanceState.MISSING_BOTH)
        self.assertEqual(self.parse_cell("").state, AttendanceState.MISSING_BOTH)
        self.assertEqual(self.parse_cell("07:30-").state, AttendanceState.MISSING_OUT)
        self.assertEqual(self.parse_cell("-16:45").state, AttendanceState.MISSING_IN)

    def test_invalid_time_is_not_silently_accepted(self) -> None:
        entry = self.parse_cell("25:61-16:45")
        self.assertEqual(entry.state, AttendanceState.INVALID)
        self.assertEqual(str(entry.confidence), "0.00")

    def test_period_detection(self) -> None:
        start, end = FingerScanPdfParser._extract_period(
            "Data Presensi Dari 26-07-2026 s/d 25-08-2026"
        )
        self.assertEqual(start, date(2026, 7, 26))
        self.assertEqual(end, date(2026, 8, 25))

    def test_missing_period_is_rejected(self) -> None:
        with self.assertRaises(PdfParseError):
            FingerScanPdfParser._extract_period("dokumen tanpa periode")


if __name__ == "__main__":
    unittest.main()

