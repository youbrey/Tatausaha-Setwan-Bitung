from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import subprocess
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


@dataclass(frozen=True, slots=True)
class _PixelBand:
    start: int
    end: int
    peak: int
    score: int


@dataclass(frozen=True, slots=True)
class _ScanGrid:
    name_left: int
    date_boundaries: tuple[int, ...]
    header_top: _PixelBand
    header_bottom: _PixelBand
    row_bands: tuple[_PixelBand, ...]


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
        ocr_pages: dict[int, _PageData] = {}
        table_pages: dict[int, _PageData] = {}

        def ocr_page(index: int) -> _PageData:
            nonlocal ocr_document
            if ocr_document is None:
                try:
                    import fitz
                    ocr_document = fitz.open(source_path)
                except Exception as exc:
                    raise PdfParseError(f"PDF tidak dapat dibuka oleh mesin OCR lokal: {exc}") from exc
            if index not in ocr_pages:
                ocr_pages[index] = self._ocr_page_data(ocr_document[index])
            return ocr_pages[index]

        def table_page(index: int, labels: list[str]) -> _PageData:
            nonlocal ocr_document
            if ocr_document is None:
                try:
                    import fitz
                    ocr_document = fitz.open(source_path)
                except Exception as exc:
                    raise PdfParseError(f"PDF tidak dapat dibuka oleh mesin OCR lokal: {exc}") from exc
            if index not in table_pages:
                table_pages[index] = self._ocr_table_page_data(
                    ocr_document[index], labels
                )
            return table_pages[index]

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
                    if labels != expected_labels:
                        # CamScanner and similar apps usually store one large
                        # image. Full-page OCR often merges the narrow date
                        # headers with table borders. Reconstruct the grid from
                        # the pixels, then OCR every identity row and occupied
                        # attendance cell independently.
                        table_candidate = table_page(page_number - 1, expected_labels)
                        table_dates = self._date_words(table_candidate.words)
                        table_labels = [word["text"] for word in table_dates]
                        if table_labels == expected_labels:
                            page_data = table_candidate
                            date_words = table_dates
                            labels = table_labels
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
    def _projection_bands(
        image,
        *,
        axis: str,
        start: int,
        end: int,
        cross_start: int,
        cross_end: int,
        minimum_ratio: float,
        merge_gap: int = 1,
    ) -> list[_PixelBand]:
        """Find dark horizontal/vertical strokes using Pillow's C histogram."""
        length = max(1, cross_end - cross_start)
        matches: list[tuple[int, int]] = []
        for coordinate in range(max(0, start), min(end, image.height if axis == "row" else image.width)):
            if axis == "row":
                strip = image.crop((cross_start, coordinate, cross_end, coordinate + 1))
            else:
                strip = image.crop((coordinate, cross_start, coordinate + 1, cross_end))
            score = strip.histogram()[0]
            if score >= length * minimum_ratio:
                matches.append((coordinate, score))

        groups: list[list[tuple[int, int]]] = []
        for coordinate, score in matches:
            if not groups or coordinate > groups[-1][-1][0] + merge_gap + 1:
                groups.append([])
            groups[-1].append((coordinate, score))
        return [
            _PixelBand(
                group[0][0],
                group[-1][0],
                max(group, key=lambda item: item[1])[0],
                max(score for _coordinate, score in group),
            )
            for group in groups
        ]

    @staticmethod
    def _regular_run(bands: list[_PixelBand], required: int) -> tuple[int, ...] | None:
        if required < 2 or len(bands) < required:
            return None
        best: tuple[float, tuple[int, ...]] | None = None
        for start in range(len(bands) - required + 1):
            values = tuple(band.peak for band in bands[start : start + required])
            gaps = [right - left for left, right in zip(values, values[1:])]
            ordered = sorted(gaps)
            median = ordered[len(ordered) // 2]
            if median < 8:
                continue
            deviations = [abs(gap - median) / median for gap in gaps]
            if max(deviations, default=1.0) > 0.22:
                continue
            score = sum(deviations) / len(deviations)
            if best is None or score < best[0]:
                best = (score, values)
        return best[1] if best else None

    @classmethod
    def _detect_scan_grid(cls, binary, date_count: int, dpi: int) -> _ScanGrid:
        width, height = binary.size
        horizontal = cls._projection_bands(
            binary,
            axis="row",
            start=round(height * 0.05),
            end=round(height * 0.45),
            cross_start=round(width * 0.015),
            cross_end=round(width * 0.985),
            minimum_ratio=0.60,
            merge_gap=max(2, round(dpi / 90)),
        )
        selected: tuple[_PixelBand, _PixelBand, list[_PixelBand], tuple[int, ...]] | None = None
        for top_index, top in enumerate(horizontal):
            for bottom in horizontal[top_index + 1 : top_index + 6]:
                gap = bottom.start - top.end
                if gap < dpi * 0.08 or gap > dpi * 0.45:
                    continue
                vertical = cls._projection_bands(
                    binary,
                    axis="column",
                    start=round(width * 0.01),
                    end=round(width * 0.99),
                    cross_start=top.end + 1,
                    cross_end=bottom.start,
                    minimum_ratio=0.62,
                    merge_gap=max(1, round(dpi / 180)),
                )
                run = cls._regular_run(vertical, date_count + 1)
                if run is not None:
                    selected = (top, bottom, vertical, run)
                    break
            if selected is not None:
                break
        if selected is None:
            raise PdfParseError(
                f"Garis tabel scan tidak dapat direkonstruksi untuk {date_count} kolom tanggal. "
                "Pastikan seluruh tabel terlihat, lurus, dan tidak terpotong."
            )

        header_top, header_bottom, vertical, date_boundaries = selected
        spacing = sorted(
            right - left
            for left, right in zip(date_boundaries, date_boundaries[1:])
        )[date_count // 2]
        name_candidates = [
            band.peak
            for band in vertical
            if 2.5 * spacing <= date_boundaries[0] - band.peak <= 8.0 * spacing
        ]
        name_left = min(name_candidates) if name_candidates else max(
            0, round(date_boundaries[0] - 3.5 * spacing)
        )

        row_scores: list[int] = []
        table_left = max(0, name_left)
        table_right = min(width, date_boundaries[-1] + max(2, round(dpi / 80)))
        for y in range(height):
            row_scores.append(
                binary.crop((table_left, y, table_right, y + 1)).histogram()[0]
            )
        rows = cls._projection_bands(
            binary,
            axis="row",
            start=header_bottom.start,
            end=round(height * 0.985),
            cross_start=table_left,
            cross_end=table_right,
            minimum_ratio=0.43,
            merge_gap=max(3, round(dpi / 32)),
        )
        rows = [row for row in rows if row.start > header_bottom.end + 2]
        rows = cls._recover_weak_row_bands(rows, row_scores, header_bottom, height, dpi)
        if len(rows) < 3:
            raise PdfParseError(
                "Baris pegawai pada tabel scan tidak dapat dideteksi. Pastikan garis tabel cukup tajam."
            )
        return _ScanGrid(
            name_left=name_left,
            date_boundaries=date_boundaries,
            header_top=header_top,
            header_bottom=header_bottom,
            row_bands=tuple(rows),
        )

    @staticmethod
    def _recover_weak_row_bands(
        rows: list[_PixelBand],
        row_scores: list[int],
        header_bottom: _PixelBand,
        image_height: int,
        dpi: int,
    ) -> list[_PixelBand]:
        if not rows:
            return rows
        gaps = [
            right.peak - left.peak
            for left, right in zip(rows, rows[1:])
            if dpi * 0.18 <= right.peak - left.peak <= dpi * 0.43
        ]
        if not gaps:
            return rows
        typical = sorted(gaps)[len(gaps) // 2]
        result: list[_PixelBand] = []
        virtual_end = _PixelBand(
            round(image_height * 0.98),
            round(image_height * 0.98),
            round(image_height * 0.98),
            0,
        )
        for left, right in zip(rows, rows[1:] + [virtual_end]):
            result.append(left)
            gap = right.peak - left.peak
            if gap <= typical * 1.55:
                continue
            missing = max(1, round(gap / typical) - 1)
            for number in range(1, missing + 1):
                target = round(left.peak + gap * number / (missing + 1))
                radius = max(4, round(typical * 0.28))
                low = max(header_bottom.end + 1, target - radius)
                high = min(image_height - 1, target + radius)
                peak = max(range(low, high + 1), key=row_scores.__getitem__)
                peak_score = row_scores[peak]
                if peak_score <= 0:
                    continue
                threshold = peak_score * 0.68
                start = peak
                end = peak
                while start > low and row_scores[start - 1] >= threshold:
                    start -= 1
                while end < high and row_scores[end + 1] >= threshold:
                    end += 1
                result.append(_PixelBand(start, end, peak, peak_score))
        result.sort(key=lambda band: band.peak)
        return result

    @staticmethod
    def _tesseract_executable() -> str | None:
        explicit = os.environ.get("TESSERACT_CMD", "").strip()
        candidates = [explicit, shutil.which("tesseract") or ""]
        for root in (
            os.environ.get("PROGRAMFILES", ""),
            os.environ.get("PROGRAMFILES(X86)", ""),
            os.environ.get("LOCALAPPDATA", ""),
        ):
            if root:
                candidates.extend((
                    str(Path(root) / "Tesseract-OCR" / "tesseract.exe"),
                    str(Path(root) / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
                ))
        return next((candidate for candidate in dict.fromkeys(candidates) if candidate and Path(candidate).is_file()), None)

    @classmethod
    def _ocr_region(
        cls,
        image,
        *,
        psm: int = 6,
        whitelist: str = "",
        threshold: bool = False,
    ) -> str:
        from PIL import Image, ImageOps

        prepared = ImageOps.autocontrast(image.convert("L"))
        if threshold:
            prepared = prepared.point(lambda value: 0 if value < 175 else 255)
        target_height = 260 if prepared.width > prepared.height * 1.8 else 320
        scale = max(1.0, min(5.0, target_height / max(1, prepared.height)))
        if scale > 1.05:
            prepared = prepared.resize(
                (
                    max(1, round(prepared.width * scale)),
                    max(1, round(prepared.height * scale)),
                ),
                Image.Resampling.LANCZOS,
            )
        prepared = ImageOps.expand(prepared, border=max(16, round(18 * scale)), fill=255)
        buffer = io.BytesIO()
        prepared.save(buffer, format="PNG")
        payload = buffer.getvalue()
        executable = cls._tesseract_executable()
        if executable:
            command = [
                executable, "stdin", "stdout", "--psm", str(psm),
                "-l", "eng", "--tessdata-dir", cls._tessdata_path(),
            ]
            if whitelist:
                command.extend(("-c", f"tessedit_char_whitelist={whitelist}"))
            try:
                result = subprocess.run(
                    command,
                    input=payload,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    check=True,
                    timeout=20,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return " ".join(result.stdout.decode("utf-8", errors="replace").split())
            except (OSError, subprocess.SubprocessError):
                pass

        # PyMuPDF includes an in-process Tesseract bridge. It is slower for
        # many small regions but keeps scan import working when tesseract.exe
        # is not available beside a frozen application.
        try:
            import fitz
            with fitz.open() as document:
                page = document.new_page(width=prepared.width, height=prepared.height)
                page.insert_image(page.rect, stream=payload)
                text_page = page.get_textpage_ocr(
                    language="eng", dpi=300, full=True, tessdata=cls._tessdata_path()
                )
                return " ".join(
                    page.get_text("text", textpage=text_page, sort=True).split()
                )
        except Exception as exc:
            raise PdfParseError(f"OCR area tabel gagal: {exc}") from exc

    @staticmethod
    def _normalize_ocr_identity(value: str) -> str | None:
        cleaned = " ".join(value.replace("\n", " ").split()).strip(" |_=~-:")
        if not cleaned:
            return None
        cleaned = cleaned.replace("{", "(").replace("[", "(")
        cleaned = cleaned.replace("}", ")").replace("]", ")")
        matches = list(re.finditer(r"\(\s*([\d\s|]+)\s*\)", cleaned))
        if matches:
            match = matches[-1]
            finger_id = re.sub(r"\D", "", match.group(1))
            name = cleaned[: match.start()]
        else:
            match = re.search(r"(?:\(|\b)([\d\s|]{1,16})\)?\s*$", cleaned)
            if not match:
                return None
            finger_id = re.sub(r"\D", "", match.group(1))
            name = cleaned[: match.start()]
        name = re.sub(r"[^0-9A-Za-zÀ-ÿ.' -]+", " ", name)
        name = " ".join(name.split()).strip(" .|_=-")
        if len(name) < 2 or not finger_id or len(finger_id) > 10:
            return None
        return f"{name}({finger_id})"

    @staticmethod
    def _clean_scan_cell(image):
        """Hapus sisa garis tabel pada tepi crop tanpa menyentuh isi sel."""

        from PIL import ImageDraw

        cleaned = image.convert("L").copy()
        width, height = cleaned.size
        pixels = cleaned.load()
        draw = ImageDraw.Draw(cleaned)
        x_margin = max(2, round(width * 0.08))
        y_margin = max(2, round(height * 0.08))
        for x in (*range(x_margin), *range(max(x_margin, width - x_margin), width)):
            dark = sum(pixels[x, y] < 175 for y in range(height))
            if dark >= height * 0.55:
                draw.rectangle((max(0, x - 2), 0, min(width - 1, x + 2), height - 1), fill=255)
        for y in (*range(y_margin), *range(max(y_margin, height - y_margin), height)):
            dark = sum(pixels[x, y] < 175 for x in range(width))
            if dark >= width * 0.65:
                draw.rectangle((0, max(0, y - 2), width - 1, min(height - 1, y + 2)), fill=255)
        return cleaned

    @classmethod
    def _cell_ink_kind(cls, image) -> str:
        from PIL import ImageOps

        ink = ImageOps.invert(cls._clean_scan_cell(image)).point(
            lambda value: 255 if value > 90 else 0
        )
        count = ink.histogram()[255]
        if count < max(9, round(image.width * image.height * 0.0020)):
            return "blank"
        box = ink.getbbox()
        if box:
            width = box[2] - box[0]
            height = box[3] - box[1]
            if height <= max(4, image.height * 0.18) and width <= image.width * 0.72:
                return "dash"
        return "content"

    @staticmethod
    def _normalize_ocr_cell(value: str) -> str:
        cleaned = value.upper().replace("—", "-").replace("–", "-")
        time_matches: list[tuple[str, int, int]] = []
        for match in re.finditer(r"(?<!\d)(\d{1,3})\s*[:.;]\s*([0-5]\d)(?!\d)", cleaned):
            hour_text, minute = match.groups()
            if len(hour_text) == 3 and int(hour_text) > 23:
                hour_text = hour_text[-2:]
            hour = int(hour_text)
            if 0 <= hour <= 23:
                time_matches.append((f"{hour:02d}:{minute}", match.start(), match.end()))
        if len(time_matches) >= 2:
            return f"{time_matches[0][0]}-{time_matches[1][0]}"
        if len(time_matches) == 1:
            value, start, end = time_matches[0]
            if re.search(r"-\s*$", cleaned[end:]):
                return f"{value}-"
            if re.search(r"^\s*-", cleaned[:start]):
                return f"-{value}"
            return value

        # Jangan mengubah noise alfabet pada jam menjadi kode. Misalnya hasil
        # OCR ``08:38- T-`` tetap merupakan satu jam tidak lengkap, bukan TL.
        # Kode khusus hanya boleh berasal dari crop tanpa angka.
        letters = re.sub(r"[^A-Z]", "", cleaned)
        if not any(character.isdigit() for character in cleaned):
            if letters in {"W", "WW"}:
                return "W"
            # Tulisan tangan "TL" sering kehilangan goresan horizontal huruf
            # L dan dibaca T/TT/TE/TW oleh Tesseract.
            if letters in {"T", "TT", "TE", "TI", "TV", "TW"}:
                return "TL"
            if letters in {"WFH", "TL", "I", "S"}:
                return letters
        return "-" if not cleaned.strip(" |_=~.") else cleaned.strip()

    @classmethod
    def _is_recognized_ocr_cell(cls, value: str) -> bool:
        if value in {"-", "W", "WFH", "TL", "I", "S"}:
            return True
        match = COMPLETE_RE.fullmatch(value)
        if match:
            return all(cls._parse_time(part) is not None for part in match.groups())
        match = MISSING_OUT_RE.fullmatch(value) or MISSING_IN_RE.fullmatch(value)
        return bool(match and cls._parse_time(match.group(1)) is not None)

    @classmethod
    def _looks_like_handwritten_code(cls, image) -> bool:
        """Bedakan goresan kode besar dari sel kosong/garis tabel.

        Pemeriksaan ini tidak menentukan arti kode. Ia hanya menandai sel
        dengan tinta besar agar konsensus OCR pada kolom yang sama dapat
        memulihkan ``W``/``TL`` yang kehilangan satu goresan saat dipindai.
        """

        from PIL import ImageOps

        prepared = ImageOps.autocontrast(cls._clean_scan_cell(image))
        ink = prepared.point(lambda value: 255 if value < 165 else 0)
        box = ink.getbbox()
        if not box:
            return False
        width = box[2] - box[0]
        height = box[3] - box[1]
        ink_count = ink.histogram()[255]
        return (
            width >= prepared.width * 0.24
            and height >= prepared.height * 0.28
            and ink_count >= prepared.width * prepared.height * 0.012
            # Dua baris angka tercetak jauh lebih padat daripada goresan
            # tulisan tangan. Batas atas ini mencegah jam yang gagal di-OCR
            # ikut diwarisi sebagai W/TL dari konsensus kolom.
            and ink_count <= prepared.width * prepared.height * 0.13
        )

    @classmethod
    def _ocr_scan_cell(cls, image, *, code_like: bool = False) -> str:
        image = cls._clean_scan_cell(image)
        whitelist = "0123456789:.-/WTLISEKFH"
        # W/TL/WFH memiliki bentuk dan konsensus tanggal yang cukup kuat pada
        # scan. I/S satu goresan terlalu mudah tertukar dengan garis/digit;
        # kandidatnya dipertahankan untuk review, sedangkan PDF bertulisan
        # tetap dapat memakai I/S secara langsung lewat parser native.
        special = {"W", "TL", "WFH"}
        all_special = special | {"I", "S"}
        first_raw = cls._ocr_region(image, psm=6, whitelist=whitelist)
        first = cls._normalize_ocr_cell(first_raw)
        if cls._is_recognized_ocr_cell(first) and first not in all_special | {"-"}:
            return first

        first_has_digits = any(character.isdigit() for character in first_raw)
        if code_like and not first_has_digits:
            # PSM 11 mencari goresan terpisah. Ini penting untuk tulisan
            # tangan ``TL`` yang sering dibaca kosong oleh mode blok karena
            # huruf L tidak menyentuh huruf T.
            candidates = [first]
            for psm, threshold in ((11, False), (6, True)):
                candidate = cls._normalize_ocr_cell(
                    cls._ocr_region(
                        image,
                        psm=psm,
                        whitelist=whitelist,
                        threshold=threshold,
                    )
                )
                candidates.append(candidate)
            votes: dict[str, int] = defaultdict(int)
            for candidate in candidates:
                if candidate in special:
                    votes[candidate] += 1
            if votes:
                candidate, count = max(votes.items(), key=lambda item: item[1])
                # Satu hasil alfabet saja masih mungkin noise dari jam cetak.
                # Dua mode OCR yang sepakat cukup untuk kode tunggal; kandidat
                # lemah tetap disimpan sebagai INVALID dan dapat dipulihkan
                # oleh konsensus kolom tanggal.
                return candidate if count >= 2 else f"?{candidate}"
            return f"?{first}" if first in all_special else first

        if first in all_special:
            return f"?{first}"

        thresholded = cls._normalize_ocr_cell(
            cls._ocr_region(image, psm=6, whitelist=whitelist, threshold=True)
        )
        if cls._is_recognized_ocr_cell(thresholded) and thresholded != "-":
            return f"?{thresholded}" if thresholded in all_special else thresholded

        # Most one-character false positives are fragments of a printed dash.
        # Accept a dash only after a second, binarized OCR pass agrees; retain
        # single-time results as INVALID so the UI asks for human review.
        first_has_time = bool(re.search(r"\d{2}:\d{2}", first))
        if not first_has_time:
            return first

        # Pisahkan dua baris jam berdasarkan proyeksi tinta, bukan titik tengah
        # crop. Scan miring membuat baris pertama sering berada di bawah titik
        # tengah dan terpotong menjadi satu glyph bila dibelah 50:50.
        times = cls._ocr_time_lines(image)
        if len(times) >= 2:
            combined = f"{times[0][0]}-{times[1][0]}"
            if cls._is_recognized_ocr_cell(combined):
                return combined
        if len(times) == 1:
            value, relative_center = times[0]
            return f"{value}-" if relative_center < 0.55 else f"-{value}"
        return first

    @classmethod
    def _ocr_time_lines(cls, image) -> list[tuple[str, float]]:
        from PIL import ImageOps

        prepared = ImageOps.autocontrast(cls._clean_scan_cell(image))
        width, height = prepared.size
        pixels = prepared.load()
        threshold = max(2, round(width * 0.025))
        active = [
            y
            for y in range(height)
            if sum(pixels[x, y] < 180 for x in range(width)) >= threshold
        ]
        groups: list[list[int]] = []
        for y in active:
            if not groups or y > groups[-1][-1] + 4:
                groups.append([])
            groups[-1].append(y)
        bands = [
            (group[0], group[-1])
            for group in groups
            if group[-1] - group[0] >= max(3, round(height * 0.035))
        ]
        if len(bands) > 2:
            bands = sorted(
                sorted(bands, key=lambda band: band[1] - band[0], reverse=True)[:2]
            )
        values: list[tuple[str, float]] = []
        for top, bottom in bands:
            padding = max(4, round((bottom - top + 1) * 0.30))
            line = prepared.crop((0, max(0, top - padding), width, min(height, bottom + padding + 1)))
            raw = cls._ocr_region(
                line,
                psm=7,
                whitelist="0123456789:.-",
            )
            normalized = cls._normalize_ocr_cell(raw)
            matches = re.findall(r"\d{2}:\d{2}", normalized)
            if matches:
                values.append((matches[0], ((top + bottom) / 2) / max(1, height)))
        return values

    @staticmethod
    def _reconcile_special_code_columns(scan_cells: list[dict[str, Any]]) -> None:
        """Pulihkan kode tulisan tangan memakai konsensus satu kolom tanggal.

        Pada laporan finger scan, kode kebijakan umumnya diterapkan kepada
        beberapa pegawai di tanggal yang sama. OCR kuat dari sel lain menjadi
        pembanding, tetapi hanya sel bertinta besar tanpa angka yang boleh
        diperbaiki. Kolom yang campur/ambigu dibiarkan untuk pemeriksaan
        operator sehingga jam tidak pernah ditebak menjadi kode.
        """

        special = {"W", "TL", "WFH", "I", "S"}
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for cell in scan_cells:
            grouped[int(cell["column"])].append(cell)

        for cells in grouped.values():
            counts: dict[str, int] = defaultdict(int)
            for cell in cells:
                raw = str(cell["word"]["text"]).upper()
                if cell["code_like"] and raw in special:
                    counts[raw] += 1
            if not counts:
                continue
            dominant, dominant_count = max(counts.items(), key=lambda item: item[1])
            recognized_count = sum(counts.values())
            runner_up = max(
                (count for code, count in counts.items() if code != dominant),
                default=0,
            )
            strong_consensus = (
                dominant_count / recognized_count >= 0.67
                or (
                    dominant_count >= 3
                    and dominant_count >= runner_up * 1.5
                )
            )
            if dominant_count < 3 or not strong_consensus:
                continue

            for cell in cells:
                raw = str(cell["word"]["text"]).upper()
                if (
                    not cell["code_like"]
                    or (
                        any(character.isdigit() for character in raw)
                        and raw not in {"1"}
                    )
                ):
                    continue
                if raw not in special or (
                    raw != dominant
                    and dominant_count >= 3
                    and dominant_count >= counts.get(raw, 0) * 2
                ):
                    cell["word"]["text"] = dominant
                    cell["word"]["ocr_inferred"] = True

    @staticmethod
    def _local_horizontal_border(binary, left: int, right: int, band: _PixelBand) -> int:
        """Cari posisi garis baris pada kolom lokal untuk mengimbangi scan miring."""

        low = max(0, band.start - 4)
        high = min(binary.height - 1, band.end + 4)
        return max(
            range(low, high + 1),
            key=lambda y: binary.crop((left, y, right, y + 1)).histogram()[0],
        )

    @classmethod
    def _ocr_table_page_data(cls, page, expected_labels: list[str]) -> _PageData:
        try:
            import fitz
            from PIL import Image

            dpi = 400
            pixmap = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
            image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
            binary = image.point(lambda value: 0 if value < 155 else 255)
            grid = cls._detect_scan_grid(binary, len(expected_labels), dpi)
        except PdfParseError:
            raise
        except Exception as exc:
            raise PdfParseError(f"Tabel scan halaman {page.number + 1} gagal dianalisis: {exc}") from exc

        scale_x = page.rect.width / image.width
        scale_y = page.rect.height / image.height
        words: list[dict[str, Any]] = []
        scan_cells: list[dict[str, Any]] = []
        for index, label in enumerate(expected_labels):
            left = grid.date_boundaries[index]
            right = grid.date_boundaries[index + 1]
            words.append({
                "x0": left * scale_x,
                "x1": right * scale_x,
                "top": grid.header_top.end * scale_y,
                "bottom": grid.header_bottom.start * scale_y,
                "text": label,
            })

        padding_x = max(3, round(dpi / 50))
        padding_y = max(3, round(dpi / 70))
        for upper, lower in zip(grid.row_bands, grid.row_bands[1:]):
            top = upper.end + padding_y
            bottom = lower.start - padding_y
            if bottom - top < dpi * 0.10:
                continue
            name_crop = image.crop((
                grid.name_left + padding_x,
                upper.start + padding_y,
                grid.date_boundaries[0] - padding_x,
                lower.end - padding_y,
            ))
            identity_candidates = [
                cls._normalize_ocr_identity(cls._ocr_region(name_crop, psm=6)),
                cls._normalize_ocr_identity(
                    cls._ocr_region(name_crop, psm=6, threshold=True)
                ),
            ]
            # The greyscale pass preserves thin characters better.  Use the
            # thresholded pass only as a fallback; choosing the longest result
            # favoured grid noise and could turn JAMES MAKIKAMA(152) into a
            # longer but incorrect identity.
            identity = next(
                (candidate for candidate in identity_candidates if candidate),
                None,
            )
            if identity is not None and len(identity.split("(", 1)[0]) < 7:
                sparse = cls._normalize_ocr_identity(cls._ocr_region(name_crop, psm=11))
                if sparse and len(sparse.split("(", 1)[0]) > len(identity.split("(", 1)[0]):
                    identity = sparse
            if identity is None:
                continue

            row_top = top * scale_y
            words.append({
                "x0": (grid.name_left + padding_x) * scale_x,
                "x1": (grid.date_boundaries[0] - padding_x) * scale_x,
                "top": row_top,
                "bottom": bottom * scale_y,
                "text": identity,
            })
            for index in range(len(expected_labels)):
                left = grid.date_boundaries[index] + padding_x
                right = grid.date_boundaries[index + 1] - padding_x
                local_top = cls._local_horizontal_border(binary, left, right, upper) + padding_y
                local_bottom = cls._local_horizontal_border(binary, left, right, lower) - padding_y
                if local_bottom - local_top < dpi * 0.10:
                    continue
                cell = image.crop((left, local_top, right, local_bottom))
                kind = cls._cell_ink_kind(cell)
                if kind == "blank":
                    continue
                code_like = kind == "content" and cls._looks_like_handwritten_code(cell)
                raw = (
                    "-"
                    if kind == "dash"
                    else cls._ocr_scan_cell(cell, code_like=code_like)
                )
                word = {
                    "x0": left * scale_x,
                    "x1": right * scale_x,
                    # Jaga token tetap berada di bawah top identitas barisnya.
                    # Pada scan miring, garis lokal dapat lebih tinggi daripada
                    # puncak global dan tanpa clamp token milik pegawai berikut
                    # akan terseret ke baris sebelumnya saat _assign_cells.
                    "top": max(row_top + scale_y, local_top * scale_y),
                    "bottom": local_bottom * scale_y,
                    "text": raw,
                }
                words.append(word)
                scan_cells.append({
                    "column": index,
                    "code_like": code_like,
                    "word": word,
                })
        cls._reconcile_special_code_columns(scan_cells)
        for cell in scan_cells:
            raw = str(cell["word"]["text"]).strip()
            if (
                not raw.startswith("?")
                and not cls._is_recognized_ocr_cell(raw)
                and len(re.sub(r"\s+", "", raw)) <= 3
            ):
                # Pecahan satu-dua glyph (L/E/1/:) umumnya sisa garis tabel
                # atau digit jam yang terpotong. Jangan jadikan noise kecil
                # sebagai 31 masalah blokir; kandidat kode yang sungguh belum
                # pasti memakai awalan '?' dan tetap masuk layar pemeriksaan.
                cell["word"]["text"] = "-"
        if not any(IDENTITY_RE.fullmatch(str(word["text"])) for word in words):
            raise PdfParseError(
                f"Nama dan ID pegawai pada halaman scan {page.number + 1} tidak dapat dibaca. "
                "Pastikan kolom Nama tidak terpotong."
            )
        return _PageData("", words, True)

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
