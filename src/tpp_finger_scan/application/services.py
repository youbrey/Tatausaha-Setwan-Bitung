from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from tpp_finger_scan.domain.models import (
    DayCalculation,
    DayOverride,
    ImportResult,
    SpecialCode,
    ZERO,
)
from tpp_finger_scan.domain.rules import DeductionEngine
from tpp_finger_scan.infrastructure.pdf_parser import FingerScanPdfParser


EntryKey = tuple[str, date]


@dataclass(slots=True)
class RecapSession:
    import_result: ImportResult
    calculations: list[DayCalculation]
    overrides: dict[EntryKey, DayOverride] = field(default_factory=dict)
    holidays: set[date] = field(default_factory=set)
    employee_positions: dict[str, str] = field(default_factory=dict)

    @property
    def blocking_count(self) -> int:
        return sum(not item.finalizable for item in self.calculations) + len(self.import_result.issues)

    @property
    def total_deduction(self) -> Decimal:
        return sum((item.deductions.total for item in self.calculations), ZERO)

    @property
    def finalizable(self) -> bool:
        return self.blocking_count == 0


class AttendanceApplicationService:
    def __init__(
        self,
        parser: FingerScanPdfParser | None = None,
        engine: DeductionEngine | None = None,
    ) -> None:
        self.parser = parser or FingerScanPdfParser()
        self.engine = engine or DeductionEngine()

    def import_pdf(self, path: str | Path) -> RecapSession:
        result = self.parser.parse(path)
        calculations = [self.engine.calculate(entry) for entry in result.entries]
        return RecapSession(result, calculations)

    def recalculate(self, session: RecapSession) -> None:
        session.calculations = [
            self.engine.calculate(
                entry,
                session.overrides.get((entry.employee.finger_id, entry.work_date)),
                is_holiday=entry.work_date in session.holidays,
            )
            for entry in session.import_result.entries
        ]

    def set_override(
        self,
        session: RecapSession,
        finger_id: str,
        work_date: date,
        code: SpecialCode,
        *,
        inpatient: bool = False,
        reason: str = "",
        evidence_path: Path | None = None,
    ) -> None:
        key = (finger_id, work_date)
        if code == SpecialCode.NONE:
            session.overrides.pop(key, None)
        else:
            session.overrides[key] = DayOverride(
                code=code,
                inpatient=inpatient,
                reason=reason.strip(),
                evidence_path=evidence_path,
            )
        self.recalculate(session)

    def set_holiday(self, session: RecapSession, work_date: date, enabled: bool) -> None:
        if enabled:
            session.holidays.add(work_date)
        else:
            session.holidays.discard(work_date)
        self.recalculate(session)
