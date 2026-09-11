from __future__ import annotations

import unittest
from datetime import date, time
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from tpp_finger_scan.application.services import AttendanceApplicationService
from tpp_finger_scan.domain.models import (
    AttendanceEntry,
    AttendanceState,
    Employee,
    ImportResult,
    SpecialCode,
)
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

    def test_handwritten_tl_is_normalized_without_guessing_times(self) -> None:
        self.assertEqual(FingerScanPdfParser._normalize_ocr_cell("T"), "TL")
        self.assertEqual(FingerScanPdfParser._normalize_ocr_cell("TT"), "TL")
        self.assertEqual(FingerScanPdfParser._normalize_ocr_cell("TW"), "TL")
        self.assertEqual(FingerScanPdfParser._normalize_ocr_cell("08:38- T-"), "08:38-")
        self.assertNotEqual(FingerScanPdfParser._normalize_ocr_cell("07:3 W721"), "W")
        self.assertEqual(FingerScanPdfParser._normalize_ocr_cell("07:58"), "07:58")
        self.assertFalse(FingerScanPdfParser._is_recognized_ocr_cell("07:58"))

    def test_column_consensus_recovers_split_tl_strokes_without_changing_times(self) -> None:
        values = ["TL", "TL", "TL", "W", "S", "", "1", "07:38-"]
        cells = [
            {"column": 8, "code_like": True, "word": {"text": value}}
            for value in values
        ]
        FingerScanPdfParser._reconcile_special_code_columns(cells)
        self.assertEqual(
            [cell["word"]["text"] for cell in cells],
            ["TL", "TL", "TL", "TL", "TL", "TL", "TL", "07:38-"],
        )

    def test_column_consensus_does_not_guess_a_mixed_code_column(self) -> None:
        cells = [
            {"column": 4, "code_like": True, "word": {"text": value}}
            for value in ("W", "TL", "", "1")
        ]
        FingerScanPdfParser._reconcile_special_code_columns(cells)
        self.assertEqual([cell["word"]["text"] for cell in cells], ["W", "TL", "", "1"])

    def test_single_time_line_uses_vertical_position_for_missing_finger(self) -> None:
        image = Image.new("L", (80, 120), 255)
        with patch.object(FingerScanPdfParser, "_ocr_region", return_value="07:29"), patch.object(
            FingerScanPdfParser,
            "_ocr_time_lines",
            return_value=[("07:29", 0.30)],
        ):
            self.assertEqual(FingerScanPdfParser._ocr_scan_cell(image), "07:29-")
        with patch.object(FingerScanPdfParser, "_ocr_region", return_value="16:51"), patch.object(
            FingerScanPdfParser,
            "_ocr_time_lines",
            return_value=[("16:51", 0.75)],
        ):
            self.assertEqual(FingerScanPdfParser._ocr_scan_cell(image), "-16:51")

    def test_single_scan_glyph_i_requires_operator_review(self) -> None:
        image = Image.new("L", (80, 120), 255)
        with patch.object(FingerScanPdfParser, "_ocr_region", side_effect=("", "I")):
            self.assertEqual(FingerScanPdfParser._ocr_scan_cell(image), "?I")

    def test_scanned_table_grid_reconstructs_date_columns(self) -> None:
        image = Image.new("L", (1400, 800), 255)
        draw = ImageDraw.Draw(image)
        date_boundaries = tuple(range(500, 1101, 120))
        for y in (100, 140, 200, 260, 320, 380):
            draw.rectangle((100, y, 1100, y + 2), fill=0)
        for x in (100, *date_boundaries):
            draw.rectangle((x, 100, x + 2, 380), fill=0)

        grid = FingerScanPdfParser._detect_scan_grid(image, 5, dpi=100)

        self.assertEqual(grid.name_left, 100)
        self.assertEqual(grid.date_boundaries, date_boundaries)
        self.assertGreaterEqual(len(grid.row_bands), 3)

    def test_special_codes_from_pdf_become_automatic_overrides(self) -> None:
        entry = AttendanceEntry(
            self.employee,
            date(2026, 8, 24),
            "TL",
            None,
            None,
            AttendanceState.INVALID,
            1,
        )
        result = ImportResult(
            Path("scan.pdf"),
            "sha256",
            entry.work_date,
            entry.work_date,
            [self.employee],
            [entry],
        )

        class StubParser:
            @staticmethod
            def parse(_path):
                return result

        session = AttendanceApplicationService(parser=StubParser()).import_pdf("scan.pdf")
        key = (self.employee.finger_id, entry.work_date)
        self.assertEqual(session.overrides[key].code, SpecialCode.TL)
        self.assertEqual(session.calculations[0].status, "TL")
        self.assertTrue(session.finalizable)


if __name__ == "__main__":
    unittest.main()
