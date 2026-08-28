from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


MONTHS_ID = (
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)
DAYS_ID = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")


def format_date_id(value: date | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return f"{value.day} {MONTHS_ID[value.month]} {value.year}"


def day_name_id(value: date) -> str:
    return DAYS_ID[value.weekday()]


def inclusive_days(start: date, end: date) -> int:
    return max(1, (end - start).days + 1)


def terbilang_small(number: int) -> str:
    words = (
        "Nol", "Satu", "Dua", "Tiga", "Empat", "Lima", "Enam", "Tujuh",
        "Delapan", "Sembilan", "Sepuluh", "Sebelas",
    )
    if 0 <= number < len(words):
        return words[number]
    if number < 20:
        return f"{words[number - 10]} Belas"
    if number < 100:
        remainder = number % 10
        return f"{words[number // 10]} Puluh" + (f" {words[remainder]}" if remainder else "")
    return str(number)


@dataclass(slots=True)
class TravelFormData:
    mode: str
    document_numbers: dict[str, str]
    letter_date: date
    start_date: date
    end_date: date
    travel_type: str
    basis_dprd: str
    basis_asn: str
    subject: str
    notice_subject: str
    destinations: list[str]
    signer_dprd: str
    signer_asn: str
    dprd: list[dict[str, Any]] = field(default_factory=list)
    asn: list[dict[str, Any]] = field(default_factory=list)
    executors: list[dict[str, Any]] = field(default_factory=list)
    companions: list[dict[str, Any]] = field(default_factory=list)

    def validate(self) -> None:
        if self.mode not in {"dprd", "setwan"}:
            raise ValueError("Mode perjalanan dinas tidak valid.")
        if self.end_date < self.start_date:
            raise ValueError("Tanggal selesai tidak boleh sebelum tanggal mulai.")
        if not self.subject.strip():
            raise ValueError("Materi/agenda kegiatan wajib diisi.")
        if not self.destinations:
            raise ValueError("Tambahkan minimal satu tujuan perjalanan.")
        if self.mode == "dprd" and not (self.dprd or self.asn):
            raise ValueError("Pilih minimal satu anggota DPRD atau pendamping ASN.")
        if self.mode == "setwan" and not (self.executors or self.companions):
            raise ValueError("Pilih minimal satu pelaksana atau pendamping ASN.")

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("letter_date", "start_date", "end_date"):
            payload[key] = getattr(self, key).isoformat()
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "TravelFormData":
        data = dict(payload)
        for key in ("letter_date", "start_date", "end_date"):
            data[key] = date.fromisoformat(str(data[key]))
        return cls(**data)


@dataclass(slots=True)
class InvitationFormData:
    invitation_type: str
    number: str
    letter_date: date
    meeting_date: date
    time_text: str
    agenda: str
    signer: str
    clothing: str = "PSH"
    scenarios: list[str] = field(default_factory=list)
    meeting_executor: str = ""
    meeting_type: str = ""
    related_parties: list[str] = field(default_factory=list)
    other_destination_pages: list[list[str]] = field(default_factory=list)
    include_official_note: bool = False
    include_attendance: bool = False
    include_related_attendance: bool = True
    include_secretariat_attendance: bool = False

    def validate(self) -> None:
        if self.invitation_type not in {"paripurna", "biasa"}:
            raise ValueError("Jenis undangan tidak valid.")
        if not self.number.strip():
            raise ValueError("Nomor undangan wajib diisi.")
        if not self.agenda.strip():
            raise ValueError("Isi surat/agenda rapat wajib diisi.")
        if not self.time_text.strip():
            raise ValueError("Jam pelaksanaan wajib diisi.")
        if self.invitation_type == "biasa" and not self.meeting_executor.strip():
            raise ValueError("Pelaksana rapat wajib diisi.")

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["letter_date"] = self.letter_date.isoformat()
        payload["meeting_date"] = self.meeting_date.isoformat()
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "InvitationFormData":
        data = dict(payload)
        data["letter_date"] = date.fromisoformat(str(data["letter_date"]))
        data["meeting_date"] = date.fromisoformat(str(data["meeting_date"]))
        return cls(**data)


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    record_id: str
    record_type: str
    title: str
    document_number: str
    document_date: str
    event_start: str
    event_end: str
    destination: str
    status: str
    author: str
    payload: dict[str, Any]
    files: list[str]
    created_at: str
    updated_at: str

    @property
    def category(self) -> str:
        return "travel" if self.record_type.startswith("travel_") else "invitation"


def new_record_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
