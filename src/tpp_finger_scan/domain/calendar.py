from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time


DAY_NAMES_ID = (
    "Senin",
    "Selasa",
    "Rabu",
    "Kamis",
    "Jumat",
    "Sabtu",
    "Minggu",
)


@dataclass(frozen=True, slots=True)
class WorkSchedule:
    start: time
    end: time
    workday: bool


def day_name_id(value: date) -> str:
    return DAY_NAMES_ID[value.weekday()]


def schedule_for(value: date) -> WorkSchedule:
    if value.weekday() <= 3:
        return WorkSchedule(time(7, 30), time(16, 45), True)
    if value.weekday() == 4:
        return WorkSchedule(time(7, 30), time(12, 0), True)
    return WorkSchedule(time(0, 0), time(0, 0), False)

