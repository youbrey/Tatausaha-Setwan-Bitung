from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal
from enum import StrEnum
from pathlib import Path


ZERO = Decimal("0.00")


class AttendanceState(StrEnum):
    COMPLETE = "COMPLETE"
    MISSING_IN = "MISSING_IN"
    MISSING_OUT = "MISSING_OUT"
    MISSING_BOTH = "MISSING_BOTH"
    INVALID = "INVALID"


class SpecialCode(StrEnum):
    NONE = ""
    TL = "TL"
    WFH = "WFH"
    W = "W"
    I = "I"
    S = "S"


class IssueSeverity(StrEnum):
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


@dataclass(frozen=True, slots=True)
class Employee:
    finger_id: str
    name: str


@dataclass(frozen=True, slots=True)
class AttendanceEntry:
    employee: Employee
    work_date: date
    raw_cell: str
    in_time: time | None
    out_time: time | None
    state: AttendanceState
    source_page: int
    confidence: Decimal = Decimal("1.00")


@dataclass(frozen=True, slots=True)
class DayOverride:
    code: SpecialCode = SpecialCode.NONE
    inpatient: bool = False
    reason: str = ""
    evidence_path: Path | None = None


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    message: str
    severity: IssueSeverity = IssueSeverity.BLOCKING


@dataclass(frozen=True, slots=True)
class DeductionBreakdown:
    late: Decimal = ZERO
    early: Decimal = ZERO
    absence: Decimal = ZERO

    @property
    def total(self) -> Decimal:
        return self.late + self.early + self.absence


@dataclass(frozen=True, slots=True)
class DayCalculation:
    entry: AttendanceEntry
    deductions: DeductionBreakdown
    status: str
    issues: tuple[Issue, ...] = ()
    highlight_yellow: bool = False

    @property
    def finalizable(self) -> bool:
        return not any(issue.severity == IssueSeverity.BLOCKING for issue in self.issues)


@dataclass(slots=True)
class ImportResult:
    source_path: Path
    source_sha256: str
    period_start: date
    period_end: date
    employees: list[Employee]
    entries: list[AttendanceEntry]
    issues: list[Issue] = field(default_factory=list)

    @property
    def page_employee_count(self) -> int:
        return len(self.employees)

    @property
    def date_count(self) -> int:
        return (self.period_end - self.period_start).days + 1
