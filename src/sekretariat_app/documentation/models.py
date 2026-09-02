from __future__ import annotations

import base64
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


PAPER_SIZES: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "F4": (215.0, 330.0),
    "Letter": (215.9, 279.4),
    "Legal": (215.9, 355.6),
}


def default_letterhead() -> dict[str, Any]:
    return {
        "enabled": False,
        "logo_left": "",
        "logo_right": "",
        "government_name": "PEMERINTAH KOTA BITUNG",
        "agency_name": "DEWAN PERWAKILAN RAKYAT DAERAH",
        "sub_agency_name": "SEKRETARIAT DEWAN",
        "address": "Jl. Sam Ratulangi No. 45, Kel. Bitung Barat Satu, Kec. Maesa, Kota Bitung",
        "contact": "Telp: (0438) 21115 / 21120 | Website: dprd.bitungkota.go.id",
        "border_style": "double",
    }


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@dataclass
class PageMargins:
    top: float = 15.0
    right: float = 15.0
    bottom: float = 15.0
    left: float = 15.0


@dataclass
class PhotoElement:
    id: str = field(default_factory=lambda: new_id("photo"))
    kind: str = "photo"
    photo_path: str = ""
    x: float = 20.0
    y: float = 20.0
    width: float = 80.0
    height: float = 60.0
    rotation: float = 0.0
    image_rotation: int = 0
    fit: str = "cover"
    crop_x: float = 0.5
    crop_y: float = 0.5
    zoom: float = 1.0
    border_width: float = 0.5
    border_color: str = "#94a3b8"
    radius: float = 1.5
    caption: str = ""
    show_caption: bool = False
    locked: bool = False


@dataclass
class TextElement:
    id: str = field(default_factory=lambda: new_id("text"))
    kind: str = "text"
    text: str = "Klik dua kali untuk mengubah teks"
    x: float = 25.0
    y: float = 25.0
    width: float = 120.0
    font_family: str = "Arial"
    font_size: float = 14.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: str = "#0f172a"
    background: str = "#00ffffff"
    alignment: str = "left"
    letter_spacing: float = 0.0
    line_height: float = 1.2
    rotation: float = 0.0
    opacity: float = 1.0
    effect: str = "none"
    effect_color: str = "#334155"
    locked: bool = False


@dataclass
class DocumentPage:
    id: str = field(default_factory=lambda: new_id("page"))
    title: str = "Halaman 1"
    elements: list[dict[str, Any]] = field(default_factory=list)
    background: str = "#ffffff"
    collage: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentProject:
    id: str = field(default_factory=lambda: new_id("project"))
    title: str = "Dokumentasi Kegiatan"
    author: str = "Sekretariat DPRD Kota Bitung"
    institution: str = "Sekretariat DPRD Kota Bitung"
    paper_size: str = "F4"
    custom_width_mm: float = 215.0
    custom_height_mm: float = 330.0
    orientation: str = "portrait"
    margins: PageMargins = field(default_factory=PageMargins)
    letterhead: dict[str, Any] = field(default_factory=default_letterhead)
    pages: list[DocumentPage] = field(default_factory=lambda: [DocumentPage()])
    media: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def page_size_mm(self) -> tuple[float, float]:
        if self.paper_size == "Custom":
            size = self.custom_width_mm, self.custom_height_mm
        else:
            size = PAPER_SIZES.get(self.paper_size, PAPER_SIZES["F4"])
        return size if self.orientation == "portrait" else (size[1], size[0])

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentProject":
        if "paperSize" in data or "kopSurat" in data:
            return cls.from_react_dict(data)
        margins_data = data.get("margins") or {}
        pages = []
        for index, raw_page in enumerate(data.get("pages") or []):
            pages.append(
                DocumentPage(
                    id=raw_page.get("id") or new_id("page"),
                    title=raw_page.get("title") or f"Halaman {index + 1}",
                    elements=list(raw_page.get("elements") or []),
                    background=raw_page.get("background", "#ffffff"),
                    collage=dict(raw_page.get("collage") or {}),
                )
            )
        project = cls(
            id=data.get("id") or new_id("project"),
            title=data.get("title", "Dokumentasi Kegiatan"),
            author=data.get("author", "Sekretariat DPRD Kota Bitung"),
            institution=data.get("institution", "Sekretariat DPRD Kota Bitung"),
            paper_size=data.get("paper_size", "F4"),
            custom_width_mm=float(data.get("custom_width_mm", 215.0)),
            custom_height_mm=float(data.get("custom_height_mm", 330.0)),
            orientation=data.get("orientation", "portrait"),
            margins=PageMargins(
                top=float(margins_data.get("top", 15.0)),
                right=float(margins_data.get("right", 15.0)),
                bottom=float(margins_data.get("bottom", 15.0)),
                left=float(margins_data.get("left", 15.0)),
            ),
            letterhead={**default_letterhead(), **(data.get("letterhead") or {})},
            pages=pages or [DocumentPage()],
            media=[str(path) for path in data.get("media") or []],
            created_at=data.get("created_at") or datetime.now().isoformat(timespec="seconds"),
            updated_at=data.get("updated_at") or datetime.now().isoformat(timespec="seconds"),
        )
        return project

    @classmethod
    def from_react_dict(
        cls,
        data: dict[str, Any],
        photos: list[dict[str, Any]] | None = None,
        media_directory: Path | None = None,
    ) -> "DocumentProject":
        """Migrasikan struktur proyek DokuFoto-React ke model Python."""
        paper_size = str(data.get("paperSize", "F4"))
        orientation = str(data.get("orientation", "portrait"))
        raw_margins = data.get("margins") or {}
        margins = PageMargins(
            top=float(raw_margins.get("top", 2.0)) * 10,
            right=float(raw_margins.get("right", 2.0)) * 10,
            bottom=float(raw_margins.get("bottom", 2.0)) * 10,
            left=float(raw_margins.get("left", 2.5)) * 10,
        )
        if paper_size == "Custom":
            base_width = float(data.get("customWidthMm", 210.0))
            base_height = float(data.get("customHeightMm", 297.0))
        else:
            base_width, base_height = PAPER_SIZES.get(paper_size, PAPER_SIZES["F4"])
        page_width, page_height = (
            (base_width, base_height) if orientation == "portrait" else (base_height, base_width)
        )
        media_directory = media_directory or Path.cwd() / "dokufoto_imported_media"
        media_directory.mkdir(parents=True, exist_ok=True)
        photo_lookup: dict[str, str] = {}
        media: list[str] = []

        def register_photo(photo: Any) -> str:
            if not isinstance(photo, dict):
                return ""
            photo_id = str(photo.get("id", ""))
            if photo_id and photo_id in photo_lookup:
                return photo_lookup[photo_id]
            data_url = str(photo.get("dataUrl", ""))
            path = _write_data_url(data_url, str(photo.get("name", photo_id or "foto")), media_directory)
            if path:
                if photo_id:
                    photo_lookup[photo_id] = path
                if path not in media:
                    media.append(path)
            return path

        for photo in photos or []:
            register_photo(photo)

        pages: list[DocumentPage] = []
        canvas_height = 560.0 / max(0.1, page_width / page_height)
        for page_index, raw_page in enumerate(data.get("pages") or []):
            elements: list[dict[str, Any]] = []
            raw_grids = list(raw_page.get("grids") or [])
            if not raw_grids and raw_page.get("cells"):
                rows = max((int(cell.get("row", 0)) + int(cell.get("rowSpan", 1)) for cell in raw_page["cells"]), default=1)
                columns = max((int(cell.get("col", 0)) + int(cell.get("colSpan", 1)) for cell in raw_page["cells"]), default=1)
                raw_grids = [
                    {
                        "x": 50,
                        "y": 52,
                        "widthPercent": float(raw_page.get("gridWidthPercent", 82)),
                        "heightPx": float(raw_page.get("gridHeightPx", canvas_height * 0.72)),
                        "rows": rows,
                        "cols": columns,
                        "gapMm": float(raw_page.get("gridGapMm", 3)),
                        "borderWidth": float(raw_page.get("cellBorderWidth", 1)),
                        "borderColor": raw_page.get("cellBorderColor", "#94a3b8"),
                        "borderRadius": float(raw_page.get("cellBorderRadius", 2)),
                        "cells": raw_page.get("cells") or [],
                    }
                ]
            for grid in raw_grids:
                grid_width = page_width * float(grid.get("widthPercent", 80)) / 100
                grid_height = page_height * float(grid.get("heightPx", canvas_height * 0.7)) / canvas_height
                grid_left = page_width * float(grid.get("x", 50)) / 100 - grid_width / 2
                grid_top = page_height * float(grid.get("y", 50)) / 100 - grid_height / 2
                rows = max(1, int(grid.get("rows", 1)))
                columns = max(1, int(grid.get("cols", 1)))
                gap = float(grid.get("gapMm", 3))
                cell_width = (grid_width - gap * (columns - 1)) / columns
                cell_height = (grid_height - gap * (rows - 1)) / rows
                for cell in grid.get("cells") or []:
                    row = int(cell.get("row", 0))
                    column = int(cell.get("col", 0))
                    row_span = max(1, int(cell.get("rowSpan", 1)))
                    column_span = max(1, int(cell.get("colSpan", 1)))
                    width = cell_width * column_span + gap * (column_span - 1)
                    height = cell_height * row_span + gap * (row_span - 1)
                    crop = cell.get("cropRect") or {}
                    crop_width = max(0.05, min(1.0, float(crop.get("width", 1))))
                    crop_height = max(0.05, min(1.0, float(crop.get("height", 1))))
                    crop_x = float(crop.get("x", 0)) / max(0.0001, 1 - crop_width) if crop_width < 1 else 0.5
                    crop_y = float(crop.get("y", 0)) / max(0.0001, 1 - crop_height) if crop_height < 1 else 0.5
                    elements.append(
                        PhotoElement(
                            id=str(cell.get("id") or new_id("photo")),
                            photo_path=register_photo(cell.get("photo")),
                            x=grid_left + column * (cell_width + gap),
                            y=grid_top + row * (cell_height + gap),
                            width=width,
                            height=height,
                            rotation=float(grid.get("rotation", 0)),
                            image_rotation=int(cell.get("rotation", 0)),
                            fit=str(cell.get("objectFit", "cover")),
                            crop_x=max(0, min(1, crop_x)),
                            crop_y=max(0, min(1, crop_y)),
                            zoom=max(1.0, min(5.0, max(1 / crop_width, 1 / crop_height))),
                            border_width=float(grid.get("borderWidth", 1)),
                            border_color=str(grid.get("borderColor", "#94a3b8")),
                            radius=float(grid.get("borderRadius", 2)),
                            caption=str(cell.get("caption", "")),
                            show_caption=bool(cell.get("showCaption", False)),
                            locked=bool(grid.get("isLocked", False)),
                        ).__dict__
                    )
            for text in raw_page.get("floatingTexts") or []:
                width = page_width * float(text.get("width", 440)) / 560
                x = page_width * float(text.get("x", 50)) / 100 - width / 2
                y = page_height * float(text.get("y", 12)) / 100
                weight = str(text.get("fontWeight", "normal"))
                elements.append(
                    TextElement(
                        id=str(text.get("id") or new_id("text")),
                        text=str(text.get("text", "Teks")),
                        x=max(0, x),
                        y=max(0, y),
                        width=max(15, width),
                        font_family=str(text.get("fontFamily", data.get("fontFamily", "Arial"))),
                        font_size=float(text.get("fontSize", 14)),
                        bold=weight in {"bold", "700", "800", "900"},
                        italic=str(text.get("fontStyle", "normal")) == "italic",
                        underline=str(text.get("textDecoration", "none")) == "underline",
                        color=str(text.get("color", "#0f172a")),
                        background=str(text.get("backgroundColor", "#00ffffff")),
                        alignment=str(text.get("textAlign", "left")),
                        letter_spacing=float(text.get("letterSpacing", 0)),
                        line_height=float(text.get("lineHeight", 1.2)),
                        rotation=float(text.get("rotation", 0)),
                        opacity=float(text.get("opacity", 1)),
                        effect=str(text.get("effect", "none")) if text.get("effect") in {"none", "shadow", "glow"} else "none",
                        effect_color=str(text.get("effectColor", "#334155")),
                        locked=bool(text.get("isLocked", False)),
                    ).__dict__
                )
            pages.append(
                DocumentPage(
                    id=str(raw_page.get("id") or new_id("page")),
                    title=str(raw_page.get("title") or f"Halaman {page_index + 1}"),
                    elements=elements,
                    collage={
                        "template_id": str((raw_grids[0] if raw_grids else {}).get("templateId", "")),
                        "gap_mm": float((raw_grids[0] if raw_grids else {}).get("gapMm", 3.0)),
                        "width_percent": float((raw_grids[0] if raw_grids else {}).get("widthPercent", 100.0)),
                        "height_percent": min(
                            100.0,
                            float((raw_grids[0] if raw_grids else {}).get("heightPx", canvas_height))
                            / max(1.0, canvas_height) * 100.0,
                        ),
                    } if raw_grids else {},
                )
            )

        kop = data.get("kopSurat") or {}
        letterhead = {
            **default_letterhead(),
            "enabled": bool(kop.get("enabled", False)),
            "government_name": str(kop.get("governmentName", default_letterhead()["government_name"])),
            "agency_name": str(kop.get("agencyName", default_letterhead()["agency_name"])),
            "sub_agency_name": str(kop.get("subAgencyName", default_letterhead()["sub_agency_name"])),
            "address": str(kop.get("address", default_letterhead()["address"])),
            "contact": str(kop.get("contactInfo", default_letterhead()["contact"])),
            "border_style": str(kop.get("borderStyle", "double")),
        }
        return cls(
            id=str(data.get("id") or new_id("project")),
            title=str(data.get("title", "Dokumentasi Kegiatan")),
            author=str(data.get("author", "Sekretariat DPRD Kota Bitung")),
            institution=str(data.get("institution", "Sekretariat DPRD Kota Bitung")),
            paper_size=paper_size,
            custom_width_mm=float(data.get("customWidthMm", 215.0)),
            custom_height_mm=float(data.get("customHeightMm", 330.0)),
            orientation=orientation,
            margins=margins,
            letterhead=letterhead,
            pages=pages or [DocumentPage()],
            media=media,
            created_at=str(data.get("createdAt", datetime.now().isoformat(timespec="seconds"))),
            updated_at=str(data.get("updatedAt", datetime.now().isoformat(timespec="seconds"))),
        )

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.touch()
        target.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> "DocumentProject":
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Format proyek Dokumentasi Foto tidak valid.")
        if data.get("kind") == "dokufoto-workspace" and isinstance(data.get("project"), dict):
            return cls.from_react_dict(
                data["project"],
                list(data.get("photos") or []),
                source.parent / f"{source.name.replace('.dokufoto.json', '')}_media",
            )
        if "paperSize" in data or "kopSurat" in data:
            return cls.from_react_dict(
                data,
                media_directory=source.parent / f"{source.name.replace('.dokufoto.json', '')}_media",
            )
        return cls.from_dict(data)


def _write_data_url(data_url: str, name: str, directory: Path) -> str:
    match = re.match(r"^data:image/(png|jpe?g|webp|bmp);base64,(.+)$", data_url, re.IGNORECASE | re.DOTALL)
    if not match:
        candidate = Path(data_url)
        return str(candidate.resolve()) if candidate.exists() else ""
    extension = "jpg" if match.group(1).lower() in {"jpg", "jpeg"} else match.group(1).lower()
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "foto"
    if not safe_name.lower().endswith(f".{extension}"):
        safe_name += f".{extension}"
    target = directory / safe_name
    suffix = 1
    while target.exists():
        target = directory / f"{Path(safe_name).stem}-{suffix}.{extension}"
        suffix += 1
    try:
        target.write_bytes(base64.b64decode(match.group(2), validate=True))
    except (ValueError, OSError):
        return ""
    return str(target.resolve())
