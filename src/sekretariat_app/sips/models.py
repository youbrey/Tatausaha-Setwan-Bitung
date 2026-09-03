from __future__ import annotations

import uuid
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


MONTHS_ID = (
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)
DAYS_ID = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")


def normalize_form_value(value: object) -> str:
    """Rapikan nilai form dan abaikan placeholder kosong berbentuk garis.

    Operator lazim memakai ``-`` untuk menandai kolom yang tidak digunakan.
    Nilai seperti itu bukan nomor, dasar, atau materi yang sengaja diisi dan
    karena itu tidak boleh ikut ke indeks pemeriksaan duplikasi.
    """
    text = " ".join(str(value or "").split())
    if not text or re.fullmatch(r"[-\u2012\u2013\u2014\u2015\s]+", text):
        return ""
    return text


def has_form_value(value: object) -> bool:
    return bool(normalize_form_value(value))


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

    def validate_preview(self) -> None:
        """Validasi minimum agar Live Preview dapat dirender saat form diisi."""
        if self.mode not in {"dprd", "setwan"}:
            raise ValueError("Mode perjalanan dinas tidak valid.")
        if self.end_date < self.start_date:
            raise ValueError("Tanggal selesai tidak boleh sebelum tanggal mulai.")
        if not has_form_value(self.travel_type):
            raise ValueError("Jenis perjalanan wajib dipilih.")
        if not has_form_value(self.subject):
            raise ValueError("Materi/agenda kegiatan wajib diisi.")
        if not self.destinations:
            raise ValueError("Tambahkan minimal satu tujuan perjalanan.")
        if self.mode == "dprd" and not (self.dprd or self.asn):
            raise ValueError("Pilih minimal satu anggota DPRD atau pendamping ASN.")
        if self.mode == "setwan" and not (self.executors or self.companions):
            raise ValueError("Pilih minimal satu pelaksana atau pendamping ASN.")

    def required_document_numbers(self) -> dict[str, str]:
        """Nomor yang benar-benar dipakai oleh cabang dokumen terpilih."""
        required: dict[str, str] = {}
        if self.mode == "dprd":
            if self.dprd:
                required.update({
                    "surat_tugas_dprd": "Surat Tugas DPRD",
                    "spd_dprd": "SPD DPRD",
                })
            if self.asn:
                required.update({
                    "surat_tugas_asn": "Surat Tugas Pendamping ASN",
                    "spd_asn": "SPD Pendamping ASN",
                })
            if self.dprd or self.asn:
                required["pemberitahuan_dprd"] = "Surat Pemberitahuan DPRD"
        else:
            required.update({
                "surat_tugas_asn": "Surat Tugas Setwan",
                "pemberitahuan_asn": "Surat Pemberitahuan Setwan",
            })
            if self.executors:
                required["spd_pelaksana"] = "SPD Pelaksana ASN"
            if self.companions:
                required["spd_pendamping"] = "SPD Pendamping ASN"
        return required

    def validate(self) -> None:
        """Validasi final sebelum seluruh surat dibuat dan dicatat."""
        self.validate_preview()
        missing_numbers = [
            label
            for key, label in self.required_document_numbers().items()
            if not has_form_value(self.document_numbers.get(key, ""))
        ]
        if missing_numbers:
            raise ValueError("Nomor dokumen wajib diisi: " + ", ".join(missing_numbers) + ".")
        if not has_form_value(self.notice_subject):
            raise ValueError("Isi Surat Pemberitahuan wajib diisi.")
        if self.mode == "dprd" and self.dprd:
            if not has_form_value(self.basis_dprd):
                raise ValueError("Dasar Surat Tugas DPRD wajib diisi.")
            if not has_form_value(self.signer_dprd):
                raise ValueError("Penandatangan DPRD wajib dipilih.")
        if (self.mode == "dprd" and self.asn) or self.mode == "setwan":
            if not has_form_value(self.basis_asn):
                raise ValueError("Dasar Surat Tugas ASN wajib diisi.")
            if not has_form_value(self.signer_asn):
                raise ValueError("Penandatangan ASN/SPD wajib dipilih.")

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

    def validate_preview(self) -> None:
        """Validasi minimum agar Live Preview tidak menunggu nomor final."""
        if self.invitation_type not in {"paripurna", "biasa"}:
            raise ValueError("Jenis undangan tidak valid.")
        if not has_form_value(self.agenda):
            raise ValueError("Isi surat/agenda rapat wajib diisi.")
        if not has_form_value(self.time_text):
            raise ValueError("Jam pelaksanaan wajib diisi.")
        if self.invitation_type == "biasa" and not has_form_value(self.meeting_executor):
            raise ValueError("Pelaksana rapat wajib diisi.")

    def validate(self) -> None:
        """Validasi final undangan dan dokumen pendukung yang dipilih."""
        self.validate_preview()
        if not has_form_value(self.number):
            raise ValueError("Nomor undangan wajib diisi.")
        if not has_form_value(self.signer):
            raise ValueError("Penandatangan undangan wajib dipilih.")
        if self.invitation_type == "paripurna":
            if not self.clothing.strip():
                raise ValueError("Pakaian rapat paripurna wajib dipilih.")
            if len(self.scenarios) > 7:
                raise ValueError("Skenario rapat paripurna maksimal tujuh item.")
        else:
            if not self.meeting_type.strip():
                raise ValueError("Jenis rapat wajib diisi.")

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
        if data.get("meeting_type") == "RDPU (Rapat Dengar Pendapat Umum)":
            data["meeting_type"] = "Rapat Dengar Pendapat Umum (RDPU)"
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
