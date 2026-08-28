from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import pdfplumber

from tpp_finger_scan.domain.models import (
    AttendanceEntry,
    AttendanceState,
    Employee,
    ImportResult,
    Issue,
)


PERIOD_RE = re.compile(
    r"Dari\s+(\d{2})[-/](\d{2})[-/](\d{4})\s+s/?d\s+"
    r"(\d{2})[-/](\d{2})[-/](\d{4})",
    re.IGNORECASE,
)
DATE_LABEL_RE = re.compile(r"^\d{2}/\d{2}$")
IDENTITY_RE = re.compile(r"^(.*?)\(\s*([\d\s]+)\s*\)\s*$")
COMPLETE_RE = re.compile(r"^(\d{2}:\d{2})-(\d{2}:\d{2})$")
MISSING_OUT_RE = re.compile(r"^(\d{2}:\d{2})-$")
MISSING_IN_RE = re.compile(r"^-(\d{2}:\d{2})$")


class PdfParseError(ValueError):
    """PDF tidak sesuai format laporan finger scan yang didukung."""


@dataclass(frozen=True, slots=True)
class _IdentityRow:
    employee: Employee
    top: float


class FingerScanPdfParser:
    """Parser deterministik untuk PDF tabular hasil finger scan.

    Parser membaca posisi teks (bukan OCR) sehingga cepat dan tidak mengirim
    dokumen ke layanan internet. PDF hasil scan gambar akan ditolak dengan
    pesan yang jelas dan dapat ditambahkan ke antrean OCR pada tahap berikutnya.
    """

    def parse(self, source: str | Path) -> ImportResult:
        source_path = Path(source).expanduser().resolve()
        if not source_path.is_file():
            raise PdfParseError(f"File tidak ditemukan: {source_path}")
        if source_path.suffix.lower() != ".pdf":
            raise PdfParseError("Dokumen sumber harus berformat PDF.")
        if source_path.stat().st_size == 0:
            raise PdfParseError("File PDF kosong.")

        with pdfplumber.open(source_path) as pdf:
            if not pdf.pages:
                raise PdfParseError("PDF tidak memiliki halaman.")
            first_text = pdf.pages[0].extract_text() or ""
            period_start, period_end = self._extract_period(first_text)
            expected_dates = self._date_range(period_start, period_end)
            expected_labels = [value.strftime("%d/%m") for value in expected_dates]

            employees: list[Employee] = []
            entries: list[AttendanceEntry] = []
            issues: list[Issue] = []
            seen_ids: set[str] = set()

            for page_number, page in enumerate(pdf.pages, start=1):
                words = page.extract_words(
                    x_tolerance=1,
                    y_tolerance=1,
                    keep_blank_chars=False,
                )
                if not words:
                    raise PdfParseError(
                        f"Halaman {page_number} tidak berisi teks yang dapat dibaca. "
                        "Dokumen kemungkinan berupa hasil scan gambar dan memerlukan OCR."
                    )
                date_words = [word for word in words if DATE_LABEL_RE.fullmatch(word["text"])]
                date_words.sort(key=lambda word: float(word["x0"]))
                labels = [word["text"] for word in date_words]
                if labels != expected_labels:
                    raise PdfParseError(
                        f"Kolom tanggal halaman {page_number} tidak cocok dengan periode dokumen. "
                        f"Ditemukan {len(labels)} kolom, diharapkan {len(expected_labels)}."
                    )

                date_centers = [
                    (float(word["x0"]) + float(word["x1"])) / 2 for word in date_words
                ]
                spacing = self._median_spacing(date_centers)
                left_boundary = date_centers[0] - (spacing / 2)
                header_bottom = max(float(word["bottom"]) for word in date_words)
                identity_rows = self._extract_identities(words, left_boundary, header_bottom)
                if not identity_rows:
                    raise PdfParseError(
                        f"Tidak menemukan nama dan ID pegawai pada halaman {page_number}."
                    )

                for index, identity in enumerate(identity_rows):
                    employee = identity.employee
                    if employee.finger_id in seen_ids:
                        issues.append(Issue(
                            "DUPLICATE_FINGER_ID",
                            f"ID finger {employee.finger_id} ({employee.name}) muncul lebih dari sekali.",
                        ))
                    else:
                        employees.append(employee)
                        seen_ids.add(employee.finger_id)

                    next_top = (
                        identity_rows[index + 1].top
                        if index + 1 < len(identity_rows)
                        else float(page.height) + 1
                    )
                    cell_words = [
                        word
                        for word in words
                        if float(word["x1"]) > left_boundary
                        and float(word["top"]) >= identity.top - 1
                        and float(word["top"]) < next_top - 1
                        and not DATE_LABEL_RE.fullmatch(word["text"])
                    ]
                    cells = self._assign_cells(cell_words, date_centers, spacing)
                    for work_date, raw_cell in zip(expected_dates, cells, strict=True):
                        entries.append(self._to_entry(
                            employee=employee,
                            work_date=work_date,
                            raw_cell=raw_cell,
                            page_number=page_number,
                        ))

        return ImportResult(
            source_path=source_path,
            source_sha256=self._sha256(source_path),
            period_start=period_start,
            period_end=period_end,
            employees=employees,
            entries=entries,
            issues=issues,
        )

    @staticmethod
    def _extract_period(text: str) -> tuple[date, date]:
        flattened = " ".join(text.split())
        match = PERIOD_RE.search(flattened)
        if not match:
            raise PdfParseError(
                "Periode 'Dari ... s/d ...' tidak ditemukan pada halaman pertama."
            )
        day1, month1, year1, day2, month2, year2 = map(int, match.groups())
        try:
            start = date(year1, month1, day1)
            end = date(year2, month2, day2)
        except ValueError as exc:
            raise PdfParseError(f"Periode PDF tidak valid: {exc}") from exc
        if end < start:
            raise PdfParseError("Tanggal akhir periode lebih kecil dari tanggal awal.")
        if (end - start).days > 62:
            raise PdfParseError("Periode lebih dari 63 hari tidak didukung untuk satu impor.")
        return start, end

    @staticmethod
    def _date_range(start: date, end: date) -> list[date]:
        return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]

    @staticmethod
    def _median_spacing(centers: list[float]) -> float:
        if len(centers) < 2:
            raise PdfParseError("PDF harus memiliki sedikitnya dua kolom tanggal.")
        gaps = sorted(b - a for a, b in zip(centers, centers[1:]))
        return gaps[len(gaps) // 2]

    def _extract_identities(
        self,
        words: list[dict[str, Any]],
        left_boundary: float,
        header_bottom: float,
    ) -> list[_IdentityRow]:
        left_words = [
            word
            for word in words
            if float(word["x0"]) < left_boundary
            and float(word["top"]) > header_bottom + 2
            and word["text"].strip().lower() not in {"nama", "dprd"}
        ]
        lines = self._group_lines(left_words)
        rows: list[_IdentityRow] = []
        fragments: list[str] = []
        fragment_top: float | None = None

        for top, text in lines:
            cleaned = " ".join(text.split())
            if not cleaned:
                continue
            if fragment_top is None:
                fragment_top = top
            fragments.append(cleaned)
            combined = " ".join(fragments)
            match = IDENTITY_RE.fullmatch(combined)
            if not match:
                continue
            name = re.sub(r"^DPRD\s+", "", match.group(1), flags=re.IGNORECASE).strip()
            finger_id = re.sub(r"\s+", "", match.group(2))
            if name and finger_id:
                rows.append(_IdentityRow(Employee(finger_id=finger_id, name=name), fragment_top))
            fragments = []
            fragment_top = None

        return rows

    @staticmethod
    def _group_lines(words: Iterable[dict[str, Any]], tolerance: float = 2.5) -> list[tuple[float, str]]:
        sorted_words = sorted(words, key=lambda word: (float(word["top"]), float(word["x0"])))
        groups: list[list[dict[str, Any]]] = []
        for word in sorted_words:
            if not groups or abs(float(word["top"]) - float(groups[-1][0]["top"])) > tolerance:
                groups.append([word])
            else:
                groups[-1].append(word)
        result: list[tuple[float, str]] = []
        for group in groups:
            group.sort(key=lambda word: float(word["x0"]))
            result.append((
                min(float(word["top"]) for word in group),
                " ".join(word["text"] for word in group),
            ))
        return result

    @staticmethod
    def _assign_cells(
        words: list[dict[str, Any]],
        date_centers: list[float],
        spacing: float,
    ) -> list[str]:
        tokens: dict[int, list[dict[str, Any]]] = defaultdict(list)
        max_distance = spacing * 0.62
        for word in words:
            center = (float(word["x0"]) + float(word["x1"])) / 2
            index = min(range(len(date_centers)), key=lambda i: abs(date_centers[i] - center))
            if abs(date_centers[index] - center) <= max_distance:
                tokens[index].append(word)

        cells: list[str] = []
        for index in range(len(date_centers)):
            ordered = sorted(
                tokens.get(index, []),
                key=lambda word: (float(word["top"]), float(word["x0"])),
            )
            cells.append("".join(word["text"] for word in ordered).replace(" ", ""))
        return cells

    @staticmethod
    def _to_entry(
        employee: Employee,
        work_date: date,
        raw_cell: str,
        page_number: int,
    ) -> AttendanceEntry:
        raw = raw_cell.strip()
        if raw in {"", "-"}:
            return AttendanceEntry(
                employee, work_date, raw, None, None,
                AttendanceState.MISSING_BOTH, page_number,
            )
        complete = COMPLETE_RE.fullmatch(raw)
        if complete:
            in_time = FingerScanPdfParser._parse_time(complete.group(1))
            out_time = FingerScanPdfParser._parse_time(complete.group(2))
            if in_time is not None and out_time is not None:
                return AttendanceEntry(
                    employee, work_date, raw, in_time, out_time,
                    AttendanceState.COMPLETE, page_number,
                )
        missing_out = MISSING_OUT_RE.fullmatch(raw)
        if missing_out:
            in_time = FingerScanPdfParser._parse_time(missing_out.group(1))
            if in_time is not None:
                return AttendanceEntry(
                    employee, work_date, raw, in_time, None,
                    AttendanceState.MISSING_OUT, page_number,
                )
        missing_in = MISSING_IN_RE.fullmatch(raw)
        if missing_in:
            out_time = FingerScanPdfParser._parse_time(missing_in.group(1))
            if out_time is not None:
                return AttendanceEntry(
                    employee, work_date, raw, None, out_time,
                    AttendanceState.MISSING_IN, page_number,
                )
        return AttendanceEntry(
            employee, work_date, raw, None, None,
            AttendanceState.INVALID, page_number, Decimal("0.00"),
        )

    @staticmethod
    def _parse_time(value: str):
        try:
            return datetime.strptime(value, "%H:%M").time()
        except ValueError:
            return None

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
