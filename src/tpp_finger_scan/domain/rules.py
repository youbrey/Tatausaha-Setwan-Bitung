from __future__ import annotations

from datetime import time
from decimal import Decimal

from .calendar import schedule_for
from .models import (
    AttendanceEntry,
    AttendanceState,
    DayCalculation,
    DayOverride,
    DeductionBreakdown,
    Issue,
    SpecialCode,
    ZERO,
)


PCT_050 = Decimal("0.50")
PCT_100 = Decimal("1.00")
PCT_125 = Decimal("1.25")
PCT_150 = Decimal("1.50")
PCT_155 = Decimal("1.55")
PCT_300 = Decimal("3.00")


class DeductionEngine:
    """Rule engine deterministik; celah aturan selalu menjadi blocking issue."""

    def calculate(
        self,
        entry: AttendanceEntry,
        override: DayOverride | None = None,
        *,
        is_holiday: bool = False,
    ) -> DayCalculation:
        override = override or DayOverride()
        schedule = schedule_for(entry.work_date)

        if is_holiday or not schedule.workday:
            return DayCalculation(entry, DeductionBreakdown(), "Bukan Hari Kerja")

        if override.code == SpecialCode.TL:
            return DayCalculation(entry, DeductionBreakdown(), "TL")
        if override.code in {SpecialCode.WFH, SpecialCode.W}:
            return DayCalculation(entry, DeductionBreakdown(), "WFH — Hadir")
        if override.code == SpecialCode.I:
            return DayCalculation(
                entry,
                DeductionBreakdown(absence=PCT_300),
                "Izin",
            )
        if override.code == SpecialCode.S:
            if override.inpatient:
                return DayCalculation(
                    entry,
                    DeductionBreakdown(),
                    "Sakit — Rawat Inap",
                    highlight_yellow=True,
                )
            return DayCalculation(
                entry,
                DeductionBreakdown(),
                "Sakit — Perlu Bukti",
                (Issue("S_REQUIRES_INPATIENT_EVIDENCE", "Status S belum memiliki bukti rawat inap."),),
                highlight_yellow=True,
            )

        if entry.state == AttendanceState.INVALID:
            return DayCalculation(
                entry,
                DeductionBreakdown(),
                "Data Tidak Valid",
                (Issue("INVALID_ATTENDANCE", f"Nilai finger tidak dapat dibaca: {entry.raw_cell!r}."),),
            )
        if entry.state == AttendanceState.MISSING_BOTH:
            return DayCalculation(
                entry,
                DeductionBreakdown(absence=PCT_300),
                "Tidak Masuk Kerja",
            )
        if entry.state == AttendanceState.MISSING_IN:
            early, early_issue = self._early(entry.work_date.weekday(), entry.out_time)
            issues = (early_issue,) if early_issue is not None else ()
            status = "Tidak Finger Masuk"
            if early > ZERO:
                status += " + Pulang Cepat"
            if issues:
                status += " + Perlu Review"
            return DayCalculation(
                entry,
                DeductionBreakdown(late=PCT_150, early=early),
                status,
                issues,
            )
        if entry.state == AttendanceState.MISSING_OUT:
            late, late_issue = self._late(entry.in_time)
            issues = (late_issue,) if late_issue is not None else ()
            status = "Tidak Finger Pulang"
            if late > ZERO:
                status = "Terlambat + " + status
            if issues:
                status += " + Perlu Review"
            return DayCalculation(
                entry,
                DeductionBreakdown(late=late, early=PCT_155),
                status,
                issues,
            )

        late, late_issue = self._late(entry.in_time)
        early, early_issue = self._early(entry.work_date.weekday(), entry.out_time)
        issues = tuple(issue for issue in (late_issue, early_issue) if issue is not None)
        status_parts = []
        if late > ZERO:
            status_parts.append("Terlambat")
        if early > ZERO:
            status_parts.append("Pulang Cepat")
        if issues:
            status_parts.append("Perlu Review")
        return DayCalculation(
            entry,
            DeductionBreakdown(late=late, early=early),
            " + ".join(status_parts) if status_parts else "Hadir",
            issues,
        )

    @staticmethod
    def _late(value: time | None) -> tuple[Decimal, Issue | None]:
        if value is None:
            return PCT_150, None
        if value <= time(7, 30):
            return ZERO, None
        if value <= time(7, 39):
            return ZERO, Issue(
                "TOLERANCE_0731_0739_UNAPPROVED",
                "Rentang 07.31–07.39 belum ditegaskan sebagai toleransi tanpa potongan.",
            )
        if value <= time(8, 0):
            return PCT_050, None
        if value <= time(8, 30):
            return PCT_100, None
        if value <= time(9, 0):
            return PCT_125, None
        return PCT_150, None

    @staticmethod
    def _early(weekday: int, value: time | None) -> tuple[Decimal, Issue | None]:
        if value is None:
            return PCT_155, None
        if weekday == 4:
            if value >= time(12, 0):
                return ZERO, None
            return ZERO, Issue(
                "FRIDAY_EARLY_RANGES_UNAPPROVED",
                "Jam pulang Jumat sebelum 12.00 terdeteksi, tetapi rentang potongannya belum disahkan.",
            )
        if value >= time(16, 45):
            return ZERO, None
        if value < time(15, 0):
            return ZERO, Issue(
                "EARLY_BEFORE_1500_UNAPPROVED",
                "Jam pulang sebelum 15.00 terdeteksi, tetapi persentase potongannya belum disahkan.",
            )
        if value <= time(15, 30):
            return PCT_150, None
        if value <= time(16, 0):
            return PCT_125, None
        if value <= time(16, 30):
            return PCT_100, None
        return PCT_050, None
