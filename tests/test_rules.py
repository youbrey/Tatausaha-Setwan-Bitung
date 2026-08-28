from __future__ import annotations

import unittest
from datetime import date, time
from decimal import Decimal

from tpp_finger_scan.domain.models import (
    AttendanceEntry,
    AttendanceState,
    DayOverride,
    Employee,
    SpecialCode,
)
from tpp_finger_scan.domain.rules import DeductionEngine


EMPLOYEE = Employee("101", "PEGAWAI UJI")


def attendance(
    in_time: time | None,
    out_time: time | None,
    *,
    work_date: date = date(2026, 8, 24),
    state: AttendanceState = AttendanceState.COMPLETE,
) -> AttendanceEntry:
    return AttendanceEntry(
        EMPLOYEE, work_date, "uji", in_time, out_time, state, source_page=1,
    )


class DeductionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DeductionEngine()

    def test_late_boundaries(self) -> None:
        cases = (
            (time(7, 30), "0.00"),
            (time(7, 40), "0.50"),
            (time(8, 0), "0.50"),
            (time(8, 1), "1.00"),
            (time(8, 30), "1.00"),
            (time(8, 31), "1.25"),
            (time(9, 0), "1.25"),
            (time(9, 1), "1.50"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                result = self.engine.calculate(attendance(value, time(16, 45)))
                self.assertEqual(result.deductions.late, Decimal(expected))
                self.assertTrue(result.finalizable)

    def test_unspecified_late_tolerance_is_blocked(self) -> None:
        result = self.engine.calculate(attendance(time(7, 35), time(16, 45)))
        self.assertEqual(result.deductions.late, Decimal("0.00"))
        self.assertFalse(result.finalizable)
        self.assertEqual(result.issues[0].code, "TOLERANCE_0731_0739_UNAPPROVED")

    def test_early_departure_boundaries_monday_to_thursday(self) -> None:
        cases = (
            (time(15, 0), "1.50"),
            (time(15, 30), "1.50"),
            (time(15, 31), "1.25"),
            (time(16, 0), "1.25"),
            (time(16, 1), "1.00"),
            (time(16, 30), "1.00"),
            (time(16, 31), "0.50"),
            (time(16, 44), "0.50"),
            (time(16, 45), "0.00"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                result = self.engine.calculate(attendance(time(7, 30), value))
                self.assertEqual(result.deductions.early, Decimal(expected))
                self.assertTrue(result.finalizable)

    def test_early_before_1500_is_blocked(self) -> None:
        result = self.engine.calculate(attendance(time(7, 30), time(14, 59)))
        self.assertFalse(result.finalizable)
        self.assertEqual(result.issues[0].code, "EARLY_BEFORE_1500_UNAPPROVED")

    def test_friday_schedule(self) -> None:
        friday = date(2026, 8, 21)
        on_time = self.engine.calculate(attendance(time(7, 30), time(12, 0), work_date=friday))
        too_early = self.engine.calculate(attendance(time(7, 30), time(11, 59), work_date=friday))
        self.assertEqual(on_time.deductions.total, Decimal("0.00"))
        self.assertTrue(on_time.finalizable)
        self.assertFalse(too_early.finalizable)

    def test_missing_scan_rules(self) -> None:
        missing_both = self.engine.calculate(attendance(
            None, None, state=AttendanceState.MISSING_BOTH,
        ))
        missing_in = self.engine.calculate(attendance(
            None, time(16, 45), state=AttendanceState.MISSING_IN,
        ))
        missing_out = self.engine.calculate(attendance(
            time(7, 30), None, state=AttendanceState.MISSING_OUT,
        ))
        self.assertEqual(missing_both.deductions.absence, Decimal("3.00"))
        self.assertEqual(missing_in.deductions.late, Decimal("1.50"))
        self.assertEqual(missing_out.deductions.early, Decimal("1.55"))

    def test_missing_out_keeps_late_deduction_regression(self) -> None:
        """Kasus Yuniky 10-08-2026: 08.31 masuk, finger pulang kosong."""
        result = self.engine.calculate(attendance(
            time(8, 31),
            None,
            work_date=date(2026, 8, 10),
            state=AttendanceState.MISSING_OUT,
        ))
        self.assertEqual(result.deductions.absence, Decimal("0.00"))
        self.assertEqual(result.deductions.late, Decimal("1.25"))
        self.assertEqual(result.deductions.early, Decimal("1.55"))
        self.assertEqual(result.deductions.total, Decimal("2.80"))
        self.assertEqual(result.status, "Terlambat + Tidak Finger Pulang")
        self.assertTrue(result.finalizable)

    def test_missing_in_keeps_early_departure_deduction(self) -> None:
        result = self.engine.calculate(attendance(
            None,
            time(16, 0),
            state=AttendanceState.MISSING_IN,
        ))
        self.assertEqual(result.deductions.absence, Decimal("0.00"))
        self.assertEqual(result.deductions.late, Decimal("1.50"))
        self.assertEqual(result.deductions.early, Decimal("1.25"))
        self.assertEqual(result.deductions.total, Decimal("2.75"))
        self.assertEqual(result.status, "Tidak Finger Masuk + Pulang Cepat")
        self.assertTrue(result.finalizable)

    def test_absence_column_only_for_missing_both(self) -> None:
        missing_in = self.engine.calculate(attendance(
            None, time(15, 30), state=AttendanceState.MISSING_IN,
        ))
        missing_out = self.engine.calculate(attendance(
            time(8, 31), None, state=AttendanceState.MISSING_OUT,
        ))
        missing_both = self.engine.calculate(attendance(
            None, None, state=AttendanceState.MISSING_BOTH,
        ))
        self.assertEqual(missing_in.deductions.absence, Decimal("0.00"))
        self.assertEqual(missing_out.deductions.absence, Decimal("0.00"))
        self.assertEqual(missing_both.deductions.absence, Decimal("3.00"))

    def test_special_codes_override_finger_result(self) -> None:
        entry = attendance(None, None, state=AttendanceState.MISSING_BOTH)
        tl = self.engine.calculate(entry, DayOverride(code=SpecialCode.TL))
        permit = self.engine.calculate(entry, DayOverride(code=SpecialCode.I))
        inpatient = self.engine.calculate(
            entry,
            DayOverride(code=SpecialCode.S, inpatient=True),
        )
        sick_without_evidence = self.engine.calculate(entry, DayOverride(code=SpecialCode.S))
        self.assertEqual(tl.deductions.total, Decimal("0.00"))
        self.assertEqual(permit.deductions.absence, Decimal("3.00"))
        self.assertEqual(inpatient.deductions.total, Decimal("0.00"))
        self.assertTrue(inpatient.highlight_yellow)
        self.assertFalse(sick_without_evidence.finalizable)

    def test_wfh_and_w_are_present_without_deduction(self) -> None:
        entry = attendance(None, None, state=AttendanceState.MISSING_BOTH)
        for code in (SpecialCode.WFH, SpecialCode.W):
            with self.subTest(code=code):
                result = self.engine.calculate(entry, DayOverride(code=code))
                self.assertEqual(result.deductions.total, Decimal("0.00"))
                self.assertEqual(result.status, "WFH — Hadir")

    def test_weekend_has_no_deduction(self) -> None:
        sunday = attendance(
            None,
            None,
            work_date=date(2026, 8, 23),
            state=AttendanceState.MISSING_BOTH,
        )
        result = self.engine.calculate(sunday)
        self.assertEqual(result.deductions.total, Decimal("0.00"))
        self.assertEqual(result.status, "Bukan Hari Kerja")


if __name__ == "__main__":
    unittest.main()
