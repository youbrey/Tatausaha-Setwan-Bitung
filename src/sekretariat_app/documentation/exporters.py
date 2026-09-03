from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QWidget

from sekretariat_app.documentation.models import DocumentProject
from sekretariat_app.documentation.scene import DocumentScene


class DocumentationExporter:
    def _scene_for_page(self, project: DocumentProject, page_index: int) -> DocumentScene:
        width, height = project.page_size_mm
        margins = (
            project.margins.top,
            project.margins.right,
            project.margins.bottom,
            project.margins.left,
        )
        scene = DocumentScene()
        letterhead = project.letterhead if page_index == 0 else {**project.letterhead, "enabled": False}
        scene.load_page(project.pages[page_index], width, height, margins, letterhead)
        return scene

    def export_png_pages(self, project: DocumentProject, directory: str | Path, dpi: int = 300) -> list[Path]:
        target_dir = Path(directory)
        target_dir.mkdir(parents=True, exist_ok=True)
        files: list[Path] = []
        stem = self._safe_name(project.title)
        for index in range(len(project.pages)):
            scene = self._scene_for_page(project, index)
            image = scene.render_image(dpi)
            target = target_dir / f"{stem}-halaman-{index + 1:02d}.png"
            if not image.save(str(target), "PNG"):
                raise OSError(f"Gagal menulis {target}")
            scene.clear()
            del image
            files.append(target)
        return files

    def export_pdf(self, project: DocumentProject, path: str | Path, dpi: int = 300) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        width_mm, height_mm = project.page_size_mm
        page_size = QPageSize(QSizeF(width_mm, height_mm), QPageSize.Unit.Millimeter, project.paper_size)
        writer = QPdfWriter(str(target))
        writer.setResolution(dpi)
        writer.setPageLayout(QPageLayout(page_size, QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0)))
        painter = QPainter(writer)
        for index in range(len(project.pages)):
            if index:
                writer.newPage()
            scene = self._scene_for_page(project, index)
            scene.render_to_painter(painter, QRectF(0, 0, writer.width(), writer.height()))
            scene.clear()
        painter.end()
        return target

    def export_docx(self, project: DocumentProject, path: str | Path, dpi: int = 300) -> Path:
        from docx import Document
        from docx.enum.text import WD_BREAK
        from docx.shared import Mm

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        width_mm, height_mm = project.page_size_mm
        with tempfile.TemporaryDirectory(prefix="dokufoto-docx-") as temp_dir:
            images = self.export_png_pages(project, temp_dir, dpi)
            document = Document()
            section = document.sections[0]
            section.page_width = Mm(width_mm)
            section.page_height = Mm(height_mm)
            section.top_margin = Mm(0)
            section.right_margin = Mm(0)
            section.bottom_margin = Mm(0)
            section.left_margin = Mm(0)
            section.header_distance = Mm(0)
            section.footer_distance = Mm(0)
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.space_before = 0
            paragraph.paragraph_format.space_after = 0
            paragraph.paragraph_format.line_spacing = 1
            for index, image_path in enumerate(images):
                if index:
                    paragraph = document.add_paragraph()
                paragraph.paragraph_format.space_before = 0
                paragraph.paragraph_format.space_after = 0
                paragraph.add_run().add_picture(str(image_path), width=Mm(width_mm), height=Mm(height_mm))
                if index < len(images) - 1:
                    paragraph.add_run().add_break(WD_BREAK.PAGE)
            document.save(target)
        return target

    def print_project(self, project: DocumentProject, parent: QWidget) -> bool:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        width_mm, height_mm = project.page_size_mm
        page_size = QPageSize(QSizeF(width_mm, height_mm), QPageSize.Unit.Millimeter, project.paper_size)
        printer.setPageLayout(QPageLayout(page_size, QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0)))
        dialog = QPrintDialog(printer, parent)
        dialog.setWindowTitle("Cetak Dokumentasi Foto")
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return False
        painter = QPainter(printer)
        for index in range(len(project.pages)):
            if index:
                printer.newPage()
            scene = self._scene_for_page(project, index)
            target_rect = QRectF(printer.pageRect(QPrinter.Unit.DevicePixel))
            scene.render_to_painter(painter, target_rect)
            scene.clear()
        painter.end()
        return True

    def export_archive(self, project: DocumentProject, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = project.to_dict()
        media_map: dict[str, str] = {}
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, media_path in enumerate(project.media):
                source = Path(media_path)
                if not source.exists() or not source.is_file():
                    continue
                archive_name = f"media/{index:04d}-{source.name}"
                archive.write(source, archive_name)
                media_map[str(source)] = archive_name
            for page in payload.get("pages", []):
                for element in page.get("elements", []):
                    if element.get("kind") == "photo" and element.get("photo_path") in media_map:
                        element["photo_path"] = media_map[element["photo_path"]]
            payload["media"] = list(media_map.values())
            payload["archive_format"] = "dokufoto-python-v1"
            archive.writestr("project.dokufoto.json", json.dumps(payload, ensure_ascii=False, indent=2))
        return target

    def import_archive(self, path: str | Path, destination: str | Path) -> DocumentProject:
        source = Path(path)
        target_dir = Path(destination) / source.stem
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source, "r") as archive:
            names = archive.namelist()
            project_name = next((name for name in names if name == "project.dokufoto.json" or name.endswith("/project.dokufoto.json")), None)
            if not project_name:
                raise ValueError("Arsip tidak memiliki project.dokufoto.json.")
            for name in names:
                candidate = (target_dir / name).resolve()
                if not str(candidate).startswith(str(target_dir.resolve())):
                    raise ValueError("Arsip berisi path yang tidak aman.")
            archive.extractall(target_dir)
        project_path = target_dir / project_name
        payload = json.loads(project_path.read_text(encoding="utf-8"))
        if payload.get("archive_format") != "dokufoto-python-v1":
            project = DocumentProject.load(project_path)
            for candidate in target_dir.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                    value = str(candidate.resolve())
                    if value not in project.media:
                        project.media.append(value)
            return project
        media = [str((target_dir / name).resolve()) for name in payload.get("media", [])]
        mapping = dict(zip(payload.get("media", []), media))
        payload["media"] = media
        for page in payload.get("pages", []):
            for element in page.get("elements", []):
                if element.get("kind") == "photo" and element.get("photo_path") in mapping:
                    element["photo_path"] = mapping[element["photo_path"]]
        return DocumentProject.from_dict(payload)

    @staticmethod
    def _safe_name(name: str) -> str:
        cleaned = "".join(character if character.isalnum() or character in "-_" else "_" for character in name)
        return cleaned.strip("_") or "Dokumentasi_Foto"
