from __future__ import annotations

import hashlib
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from importlib.resources import files
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
    r"Dar[iIl1]\s*:?\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{4})"
    r"\s+s\s*[/\\|Il1]?\s*d\s*:?\s*"
    r"(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{4})",
    re.IGNORECASE,
)
FULL_DATE_RE = re.compile(
    r"(?<!\d)(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{4})(?!\d)"
)
DATE_LABEL_RE = re.compile(r"^(\d{1,2})\s*[-/.]\s*(\d{1,2})$")
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


@dataclass(frozen=True, slots=True)
class _PageData:
    text: str
    words: list[dict[str, Any]]
    from_ocr: bool = False


class FingerScanPdfParser:
    """Parser posisi untuk PDF teks dan PDF scan dengan OCR lokal.

    Lapisan teks asli selalu dipakai lebih dahulu. OCR PyMuPDF/Tesseract hanya
    dijalankan pada halaman scan atau halaman yang kolom tanggalnya tidak dapat
    dibaca. Dokumen tidak pernah dikirim ke layanan internet.
    """

    def parse(self, source: str | Path) -> ImportResult:
        source_path = Path(source).expanduser().resolve()
        if not source_path.is_file():
            raise PdfParseError(f"File tidak ditemukan: {source_path}")
        if source_path.suffix.lower() != ".pdf":
            raise PdfParseError("Dokumen sumber harus berformat PDF.")
        if source_path.stat().st_size == 0:
            raise PdfParseError("File PDF kosong.")

        ocr_document = None

        def ocr_page(index: int) -> _PageData:
            nonlocal ocr_document
            if ocr_document is None:
                try:
                    import fitz
                    ocr_document = fitz.open(source_path)
                except Exception as exc:
                    raise PdfParseError(f"PDF tidak dapat dibuka oleh mesin OCR lokal: {exc}") from exc
            return self._ocr_page_data(ocr_document[index])

        try:
            with pdfplumber.open(source_path) as pdf:
                if not pdf.pages:
                    raise PdfParseError("PDF tidak memiliki halaman.")
                first_page = self._native_page_data(pdf.pages[0])
                try:
                    period_start, period_end = self._extract_period(first_page.text)
                except PdfParseError:
                    first_page = ocr_page(0)
                    period_start, period_end = self._extract_period(first_page.text)
                expected_dates = self._date_range(period_start, period_end)
                expected_labels = [value.strftime("%d/%m") for value in expected_dates]

                employees: list[Employee] = []
                entries: list[AttendanceEntry] = []
                issues: list[Issue] = []
                seen_ids: set[str] = set()

                for page_number, page in enumerate(pdf.pages, start=1):
                    page_data = (
                        first_page
                        if page_number == 1
                        else self._native_page_data(page)
                    )
                    date_words = self._date_words(page_data.words)
                    labels = [word["text"] for word in date_words]
                    if labels != expected_labels and not page_data.from_ocr:
                        ocr_candidate = ocr_page(page_number - 1)
                        candidate_dates = self._date_words(ocr_candidate.words)
                        candidate_labels = [word["text"] for word in candidate_dates]
                        if (
                            candidate_labels == expected_labels
                            or not page_data.words
                            or len(candidate_dates) > len(date_words)
                        ):
                            page_data = ocr_candidate
                            date_words = candidate_dates
                            labels = candidate_labels
                    words = page_data.words
                    if not words:
                        raise PdfParseError(
                            f"Halaman {page_number} tidak berisi teks yang dapat dibaca, "
                            "termasuk setelah OCR lokal."
                        )
                    date_words.sort(key=lambda word: float(word["x0"]))
                    if labels != expected_labels:
                        source_kind = "OCR" if page_data.from_ocr else "lapisan teks PDF"
                        raise PdfParseError(
                            f"Kolom tanggal halaman {page_number} tidak cocok dengan periode dokumen "
                            f"setelah membaca {source_kind}. Ditemukan {len(labels)} kolom, "
                            f"diharapkan {len(expected_labels)}. Pastikan scan lurus dan tajam."
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
                            f"Tidak menemukan nama dan ID pegawai pada halaman {page_number}. "
                            "Pastikan scan tidak terpotong dan tulisan cukup tajam."
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
                            and self._normalize_date_label(str(word["text"])) is None
                        ]
                        cells = self._assign_cells(cell_words, date_centers, spacing)
                        for work_date, raw_cell in zip(expected_dates, cells, strict=True):
                            entries.append(self._to_entry(
                                employee=employee,
                                work_date=work_date,
                                raw_cell=raw_cell,
                                page_number=page_number,
                            ))
        finally:
            if ocr_document is not None:
                ocr_document.close()

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
        groups: tuple[str, ...] | None = match.groups() if match else None
        if groups is None and re.search(r"\bDar[iIl1]\b", flattened, re.IGNORECASE):
            dates = FULL_DATE_RE.findall(flattened)
            if len(dates) >= 2:
                groups = (*dates[0], *dates[1])
        if groups is None:
            raise PdfParseError(
                "Periode 'Dari ... s/d ...' tidak ditemukan pada halaman pertama, "
                "termasuk setelah pembacaan OCR jika dokumen berupa hasil scan."
            )
        day1, month1, year1, day2, month2, year2 = map(int, groups)
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
    def _native_page_data(page) -> _PageData:
        words = page.extract_words(
            x_tolerance=1,
            y_tolerance=1,
            keep_blank_chars=False,
        )
        return _PageData(page.extract_text() or "", list(words or []), False)

    @staticmethod
    def _tessdata_path() -> str:
        candidates: list[str] = []
        try:
            packaged = files("tpp_finger_scan.resources").joinpath("tessdata")
            candidates.append(str(packaged))
        except (ModuleNotFoundError, TypeError):
            pass
        candidates.extend((
            str(Path.cwd()),
            str(Path(__file__).resolve().parents[3]),
        ))
        if os.environ.get("TESSDATA_PREFIX"):
            candidates.append(os.environ["TESSDATA_PREFIX"])
        try:
            import fitz
            candidates.append(str(fitz.get_tessdata()))
        except Exception:
            pass
        for root in (
            os.environ.get("PROGRAMFILES", ""),
            os.environ.get("PROGRAMFILES(X86)", ""),
        ):
            if root:
                candidates.append(str(Path(root) / "Tesseract-OCR" / "tessdata"))
        for candidate in dict.fromkeys(candidates):
            if candidate and (Path(candidate) / "eng.traineddata").is_file():
                return candidate
        raise PdfParseError(
            "PDF ini berupa hasil scan dan memerlukan data OCR offline 'eng.traineddata'. "
            "Instal Tesseract OCR lokal atau letakkan eng.traineddata pada folder "
            "tpp_finger_scan/resources/tessdata, lalu buka kembali aplikasi."
        )

    def _ocr_page_data(self, page) -> _PageData:
        try:
            text_page = page.get_textpage_ocr(
                language="eng",
                dpi=300,
                full=True,
                tessdata=self._tessdata_path(),
            )
            raw_words = page.get_text("words", textpage=text_page, sort=True)
            text = page.get_text("text", textpage=text_page, sort=True)
        except PdfParseError:
            raise
        except Exception as exc:
            raise PdfParseError(
                f"OCR lokal tidak dapat membaca halaman {page.number + 1}: {exc}"
            ) from exc
        words = [
            {
                "x0": float(word[0]),
                "top": float(word[1]),
                "x1": float(word[2]),
                "bottom": float(word[3]),
                "text": str(word[4]),
            }
            for word in raw_words
            if len(word) >= 5 and str(word[4]).strip()
        ]
        return _PageData(text or "", words, True)

    @staticmethod
    def _normalize_date_label(value: str) -> str | None:
        compact = value.strip().strip("|[](){}")
        if not any(character.isdigit() for character in compact):
            return None
        compact = compact.translate(str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"}))
        match = DATE_LABEL_RE.fullmatch(compact)
        if not match:
            return None
        day, month = map(int, match.groups())
        if not 1 <= day <= 31 or not 1 <= month <= 12:
            return None
        return f"{day:02d}/{month:02d}"

    @classmethod
    def _date_words(cls, words: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for word in words:
            normalized = cls._normalize_date_label(str(word.get("text", "")))
            if normalized is not None:
                result.append({**word, "text": normalized})
        result.sort(key=lambda word: float(word["x0"]))
        return result

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
        raw = raw_cell.strip().upper()
        raw = raw.translate(str.maketrans({"‒": "-", "–": "-", "—": "-", "―": "-"}))
        raw = re.sub(r"(?<=\d)[.;](?=\d{2})", ":", raw)
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
