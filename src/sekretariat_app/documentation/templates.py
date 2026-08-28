from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cell:
    row: int
    column: int
    row_span: int = 1
    column_span: int = 1


@dataclass(frozen=True)
class LayoutTemplate:
    template_id: str
    name: str
    description: str
    rows: int
    columns: int
    cells: tuple[Cell, ...]


TEMPLATES: tuple[LayoutTemplate, ...] = (
    LayoutTemplate("grid-1", "1 Foto Utama", "Satu foto memenuhi area kerja", 1, 1, (Cell(0, 0),)),
    LayoutTemplate("grid-2-v", "2 Foto Atas–Bawah", "Dua foto bertumpuk vertikal", 2, 1, (Cell(0, 0), Cell(1, 0))),
    LayoutTemplate("grid-2-h", "2 Foto Kiri–Kanan", "Dua foto bersandingan", 1, 2, (Cell(0, 0), Cell(0, 1))),
    LayoutTemplate(
        "grid-3-a", "3 Foto: 1 Atas, 2 Bawah", "Foto utama di atas", 2, 2,
        (Cell(0, 0, 1, 2), Cell(1, 0), Cell(1, 1)),
    ),
    LayoutTemplate(
        "grid-3-b", "3 Foto: 1 Kiri, 2 Kanan", "Foto tinggi di kiri", 2, 2,
        (Cell(0, 0, 2, 1), Cell(0, 1), Cell(1, 1)),
    ),
    LayoutTemplate(
        "grid-4-a", "4 Foto Asimetris", "Banner atas dan tiga foto", 3, 2,
        (Cell(0, 0, 1, 2), Cell(1, 0, 2, 1), Cell(1, 1), Cell(2, 1)),
    ),
    LayoutTemplate(
        "grid-4", "4 Foto 2 × 2", "Kisi dokumentasi standar", 2, 2,
        (Cell(0, 0), Cell(0, 1), Cell(1, 0), Cell(1, 1)),
    ),
    LayoutTemplate(
        "grid-5", "5 Foto", "Banner atas dan kisi 2 × 2", 3, 2,
        (Cell(0, 0, 1, 2), Cell(1, 0), Cell(1, 1), Cell(2, 0), Cell(2, 1)),
    ),
    LayoutTemplate(
        "grid-6-a", "6 Foto Berjenjang", "Banner atas, empat foto, banner bawah", 4, 2,
        (Cell(0, 0, 1, 2), Cell(1, 0), Cell(1, 1), Cell(2, 0), Cell(2, 1), Cell(3, 0, 1, 2)),
    ),
    LayoutTemplate(
        "grid-6-b", "6 Foto 3 × 2", "Tiga baris dan dua kolom", 3, 2,
        tuple(Cell(row, column) for row in range(3) for column in range(2)),
    ),
    LayoutTemplate(
        "grid-8", "8 Foto 4 × 2", "Empat baris dan dua kolom", 4, 2,
        tuple(Cell(row, column) for row in range(4) for column in range(2)),
    ),
)


def template_by_id(template_id: str) -> LayoutTemplate:
    return next((template for template in TEMPLATES if template.template_id == template_id), TEMPLATES[0])


def layout_rectangles(
    template: LayoutTemplate,
    page_width: float,
    page_height: float,
    margins: tuple[float, float, float, float],
    gap: float = 3.0,
) -> list[tuple[float, float, float, float]]:
    top, right, bottom, left = margins
    usable_width = max(20.0, page_width - left - right)
    usable_height = max(20.0, page_height - top - bottom)
    column_width = (usable_width - gap * (template.columns - 1)) / template.columns
    row_height = (usable_height - gap * (template.rows - 1)) / template.rows
    result: list[tuple[float, float, float, float]] = []
    for cell in template.cells:
        x = left + cell.column * (column_width + gap)
        y = top + cell.row * (row_height + gap)
        width = column_width * cell.column_span + gap * (cell.column_span - 1)
        height = row_height * cell.row_span + gap * (cell.row_span - 1)
        result.append((x, y, width, height))
    return result
