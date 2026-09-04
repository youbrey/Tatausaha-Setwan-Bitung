from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImageReader,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from sekretariat_app.config import autosave_path, documentation_dir
from sekretariat_app.documentation.exporters import DocumentationExporter
from sekretariat_app.documentation.models import DocumentPage, DocumentProject, PhotoElement, TextElement
from sekretariat_app.documentation.scene import DocumentScene, PhotoItem, TextItem
from sekretariat_app.documentation.templates import TEMPLATES, layout_rectangles, template_by_id


IMAGE_FILTER = "Gambar (*.jpg *.jpeg *.png *.webp *.bmp)"


def _scaled_pixmap(path: str, maximum: QSize) -> QPixmap:
    """Decode gambar langsung pada resolusi preview, bukan resolusi kamera."""

    if not path or not Path(path).exists():
        return QPixmap()
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    original = reader.size()
    if original.isValid() and (
        original.width() > maximum.width() or original.height() > maximum.height()
    ):
        reader.setScaledSize(original.scaled(maximum, Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    return QPixmap.fromImage(image) if not image.isNull() else QPixmap()


def _template_icon(template_id: str, size: QSize = QSize(184, 104)) -> QIcon:
    """Buat mini-preview kisi tanpa bergantung pada aset gambar eksternal."""
    template = template_by_id(template_id)
    pixmap = QPixmap(size)
    pixmap.fill(QColor("#f1f5f9"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    page_height = max(72.0, size.height() - 12.0)
    page_width = page_height * 215.0 / 330.0
    page = QRectF((size.width() - page_width) / 2.0, 6.0, page_width, page_height)
    painter.fillRect(page, QColor("#ffffff"))
    painter.setPen(QPen(QColor("#94a3b8"), 1.0))
    painter.drawRoundedRect(page, 3.0, 3.0)
    rectangles = layout_rectangles(template, page_width, page_height, (7, 5, 5, 5), 2.2)
    colors = ("#bfdbfe", "#c7d2fe", "#ddd6fe", "#bae6fd", "#a5f3fc", "#dbeafe")
    for index, (x, y, width, height) in enumerate(rectangles):
        cell = QRectF(page.left() + x, page.top() + y, width, height)
        painter.fillRect(cell, QColor(colors[index % len(colors)]))
        painter.setPen(QPen(QColor("#3b82f6"), 0.8))
        painter.drawRoundedRect(cell, 1.2, 1.2)
    painter.end()
    return QIcon(pixmap)


class CanvasView(QGraphicsView):
    files_dropped = Signal(list)

    def __init__(self, scene: DocumentScene):
        super().__init__(scene)
        self.setAcceptDrops(True)
        self.setRenderHints(
            self.renderHints()
            | QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setBackgroundBrush(QColor("#cbd5e1"))

    def wheelEvent(self, event) -> None:
        scene = self.scene()
        if isinstance(scene, DocumentScene) and scene.active_crop_item is not None:
            step = 0.12 if event.angleDelta().y() > 0 else -0.12
            current = float(scene.active_crop_item.data.get("zoom", 1.0))
            scene.active_crop_item.set_crop_zoom(current + step)
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        images = [path for path in paths if Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}]
        if images:
            self.files_dropped.emit(images)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def fit_page(self) -> None:
        self.resetTransform()
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class CropPreview(QWidget):
    """Crop interaktif: frame tetap, foto digeser dan diperbesar seperti Canva."""

    crop_changed = Signal(float, float, float)

    def __init__(self, photo_path: str, target_aspect: float, parent=None):
        super().__init__(parent)
        self.photo_path = photo_path
        self.target_aspect = max(0.1, target_aspect)
        self.crop_x = 0.5
        self.crop_y = 0.5
        self.zoom = 1.0
        self.fit = "cover"
        self.image_rotation = 0
        self._drag_position = None
        self._pixmap = _scaled_pixmap(photo_path, QSize(2048, 2048))
        self._rotated_pixmap = QPixmap()
        self._cached_rotation = -1
        self.setMinimumSize(560, 360)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_state(
        self,
        crop_x: float,
        crop_y: float,
        zoom: float,
        fit: str,
        image_rotation: int,
    ) -> None:
        self.crop_x = max(0.0, min(1.0, crop_x))
        self.crop_y = max(0.0, min(1.0, crop_y))
        self.zoom = max(1.0, min(5.0, zoom))
        self.fit = fit
        self.image_rotation = image_rotation % 360
        self.update()

    def _display_pixmap(self) -> QPixmap:
        if self._pixmap.isNull() or not self.image_rotation:
            return self._pixmap
        if self._cached_rotation != self.image_rotation:
            self._rotated_pixmap = self._pixmap.transformed(
                QTransform().rotate(self.image_rotation),
                Qt.TransformationMode.SmoothTransformation,
            )
            self._cached_rotation = self.image_rotation
        return self._rotated_pixmap

    def _frame_rect(self) -> QRectF:
        available = QRectF(self.rect()).adjusted(34, 28, -34, -28)
        if available.width() / max(1.0, available.height()) > self.target_aspect:
            height = available.height()
            width = height * self.target_aspect
        else:
            width = available.width()
            height = width / self.target_aspect
        return QRectF(
            available.center().x() - width / 2.0,
            available.center().y() - height / 2.0,
            width,
            height,
        )

    def _cover_source(self, pixmap: QPixmap, frame: QRectF) -> tuple[QRectF, float, float]:
        source = QRectF(pixmap.rect())
        source_aspect = source.width() / max(1.0, source.height())
        target_aspect = frame.width() / max(1.0, frame.height())
        if source_aspect > target_aspect:
            source_width, source_height = source.height() * target_aspect, source.height()
        else:
            source_width, source_height = source.width(), source.width() / target_aspect
        source_width /= self.zoom
        source_height /= self.zoom
        max_x = max(0.0, source.width() - source_width)
        max_y = max(0.0, source.height() - source_height)
        return (
            QRectF(max_x * self.crop_x, max_y * self.crop_y, source_width, source_height),
            max_x,
            max_y,
        )

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor("#0f172a"))
        frame = self._frame_rect()
        painter.fillRect(frame, QColor("#111827"))
        pixmap = self._display_pixmap()
        if not pixmap.isNull():
            if self.fit == "fill":
                painter.drawPixmap(frame, pixmap, QRectF(pixmap.rect()))
            elif self.fit == "contain":
                source_aspect = pixmap.width() / max(1.0, pixmap.height())
                target_aspect = frame.width() / max(1.0, frame.height())
                if source_aspect > target_aspect:
                    height = frame.width() / source_aspect
                    target = QRectF(frame.left(), frame.center().y() - height / 2.0, frame.width(), height)
                else:
                    width = frame.height() * source_aspect
                    target = QRectF(frame.center().x() - width / 2.0, frame.top(), width, frame.height())
                painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
            else:
                source, _max_x, _max_y = self._cover_source(pixmap, frame)
                painter.drawPixmap(frame, pixmap, source)
        painter.setPen(QPen(QColor("#38bdf8"), 3.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(frame)
        painter.setPen(QColor("#e2e8f0"))
        painter.drawText(
            QRectF(0, self.height() - 24, self.width(), 18),
            Qt.AlignmentFlag.AlignCenter,
            "Seret foto untuk mengatur posisi · roda mouse untuk zoom",
        )
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._frame_rect().contains(event.position()):
            self._drag_position = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_position is None or self.fit != "cover":
            super().mouseMoveEvent(event)
            return
        pixmap = self._display_pixmap()
        frame = self._frame_rect()
        source, max_x, max_y = self._cover_source(pixmap, frame)
        delta = event.position() - self._drag_position
        if max_x > 0:
            self.crop_x = max(0.0, min(1.0, self.crop_x - delta.x() * source.width() / frame.width() / max_x))
        if max_y > 0:
            self.crop_y = max(0.0, min(1.0, self.crop_y - delta.y() * source.height() / frame.height() / max_y))
        self._drag_position = event.position()
        self.crop_changed.emit(self.crop_x, self.crop_y, self.zoom)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_position is not None:
            self._drag_position = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        if self._frame_rect().contains(event.position()) and self.fit == "cover":
            step = 0.12 if event.angleDelta().y() > 0 else -0.12
            self.zoom = max(1.0, min(5.0, self.zoom + step))
            self.crop_changed.emit(self.crop_x, self.crop_y, self.zoom)
            self.update()
            event.accept()
            return
        super().wheelEvent(event)


class CropDialog(QDialog):
    def __init__(self, item: PhotoItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.original = {
            "crop_x": float(item.data.get("crop_x", 0.5)),
            "crop_y": float(item.data.get("crop_y", 0.5)),
            "zoom": float(item.data.get("zoom", 1.0)),
            "image_rotation": int(item.data.get("image_rotation", 0)),
            "fit": str(item.data.get("fit", "cover")),
        }
        self.setWindowTitle("Crop dan Posisi Foto")
        self.resize(760, 680)
        layout = QVBoxLayout(self)
        instruction = QLabel(
            "Area biru adalah frame akhir. Seret foto di dalam frame untuk mengatur bagian yang tampil."
        )
        instruction.setWordWrap(True)
        instruction.setObjectName("MutedText")
        layout.addWidget(instruction)
        self.preview = CropPreview(
            str(item.data.get("photo_path", "")),
            item._rect.width() / max(1.0, item._rect.height()),
            self,
        )
        self.preview.set_state(
            self.original["crop_x"],
            self.original["crop_y"],
            self.original["zoom"],
            self.original["fit"],
            self.original["image_rotation"],
        )
        layout.addWidget(self.preview, 1)

        form = QFormLayout()
        self.fit_combo = QComboBox()
        self.fit_combo.addItems(("cover", "contain", "fill"))
        self.fit_combo.setCurrentText(self.original["fit"])
        form.addRow("Mode gambar", self.fit_combo)
        self.zoom = QSlider(Qt.Orientation.Horizontal)
        self.zoom.setRange(100, 500)
        self.zoom.setValue(round(self.original["zoom"] * 100))
        form.addRow("Zoom", self.zoom)
        self.horizontal = QSlider(Qt.Orientation.Horizontal)
        self.horizontal.setRange(0, 100)
        self.horizontal.setValue(round(self.original["crop_x"] * 100))
        form.addRow("Posisi horizontal", self.horizontal)
        self.vertical = QSlider(Qt.Orientation.Horizontal)
        self.vertical.setRange(0, 100)
        self.vertical.setValue(round(self.original["crop_y"] * 100))
        form.addRow("Posisi vertikal", self.vertical)
        rotate_row = QHBoxLayout()
        rotate_left = QPushButton("Putar −90°")
        rotate_right = QPushButton("Putar +90°")
        rotate_row.addWidget(rotate_left)
        rotate_row.addWidget(rotate_right)
        form.addRow("Rotasi foto", rotate_row)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        reset = QPushButton("Reset Crop")
        reset.clicked.connect(self._reset_crop)
        button_row.addWidget(reset)
        button_row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Terapkan Crop")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_row.addWidget(buttons)
        layout.addLayout(button_row)
        self.zoom.valueChanged.connect(self._update_from_controls)
        self.horizontal.valueChanged.connect(self._update_from_controls)
        self.vertical.valueChanged.connect(self._update_from_controls)
        self.fit_combo.currentTextChanged.connect(self._update_from_controls)
        self.preview.crop_changed.connect(self._update_from_preview)
        rotate_left.clicked.connect(lambda: self._rotate(-90))
        rotate_right.clicked.connect(lambda: self._rotate(90))
        self._update_from_controls()

    def _rotate(self, degrees: int) -> None:
        self.item.data["image_rotation"] = (int(self.item.data.get("image_rotation", 0)) + degrees) % 360
        self._update_from_controls()

    def _update_from_controls(self) -> None:
        self.item.data["fit"] = self.fit_combo.currentText()
        self.item.data["zoom"] = self.zoom.value() / 100
        self.item.data["crop_x"] = self.horizontal.value() / 100
        self.item.data["crop_y"] = self.vertical.value() / 100
        self.item.update()
        self.preview.set_state(
            float(self.item.data["crop_x"]),
            float(self.item.data["crop_y"]),
            float(self.item.data["zoom"]),
            str(self.item.data["fit"]),
            int(self.item.data.get("image_rotation", 0)),
        )

    def _update_from_preview(self, crop_x: float, crop_y: float, zoom: float) -> None:
        blockers = (
            QSignalBlocker(self.horizontal),
            QSignalBlocker(self.vertical),
            QSignalBlocker(self.zoom),
        )
        self.horizontal.setValue(round(crop_x * 100))
        self.vertical.setValue(round(crop_y * 100))
        self.zoom.setValue(round(zoom * 100))
        del blockers
        self.item.data.update(crop_x=crop_x, crop_y=crop_y, zoom=zoom)
        self.item.update()

    def _reset_crop(self) -> None:
        blockers = (
            QSignalBlocker(self.horizontal),
            QSignalBlocker(self.vertical),
            QSignalBlocker(self.zoom),
            QSignalBlocker(self.fit_combo),
        )
        self.horizontal.setValue(50)
        self.vertical.setValue(50)
        self.zoom.setValue(100)
        self.fit_combo.setCurrentText("cover")
        del blockers
        self.item.data.update(crop_x=0.5, crop_y=0.5, zoom=1.0, fit="cover", image_rotation=0)
        self._update_from_controls()

    def reject(self) -> None:
        self.item.data.update(self.original)
        self.item.update()
        super().reject()


class PageSetupDialog(QDialog):
    def __init__(self, project: DocumentProject, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Ukuran Kertas dan Margin")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.paper = QComboBox()
        self.paper.addItems(("A4", "F4", "Letter", "Legal", "Custom"))
        self.paper.setCurrentText(project.paper_size)
        form.addRow("Ukuran kertas", self.paper)
        self.orientation = QComboBox()
        self.orientation.addItems(("portrait", "landscape"))
        self.orientation.setCurrentText(project.orientation)
        form.addRow("Orientasi", self.orientation)
        self.custom_width = self._spin(project.custom_width_mm, 80, 600)
        self.custom_height = self._spin(project.custom_height_mm, 80, 600)
        form.addRow("Lebar kustom (mm)", self.custom_width)
        form.addRow("Tinggi kustom (mm)", self.custom_height)
        self.top = self._spin(project.margins.top, 0, 80)
        self.right = self._spin(project.margins.right, 0, 80)
        self.bottom = self._spin(project.margins.bottom, 0, 80)
        self.left = self._spin(project.margins.left, 0, 80)
        form.addRow("Margin atas (mm)", self.top)
        form.addRow("Margin kanan (mm)", self.right)
        form.addRow("Margin bawah (mm)", self.bottom)
        form.addRow("Margin kiri (mm)", self.left)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _spin(value: float, minimum: float, maximum: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(1)
        spin.setValue(value)
        return spin


class AutoCollageDialog(QDialog):
    """Studio auto-kolase dengan preview foto nyata sebelum diterapkan."""

    def __init__(self, project: DocumentProject, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Studio Auto Kolase Foto")
        self.resize(980, 720)
        layout = QVBoxLayout(self)
        width_mm, height_mm = project.page_size_mm
        heading = QLabel(
            f"{len(project.media)} foto terpilih  ·  {project.paper_size} "
            f"{width_mm:g} × {height_mm:g} mm  ·  {project.orientation.title()}"
        )
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)
        info = QLabel(
            "Pilih model kisi melalui mini-preview. Pratinjau di bawah diperbarui otomatis "
            "sebelum kolase diterapkan ke dokumen."
        )
        info.setWordWrap(True)
        info.setObjectName("MutedText")
        layout.addWidget(info)

        body = QSplitter(Qt.Orientation.Horizontal)
        preview_card = QFrame()
        preview_card.setObjectName("CanvasCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.addWidget(QLabel("Pratinjau Auto Kolase"))
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(360, 460)
        self.preview.setStyleSheet("background: #cbd5e1; border: 1px solid #94a3b8;")
        preview_layout.addWidget(self.preview, 1)
        self.preview_summary = QLabel()
        self.preview_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_summary.setObjectName("MutedText")
        preview_layout.addWidget(self.preview_summary)
        body.addWidget(preview_card)

        options = QFrame()
        options.setObjectName("SidePanel")
        options_layout = QVBoxLayout(options)
        options_layout.addWidget(QLabel("Pilihan Model Kisi"))
        self.template_list = QListWidget()
        self.template_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.template_list.setIconSize(QSize(150, 84))
        self.template_list.setGridSize(QSize(184, 128))
        self.template_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.template_list.setMovement(QListWidget.Movement.Static)
        self.template_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for template in TEMPLATES:
            item = QListWidgetItem(_template_icon(template.template_id), template.name)
            item.setData(Qt.ItemDataRole.UserRole, template.template_id)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setToolTip(template.description)
            self.template_list.addItem(item)
        options_layout.addWidget(self.template_list, 1)

        form = QFormLayout()
        self.gap = QDoubleSpinBox()
        self.gap.setRange(0.0, 16.0)
        self.gap.setSingleStep(0.5)
        self.gap.setValue(3.0)
        self.gap.setSuffix(" mm")
        self.width_percent = QSpinBox()
        self.width_percent.setRange(50, 100)
        self.width_percent.setValue(100)
        self.width_percent.setSuffix("%")
        self.height_percent = QSpinBox()
        self.height_percent.setRange(50, 100)
        self.height_percent.setValue(100)
        self.height_percent.setSuffix("%")
        form.addRow("Jarak antar foto", self.gap)
        form.addRow("Lebar kumpulan", self.width_percent)
        form.addRow("Tinggi kumpulan", self.height_percent)
        options_layout.addLayout(form)
        self.replace_pages = QCheckBox("Ganti seluruh halaman yang ada")
        self.replace_pages.setChecked(True)
        options_layout.addWidget(self.replace_pages)
        body.addWidget(options)
        body.setSizes((430, 510))
        layout.addWidget(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Terapkan Kolase ke Dokumen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        preferred_count = min(len(project.media), 8)
        preferred = next(
            (index for index, template in enumerate(TEMPLATES) if len(template.cells) == preferred_count),
            next((index for index, template in enumerate(TEMPLATES) if template.template_id == "grid-4"), 0),
        )
        self.template_list.setCurrentRow(preferred)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(90)
        self._preview_timer.timeout.connect(self._render_preview)
        self.template_list.currentItemChanged.connect(self._schedule_preview)
        self.gap.valueChanged.connect(self._schedule_preview)
        self.width_percent.valueChanged.connect(self._schedule_preview)
        self.height_percent.valueChanged.connect(self._schedule_preview)
        self._render_preview()

    @property
    def template_id(self) -> str:
        item = self.template_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else "grid-4"

    def _schedule_preview(self, *_args) -> None:
        self._preview_timer.start()

    def _render_preview(self, *_args) -> None:
        template = template_by_id(self.template_id)
        width, height = self.project.page_size_mm
        margins = (
            self.project.margins.top,
            self.project.margins.right,
            self.project.margins.bottom,
            self.project.margins.left,
        )
        scene = DocumentScene()
        scene.configure_page(width, height, margins, "#ffffff", self.project.letterhead)
        scene.apply_template(
            template.template_id,
            self.project.media[: len(template.cells)],
            gap=self.gap.value(),
            width_percent=self.width_percent.value(),
            height_percent=self.height_percent.value(),
        )
        image = scene.render_image(72)
        pixmap = QPixmap.fromImage(image).scaled(
            max(1, self.preview.width() - 24),
            max(1, self.preview.height() - 24),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scene.clear()
        self.preview.setPixmap(pixmap)
        pages = max(1, (len(self.project.media) + len(template.cells) - 1) // len(template.cells))
        self.preview_summary.setText(
            f"{template.name} · {len(template.cells)} foto/halaman · estimasi {pages} halaman"
        )


class PreviewDialog(QDialog):
    def __init__(self, project: DocumentProject, exporter: DocumentationExporter, parent=None):
        super().__init__(parent)
        self.project = project
        self.exporter = exporter
        self.index = 0
        self.setWindowTitle("Pratinjau Dokumentasi Foto")
        self.resize(900, 760)
        layout = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.label)
        layout.addWidget(scroll, 1)
        row = QHBoxLayout()
        previous = QPushButton("Halaman Sebelumnya")
        self.counter = QLabel()
        following = QPushButton("Halaman Berikutnya")
        print_button = QPushButton("Cetak…")
        print_button.setObjectName("PrimaryButton")
        row.addWidget(previous)
        row.addStretch()
        row.addWidget(self.counter)
        row.addStretch()
        row.addWidget(following)
        row.addWidget(print_button)
        layout.addLayout(row)
        previous.clicked.connect(lambda: self._move(-1))
        following.clicked.connect(lambda: self._move(1))
        print_button.clicked.connect(lambda: exporter.print_project(project, self))
        self._render()

    def _move(self, delta: int) -> None:
        self.index = max(0, min(len(self.project.pages) - 1, self.index + delta))
        self._render()

    def _render(self) -> None:
        scene = self.exporter._scene_for_page(self.project, self.index)
        image = scene.render_image(110)
        self.label.setPixmap(QPixmap.fromImage(image))
        scene.clear()
        self.counter.setText(f"Halaman {self.index + 1} dari {len(self.project.pages)}")


class DocumentationPhotoPage(QWidget):
    """Workspace DokuFoto asli-Qt yang hidup di halaman utama aplikasi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = DocumentProject()
        self.current_page_index = 0
        self.current_path: Path | None = None
        self.exporter = DocumentationExporter()
        self.history: list[str] = []
        self.history_index = -1
        self._restoring = False
        self._active_crop_item: PhotoItem | None = None
        self._thumbnail_cache: dict[str, tuple[int, QIcon]] = {}
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(650)
        self._autosave_timer.timeout.connect(self._write_autosave)
        self._build_ui()
        self._connect_shortcuts()
        self._load_autosave()
        if not self.project.letterhead.get("logo_left"):
            self.project.letterhead["logo_left"] = str(files("sekretariat_app.resources").joinpath("app_icon.ico"))
        if self.project.pages and not self.project.pages[0].elements:
            self._initialize_default_page()
        self._refresh_all(push_history=True)

    def _initialize_default_page(self) -> None:
        self._restoring = True
        width, height = self.project.page_size_mm
        margins = (
            self.project.margins.top,
            self.project.margins.right,
            self.project.margins.bottom,
            self.project.margins.left,
        )
        self.scene.configure_page(width, height, margins, "#ffffff", self.project.letterhead)
        self.scene.apply_template("grid-4")
        self.project.pages[0].collage = {
            "template_id": "grid-4",
            "gap_mm": 3.0,
            "width_percent": 100,
            "height_percent": 100,
        }
        text = TextElement(
            text="MASUKAN TEKS",
            x=35,
            y=7,
            width=max(80, width - 70),
            font_size=28,
            bold=True,
            underline=True,
            color="#e11d48",
        )
        self.scene.add_element(text.__dict__)
        self.project.pages[0].elements = self.scene.serialize_elements()
        self._restoring = False

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)
        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Dokumentasi Foto")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Workspace kolase WYSIWYG · seluruh pemrosesan berlangsung offline")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        title_row.addLayout(title_box)
        title_row.addStretch()
        badge = QLabel("●  OFFLINE")
        badge.setObjectName("OfflineBadge")
        title_row.addWidget(badge)
        root.addLayout(title_row)

        toolbar = QFrame()
        toolbar.setObjectName("ToolbarCard")
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_layout.setSpacing(6)
        tools = QHBoxLayout()
        tools.setSpacing(6)
        for text, slot in (
            ("Baru", self.new_project),
            ("Buka", self.open_project),
            ("Simpan", self.save_project),
            ("Arsip ZIP", self.export_archive),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            tools.addWidget(button)
        tools.addSpacing(6)
        self.undo_button = QPushButton("Urungkan")
        self.redo_button = QPushButton("Ulangi")
        self.undo_button.clicked.connect(self.undo)
        self.redo_button.clicked.connect(self.redo)
        tools.addWidget(self.undo_button)
        tools.addWidget(self.redo_button)
        tools.addStretch()
        preview = QPushButton("Pratinjau")
        preview.clicked.connect(self.preview)
        tools.addWidget(preview)
        docx = QPushButton("Ekspor DOCX")
        docx.clicked.connect(self.export_docx)
        tools.addWidget(docx)
        pdf = QPushButton("Ekspor PDF")
        pdf.clicked.connect(self.export_pdf)
        tools.addWidget(pdf)
        print_button = QPushButton("Cetak")
        print_button.setObjectName("PrimaryButton")
        print_button.clicked.connect(self.print_document)
        tools.addWidget(print_button)
        toolbar_layout.addLayout(tools)

        edit_tools = QHBoxLayout()
        edit_tools.setSpacing(6)
        for text, slot in (
            ("Impor Foto", self.import_photos),
            ("Impor Folder", self.import_folder),
            ("Kolase Otomatis", self.auto_collage),
            ("Tambah Teks", self.add_text),
            ("Atur Kertas && Margin", self.page_setup),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            edit_tools.addWidget(button)
        edit_tools.addStretch()
        hint = QLabel("Tarik foto ke kanvas · Ctrl+roda untuk zoom · Delete untuk menghapus")
        hint.setObjectName("MutedText")
        edit_tools.addWidget(hint)
        toolbar_layout.addLayout(edit_tools)
        root.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_left_panel())

        center = QFrame()
        center.setObjectName("CanvasCard")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(10, 10, 10, 8)
        canvas_toolbar = QHBoxLayout()
        self.project_title = QLineEdit(self.project.title)
        self.project_title.setPlaceholderText("Judul proyek dokumentasi")
        self.project_title.editingFinished.connect(self._update_project_title)
        canvas_toolbar.addWidget(QLabel("Proyek:"))
        canvas_toolbar.addWidget(self.project_title, 1)
        self.paper_badge = QLabel()
        self.paper_badge.setObjectName("OfflineBadge")
        canvas_toolbar.addWidget(self.paper_badge)
        zoom_out = QToolButton()
        zoom_out.setText("−")
        zoom_in = QToolButton()
        zoom_in.setText("+")
        fit = QPushButton("Pas Halaman")
        zoom_out.clicked.connect(lambda: self.view.scale(0.85, 0.85))
        zoom_in.clicked.connect(lambda: self.view.scale(1.15, 1.15))
        fit.clicked.connect(self._fit_page)
        canvas_toolbar.addWidget(zoom_out)
        canvas_toolbar.addWidget(zoom_in)
        canvas_toolbar.addWidget(fit)
        self.resize_collage_button = QPushButton("Ubah Ukuran Kolase")
        self.resize_collage_button.clicked.connect(self._toggle_collage_resize)
        canvas_toolbar.addWidget(self.resize_collage_button)
        center_layout.addLayout(canvas_toolbar)

        self.crop_toolbar = QFrame()
        self.crop_toolbar.setObjectName("ToolbarCard")
        crop_tools = QHBoxLayout(self.crop_toolbar)
        crop_tools.setContentsMargins(9, 6, 9, 6)
        crop_tools.setSpacing(7)
        crop_label = QLabel("Mode Crop")
        crop_label.setObjectName("PanelTitle")
        crop_tools.addWidget(crop_label)
        crop_tools.addWidget(QLabel("Zoom"))
        self.inline_crop_zoom = QSlider(Qt.Orientation.Horizontal)
        self.inline_crop_zoom.setRange(100, 500)
        self.inline_crop_zoom.setSingleStep(5)
        self.inline_crop_zoom.setMinimumWidth(150)
        self.inline_crop_zoom.valueChanged.connect(self._set_inline_crop_zoom)
        crop_tools.addWidget(self.inline_crop_zoom, 1)
        rotate_left = QPushButton("Putar −90°")
        rotate_right = QPushButton("Putar +90°")
        reset_crop = QPushButton("Reset")
        cancel_crop = QPushButton("Batal")
        apply_crop = QPushButton("Selesai Crop")
        apply_crop.setObjectName("PrimaryButton")
        rotate_left.clicked.connect(lambda: self._rotate_inline_crop(-90))
        rotate_right.clicked.connect(lambda: self._rotate_inline_crop(90))
        reset_crop.clicked.connect(self._reset_inline_crop)
        cancel_crop.clicked.connect(self._cancel_inline_crop)
        apply_crop.clicked.connect(self._apply_inline_crop)
        for control in (rotate_left, rotate_right, reset_crop, cancel_crop, apply_crop):
            crop_tools.addWidget(control)
        self.crop_toolbar.setVisible(False)
        center_layout.addWidget(self.crop_toolbar)

        self.scene = DocumentScene(self)
        self.view = CanvasView(self.scene)
        self.view.files_dropped.connect(self._add_media_paths)
        center_layout.addWidget(self.view, 1)
        self.status = QLabel("Siap. Tarik foto dari Windows Explorer ke area kerja.")
        self.status.setObjectName("StatusLabel")
        center_layout.addWidget(self.status)
        splitter.addWidget(center)
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([285, 900, 260])
        root.addWidget(splitter, 1)

        self.scene.content_changed.connect(self._on_scene_changed)
        self.scene.crop_requested.connect(self._begin_inline_crop)
        self.scene.selectionChanged.connect(self._selection_changed)
        self.scene.focusItemChanged.connect(lambda new, old, reason: self._on_scene_changed() if isinstance(old, TextItem) else None)

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("SidePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        tabs = QTabWidget()
        tabs.addTab(self._templates_tab(), "Template")
        tabs.addTab(self._media_tab(), "Media")
        tabs.addTab(self._letterhead_tab(), "Kop Surat")
        tabs.addTab(self._properties_tab(), "Properti")
        layout.addWidget(tabs)
        return panel

    def _templates_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        info = QLabel("Pilih kisi. Foto yang sudah terpasang akan dipertahankan sesuai urutan.")
        info.setWordWrap(True)
        info.setObjectName("MutedText")
        layout.addWidget(info)
        self.template_list = QListWidget()
        self.template_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.template_list.setIconSize(QSize(184, 104))
        self.template_list.setGridSize(QSize(224, 148))
        self.template_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.template_list.setMovement(QListWidget.Movement.Static)
        self.template_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for template in TEMPLATES:
            item = QListWidgetItem(_template_icon(template.template_id), template.name)
            item.setData(Qt.ItemDataRole.UserRole, template.template_id)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setToolTip(template.description)
            self.template_list.addItem(item)
        self.template_list.itemDoubleClicked.connect(lambda item: self.apply_template(item.data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.template_list, 1)
        apply_button = QPushButton("Terapkan Template")
        apply_button.setObjectName("PrimaryButton")
        apply_button.clicked.connect(self._apply_selected_template)
        layout.addWidget(apply_button)
        custom_box = QFrame()
        custom_box.setObjectName("InsetCard")
        custom_layout = QFormLayout(custom_box)
        self.custom_columns = QSpinBox()
        self.custom_columns.setRange(1, 6)
        self.custom_columns.setValue(2)
        self.custom_rows = QSpinBox()
        self.custom_rows.setRange(1, 6)
        self.custom_rows.setValue(2)
        custom_layout.addRow("Kolom", self.custom_columns)
        custom_layout.addRow("Baris", self.custom_rows)
        custom_apply = QPushButton("Buat Kisi Kustom")
        custom_apply.clicked.connect(self.apply_custom_grid)
        custom_layout.addRow(custom_apply)
        layout.addWidget(custom_box)

        collage_box = QFrame()
        collage_box.setObjectName("InsetCard")
        collage_layout = QFormLayout(collage_box)
        self.collage_gap = QDoubleSpinBox()
        self.collage_gap.setRange(0.0, 16.0)
        self.collage_gap.setSingleStep(0.5)
        self.collage_gap.setValue(3.0)
        self.collage_gap.setSuffix(" mm")
        self.collage_width = QSpinBox()
        self.collage_width.setRange(50, 100)
        self.collage_width.setValue(100)
        self.collage_width.setSuffix("%")
        self.collage_height = QSpinBox()
        self.collage_height.setRange(50, 100)
        self.collage_height.setValue(100)
        self.collage_height.setSuffix("%")
        collage_layout.addRow("Jarak foto", self.collage_gap)
        collage_layout.addRow("Lebar kolase", self.collage_width)
        collage_layout.addRow("Tinggi kolase", self.collage_height)
        resize_collage = QPushButton("Terapkan Ukuran Kolase")
        resize_collage.clicked.connect(self._apply_collage_settings)
        collage_layout.addRow(resize_collage)
        layout.addWidget(collage_box)
        return widget

    def _letterhead_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        self.letterhead_enabled = QCheckBox("Tampilkan kop pada halaman pertama")
        self.letterhead_enabled.toggled.connect(self._update_letterhead)
        layout.addWidget(self.letterhead_enabled)
        form = QFormLayout()
        self.letterhead_government = QLineEdit()
        self.letterhead_agency = QLineEdit()
        self.letterhead_sub_agency = QLineEdit()
        self.letterhead_address = QTextEdit()
        self.letterhead_address.setMaximumHeight(70)
        self.letterhead_contact = QLineEdit()
        self.letterhead_border = QComboBox()
        self.letterhead_border.addItems(("double", "single", "bold", "none"))
        form.addRow("Pemerintah", self.letterhead_government)
        form.addRow("Instansi", self.letterhead_agency)
        form.addRow("Sub-instansi", self.letterhead_sub_agency)
        form.addRow("Alamat", self.letterhead_address)
        form.addRow("Kontak", self.letterhead_contact)
        form.addRow("Garis kop", self.letterhead_border)
        layout.addLayout(form)
        for field in (
            self.letterhead_government,
            self.letterhead_agency,
            self.letterhead_sub_agency,
            self.letterhead_contact,
        ):
            field.editingFinished.connect(self._update_letterhead)
        self.letterhead_address.textChanged.connect(self._schedule_letterhead_update)
        self.letterhead_border.currentTextChanged.connect(self._update_letterhead)
        logo_card = QFrame()
        logo_card.setObjectName("InsetCard")
        logo_layout = QVBoxLayout(logo_card)
        self.logo_left_path = QLabel()
        self.logo_left_path.setWordWrap(True)
        self.logo_left_path.setObjectName("MutedText")
        choose_left = QPushButton("Pilih Logo Kiri…")
        choose_left.clicked.connect(lambda: self._choose_letterhead_logo("logo_left"))
        self.logo_right_path = QLabel()
        self.logo_right_path.setWordWrap(True)
        self.logo_right_path.setObjectName("MutedText")
        choose_right = QPushButton("Pilih Logo Kanan…")
        choose_right.clicked.connect(lambda: self._choose_letterhead_logo("logo_right"))
        logo_layout.addWidget(QLabel("Logo kiri"))
        logo_layout.addWidget(self.logo_left_path)
        logo_layout.addWidget(choose_left)
        logo_layout.addWidget(QLabel("Logo kanan"))
        logo_layout.addWidget(self.logo_right_path)
        logo_layout.addWidget(choose_right)
        layout.addWidget(logo_card)
        layout.addStretch()
        scroll.setWidget(body)
        return scroll

    def _media_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        row = QHBoxLayout()
        add = QPushButton("Tambah Foto")
        add.clicked.connect(self.import_photos)
        folder = QPushButton("Folder")
        folder.clicked.connect(self.import_folder)
        row.addWidget(add)
        row.addWidget(folder)
        layout.addLayout(row)
        self.media_list = QListWidget()
        self.media_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.media_list.setIconSize(QSize(72, 72))
        self.media_list.setGridSize(QSize(105, 104))
        self.media_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.media_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.media_list.itemDoubleClicked.connect(self._assign_media_item)
        layout.addWidget(self.media_list, 1)
        assign = QPushButton("Pasang ke Slot Terpilih")
        assign.setObjectName("PrimaryButton")
        assign.clicked.connect(self.assign_selected_media)
        layout.addWidget(assign)
        remove = QPushButton("Hapus dari Media")
        remove.clicked.connect(self.remove_selected_media)
        layout.addWidget(remove)
        return widget

    def _properties_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        self.property_form = QFormLayout(body)
        self.property_hint = QLabel("Pilih foto atau teks pada kanvas untuk mengubah propertinya.")
        self.property_hint.setWordWrap(True)
        self.property_form.addRow(self.property_hint)

        self.fit_combo = QComboBox()
        self.fit_combo.addItems(("cover", "contain", "fill"))
        self.fit_combo.currentTextChanged.connect(self._apply_photo_properties)
        self.caption_field = QLineEdit()
        self.caption_field.editingFinished.connect(self._apply_photo_properties)
        self.caption_check = QCheckBox("Tampilkan keterangan")
        self.caption_check.toggled.connect(self._apply_photo_properties)
        self.border_spin = QDoubleSpinBox()
        self.border_spin.setRange(0, 8)
        self.border_spin.setSingleStep(0.25)
        self.border_spin.valueChanged.connect(self._apply_photo_properties)
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(0, 32)
        self.radius_spin.valueChanged.connect(self._apply_photo_properties)
        self.photo_width = QDoubleSpinBox()
        self.photo_width.setRange(PhotoItem.MIN_SIZE, 600.0)
        self.photo_width.setDecimals(1)
        self.photo_width.setSuffix(" mm")
        self.photo_width.valueChanged.connect(self._apply_photo_geometry)
        self.photo_height = QDoubleSpinBox()
        self.photo_height.setRange(PhotoItem.MIN_SIZE, 600.0)
        self.photo_height.setDecimals(1)
        self.photo_height.setSuffix(" mm")
        self.photo_height.valueChanged.connect(self._apply_photo_geometry)
        self.photo_aspect_lock = QCheckBox("Pertahankan rasio frame")
        self.photo_aspect_lock.setChecked(False)
        self.rotation_spin = QDoubleSpinBox()
        self.rotation_spin.setRange(-360, 360)
        self.rotation_spin.valueChanged.connect(self._apply_common_properties)
        self.lock_check = QCheckBox("Kunci elemen")
        self.lock_check.toggled.connect(self._apply_common_properties)
        self.crop_button = QPushButton("Crop Langsung di Kanvas")
        self.crop_button.clicked.connect(self._crop_selected)
        self.replace_button = QPushButton("Ganti Foto…")
        self.replace_button.clicked.connect(self.replace_selected_photo)

        self.text_editor = QTextEdit()
        self.text_editor.setMaximumHeight(100)
        self.text_editor.textChanged.connect(self._apply_text_properties)
        self.font_combo = QComboBox()
        self.font_combo.addItems(("Arial", "Calibri", "Times New Roman", "Poppins", "Montserrat", "Segoe UI"))
        self.font_combo.currentTextChanged.connect(self._apply_text_properties)
        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(6, 144)
        self.font_size.valueChanged.connect(self._apply_text_properties)
        self.text_width = QDoubleSpinBox()
        self.text_width.setRange(15, 500)
        self.text_width.setSuffix(" mm")
        self.text_width.valueChanged.connect(self._apply_text_properties)
        self.text_alignment = QComboBox()
        self.text_alignment.addItems(("left", "center", "right", "justify"))
        self.text_alignment.currentTextChanged.connect(self._apply_text_properties)
        self.letter_spacing = QDoubleSpinBox()
        self.letter_spacing.setRange(-2, 20)
        self.letter_spacing.setSingleStep(0.25)
        self.letter_spacing.valueChanged.connect(self._apply_text_properties)
        self.line_height = QDoubleSpinBox()
        self.line_height.setRange(0.8, 3.0)
        self.line_height.setSingleStep(0.1)
        self.line_height.valueChanged.connect(self._apply_text_properties)
        self.text_opacity = QSpinBox()
        self.text_opacity.setRange(10, 100)
        self.text_opacity.setSuffix("%")
        self.text_opacity.valueChanged.connect(self._apply_text_properties)
        self.text_effect = QComboBox()
        self.text_effect.addItems(("none", "shadow", "glow"))
        self.text_effect.currentTextChanged.connect(self._apply_text_properties)
        self.bold_check = QCheckBox("Tebal")
        self.italic_check = QCheckBox("Miring")
        self.underline_check = QCheckBox("Garis bawah")
        for control in (self.bold_check, self.italic_check, self.underline_check):
            control.toggled.connect(self._apply_text_properties)
        self.text_color_button = QPushButton("Warna Teks…")
        self.text_color_button.clicked.connect(self._choose_text_color)
        self.text_background_button = QPushButton("Warna Latar…")
        self.text_background_button.clicked.connect(self._choose_text_background)
        self.text_effect_color_button = QPushButton("Warna Efek…")
        self.text_effect_color_button.clicked.connect(self._choose_text_effect_color)
        self.delete_element_button = QPushButton("Hapus Elemen")
        self.delete_element_button.setObjectName("DangerButton")
        self.delete_element_button.clicked.connect(self.delete_selected)

        self.photo_controls = [
            ("Mode gambar", self.fit_combo),
            ("Lebar frame", self.photo_width),
            ("Tinggi frame", self.photo_height),
            ("", self.photo_aspect_lock),
            ("Keterangan", self.caption_field),
            ("", self.caption_check),
            ("Tebal bingkai", self.border_spin),
            ("Sudut bulat", self.radius_spin),
            ("", self.crop_button),
            ("", self.replace_button),
        ]
        self.text_controls = [
            ("Isi teks", self.text_editor),
            ("Font", self.font_combo),
            ("Ukuran", self.font_size),
            ("Lebar kotak", self.text_width),
            ("Perataan", self.text_alignment),
            ("Jarak huruf", self.letter_spacing),
            ("Tinggi baris", self.line_height),
            ("Opasitas", self.text_opacity),
            ("Efek", self.text_effect),
            ("", self.bold_check),
            ("", self.italic_check),
            ("", self.underline_check),
            ("", self.text_color_button),
            ("", self.text_background_button),
            ("", self.text_effect_color_button),
        ]
        self.common_controls = [
            ("Rotasi elemen", self.rotation_spin),
            ("", self.lock_check),
            ("", self.delete_element_button),
        ]
        for label, control in self.photo_controls + self.text_controls + self.common_controls:
            self.property_form.addRow(label, control)
            self._set_property_control_visible(control, False)
        scroll.setWidget(body)
        return scroll

    def _build_right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("SidePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        heading = QLabel("Halaman")
        heading.setObjectName("PanelTitle")
        layout.addWidget(heading)
        self.page_list = QListWidget()
        self.page_list.currentRowChanged.connect(self.set_current_page)
        layout.addWidget(self.page_list, 1)
        row = QGridLayout()
        add = QPushButton("+ Halaman")
        duplicate = QPushButton("Duplikat")
        remove = QPushButton("Hapus")
        add.clicked.connect(self.add_page)
        duplicate.clicked.connect(self.duplicate_page)
        remove.clicked.connect(self.delete_page)
        row.addWidget(add, 0, 0)
        row.addWidget(duplicate, 0, 1)
        row.addWidget(remove, 1, 0, 1, 2)
        layout.addLayout(row)
        help_text = QLabel(
            "Kontrol kanvas:\n"
            "• Seret elemen untuk memindahkan\n"
            "• Seret pegangan putih untuk resize frame\n"
            "• Ubah Ukuran Kolase untuk skala bersama\n"
            "• Klik ganda foto untuk crop langsung\n"
            "• Klik ganda teks untuk mengetik\n"
            "• Roda mouse saat crop untuk zoom\n"
            "• Ctrl + roda mouse untuk zoom kanvas"
        )
        help_text.setWordWrap(True)
        help_text.setObjectName("HelpCard")
        layout.addWidget(help_text)
        return panel

    def _connect_shortcuts(self) -> None:
        QShortcut(QKeySequence.StandardKey.Save, self, self.save_project)
        QShortcut(QKeySequence.StandardKey.Open, self, self.open_project)
        QShortcut(QKeySequence.StandardKey.Undo, self, self.undo)
        QShortcut(QKeySequence.StandardKey.Redo, self, self.redo)
        QShortcut(QKeySequence.StandardKey.Delete, self, self.delete_selected)
        QShortcut(QKeySequence("Escape"), self, self._cancel_inline_crop)
        QShortcut(QKeySequence("Ctrl+Return"), self, self._apply_inline_crop)

    def _load_autosave(self) -> None:
        path = autosave_path()
        if path.exists():
            try:
                self.project = DocumentProject.load(path)
                self.status_text("Autosave proyek sebelumnya berhasil dipulihkan.")
            except Exception:
                pass

    def _refresh_all(self, push_history: bool = False) -> None:
        self._restoring = True
        self.current_page_index = max(0, min(self.current_page_index, len(self.project.pages) - 1))
        with QSignalBlocker(self.page_list):
            self.page_list.clear()
            for index, page in enumerate(self.project.pages):
                self.page_list.addItem(f"{index + 1}. {page.title}")
            self.page_list.setCurrentRow(self.current_page_index)
        with QSignalBlocker(self.project_title):
            self.project_title.setText(self.project.title)
        width, height = self.project.page_size_mm
        self.paper_badge.setText(
            f"{self.project.paper_size} · {width:g} × {height:g} mm · {self.project.orientation.title()}"
        )
        self._load_current_scene()
        self._refresh_media()
        self._refresh_letterhead_controls()
        self._restoring = False
        if push_history:
            self._push_history(force=True)
        QTimer.singleShot(0, self._fit_page)

    def _load_current_scene(self) -> None:
        if self.scene.active_crop_item is not None:
            self.scene.finish_crop(False)
        if self.scene.collage_overlay is not None:
            self.scene.finish_collage_resize(False)
        self._reset_editor_mode_ui()
        page = self.project.pages[self.current_page_index]
        width, height = self.project.page_size_mm
        margins = (self.project.margins.top, self.project.margins.right, self.project.margins.bottom, self.project.margins.left)
        letterhead = self.project.letterhead if self.current_page_index == 0 else {**self.project.letterhead, "enabled": False}
        self.scene.load_page(page, width, height, margins, letterhead)
        collage = page.collage or {}
        if hasattr(self, "collage_gap"):
            controls = (self.collage_gap, self.collage_width, self.collage_height)
            blockers = [QSignalBlocker(control) for control in controls]
            self.collage_gap.setValue(float(collage.get("gap_mm", 3.0)))
            self.collage_width.setValue(int(collage.get("width_percent", 100)))
            self.collage_height.setValue(int(collage.get("height_percent", 100)))
            del blockers
            template_id = str(collage.get("template_id", ""))
            if template_id:
                for index in range(self.template_list.count()):
                    item = self.template_list.item(index)
                    if item.data(Qt.ItemDataRole.UserRole) == template_id:
                        with QSignalBlocker(self.template_list):
                            self.template_list.setCurrentRow(index)
                        break

    def _refresh_letterhead_controls(self) -> None:
        data = self.project.letterhead
        controls = (
            self.letterhead_enabled,
            self.letterhead_government,
            self.letterhead_agency,
            self.letterhead_sub_agency,
            self.letterhead_address,
            self.letterhead_contact,
            self.letterhead_border,
        )
        blockers = [QSignalBlocker(control) for control in controls]
        self.letterhead_enabled.setChecked(bool(data.get("enabled", False)))
        self.letterhead_government.setText(str(data.get("government_name", "")))
        self.letterhead_agency.setText(str(data.get("agency_name", "")))
        self.letterhead_sub_agency.setText(str(data.get("sub_agency_name", "")))
        self.letterhead_address.setPlainText(str(data.get("address", "")))
        self.letterhead_contact.setText(str(data.get("contact", "")))
        self.letterhead_border.setCurrentText(str(data.get("border_style", "double")))
        self.logo_left_path.setText(Path(str(data.get("logo_left", ""))).name or "Belum dipilih")
        self.logo_right_path.setText(Path(str(data.get("logo_right", ""))).name or "Belum dipilih")
        del blockers

    def _schedule_letterhead_update(self) -> None:
        QTimer.singleShot(350, self._update_letterhead)

    def _update_letterhead(self) -> None:
        if self._restoring:
            return
        self._save_current_scene()
        was_enabled = bool(self.project.letterhead.get("enabled", False))
        enabled = self.letterhead_enabled.isChecked()
        self.project.letterhead.update(
            enabled=enabled,
            government_name=self.letterhead_government.text().strip(),
            agency_name=self.letterhead_agency.text().strip(),
            sub_agency_name=self.letterhead_sub_agency.text().strip(),
            address=self.letterhead_address.toPlainText().strip(),
            contact=self.letterhead_contact.text().strip(),
            border_style=self.letterhead_border.currentText(),
        )
        if was_enabled != enabled and self.project.pages:
            delta = 31.0 if enabled else -31.0
            for element in self.project.pages[0].elements:
                element["y"] = max(self.project.margins.top, float(element.get("y", 0)) + delta)
        self._load_current_scene()
        self._push_history()
        self._schedule_autosave()

    def _choose_letterhead_logo(self, key: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Pilih logo kop surat", "", IMAGE_FILTER + ";;Icon (*.ico)")
        if not path:
            return
        self.project.letterhead[key] = str(Path(path).resolve())
        self._refresh_letterhead_controls()
        self._load_current_scene()
        self._push_history()
        self._schedule_autosave()

    def _save_current_scene(self) -> None:
        if self._restoring or not self.project.pages:
            return
        self.project.pages[self.current_page_index].elements = self.scene.serialize_elements()
        self.project.touch()

    def _on_scene_changed(self) -> None:
        if self._restoring:
            return
        self._selection_changed()
        self._save_current_scene()
        self._push_history()
        self._schedule_autosave()

    def _schedule_autosave(self) -> None:
        self._autosave_timer.start()

    def _write_autosave(self) -> None:
        try:
            self._save_current_scene()
            self.project.save(autosave_path())
        except Exception:
            self.status_text("Autosave gagal; simpan proyek secara manual.", error=True)

    def _push_history(self, force: bool = False) -> None:
        snapshot = json.dumps(self.project.to_dict(), ensure_ascii=False, sort_keys=True)
        if not force and self.history_index >= 0 and self.history[self.history_index] == snapshot:
            return
        del self.history[self.history_index + 1 :]
        self.history.append(snapshot)
        if len(self.history) > 30:
            self.history.pop(0)
        self.history_index = len(self.history) - 1
        self._update_history_buttons()

    def undo(self) -> None:
        if self.history_index <= 0:
            return
        self.history_index -= 1
        self._restore_history()

    def redo(self) -> None:
        if self.history_index >= len(self.history) - 1:
            return
        self.history_index += 1
        self._restore_history()

    def _restore_history(self) -> None:
        self.project = DocumentProject.from_dict(json.loads(self.history[self.history_index]))
        self._refresh_all(push_history=False)
        self._update_history_buttons()
        self._schedule_autosave()

    def _update_history_buttons(self) -> None:
        self.undo_button.setEnabled(self.history_index > 0)
        self.redo_button.setEnabled(self.history_index < len(self.history) - 1)

    def set_current_page(self, index: int) -> None:
        if self._restoring or index < 0 or index >= len(self.project.pages) or index == self.current_page_index:
            return
        if self._active_crop_item is not None:
            self._finish_inline_crop(True)
        if self.scene.collage_overlay is not None:
            self.scene.finish_collage_resize()
            self.resize_collage_button.setText("Ubah Ukuran Kolase")
        self._save_current_scene()
        self.current_page_index = index
        self._load_current_scene()
        QTimer.singleShot(0, self._fit_page)

    def add_page(self) -> None:
        self._save_current_scene()
        page = DocumentPage(title=f"Halaman {len(self.project.pages) + 1}")
        self.project.pages.append(page)
        self.current_page_index = len(self.project.pages) - 1
        self._refresh_all()
        self._push_history()

    def duplicate_page(self) -> None:
        self._save_current_scene()
        source = self.project.pages[self.current_page_index]
        copy = DocumentPage.from_dict(source.__dict__) if hasattr(DocumentPage, "from_dict") else DocumentPage(
            title=f"{source.title} (Salinan)",
            elements=json.loads(json.dumps(source.elements)),
            background=source.background,
            collage=json.loads(json.dumps(source.collage)),
        )
        self.project.pages.insert(self.current_page_index + 1, copy)
        self.current_page_index += 1
        self._refresh_all()
        self._push_history()

    def delete_page(self) -> None:
        if len(self.project.pages) == 1:
            QMessageBox.information(self, "Halaman terakhir", "Proyek harus memiliki minimal satu halaman.")
            return
        self.project.pages.pop(self.current_page_index)
        self.current_page_index = min(self.current_page_index, len(self.project.pages) - 1)
        self._refresh_all()
        self._push_history()

    def _apply_selected_template(self) -> None:
        item = self.template_list.currentItem()
        if not item:
            QMessageBox.information(self, "Pilih template", "Pilih salah satu template terlebih dahulu.")
            return
        self.apply_template(item.data(Qt.ItemDataRole.UserRole))

    def apply_template(self, template_id: str) -> None:
        self._close_canvas_modes(commit_crop=True, commit_collage=False)
        self.project.pages[self.current_page_index].collage = {
            "template_id": template_id,
            "gap_mm": self.collage_gap.value(),
            "width_percent": self.collage_width.value(),
            "height_percent": self.collage_height.value(),
        }
        self.scene.apply_template(
            template_id,
            gap=self.collage_gap.value(),
            width_percent=self.collage_width.value(),
            height_percent=self.collage_height.value(),
        )
        self.status_text("Template diterapkan. Klik ganda slot untuk memilih atau mengatur foto.")

    def _apply_collage_settings(self) -> None:
        page = self.project.pages[self.current_page_index]
        template_id = str((page.collage or {}).get("template_id", ""))
        if not template_id:
            item = self.template_list.currentItem()
            template_id = str(item.data(Qt.ItemDataRole.UserRole)) if item else "grid-4"
        self.apply_template(template_id)
        self.status_text(
            f"Ukuran kumpulan foto diperbarui: {self.collage_width.value()}% × "
            f"{self.collage_height.value()}%, jarak {self.collage_gap.value():g} mm."
        )

    def apply_custom_grid(self) -> None:
        self._close_canvas_modes(commit_crop=True, commit_collage=False)
        columns = self.custom_columns.value()
        rows = self.custom_rows.value()
        top, right, bottom, left = self.scene.effective_margins()
        gap = 3.0
        usable_width = self.scene.page_width - left - right
        usable_height = self.scene.page_height - top - bottom
        width = (usable_width - gap * (columns - 1)) / columns
        height = (usable_height - gap * (rows - 1)) / rows
        existing = [item.to_data().get("photo_path", "") for item in self.scene.items() if isinstance(item, PhotoItem)]
        for item in list(self.scene.items()):
            if isinstance(item, PhotoItem):
                self.scene.removeItem(item)
        index = 0
        for row in range(rows):
            for column in range(columns):
                data = PhotoElement(
                    photo_path=existing[index] if index < len(existing) else "",
                    x=left + column * (width + gap),
                    y=top + row * (height + gap),
                    width=width,
                    height=height,
                ).__dict__
                self.scene.add_element(data)
                index += 1
        self.project.pages[self.current_page_index].collage = {
            "custom_rows": rows,
            "custom_columns": columns,
            "gap_mm": gap,
            "width_percent": 100,
            "height_percent": 100,
        }
        self.scene.content_changed.emit()

    def auto_collage(self) -> None:
        self._close_canvas_modes(commit_crop=True, commit_collage=True)
        if not self.project.media:
            QMessageBox.information(self, "Media kosong", "Impor foto terlebih dahulu sebelum membuat kolase otomatis.")
            return
        dialog = AutoCollageDialog(self.project, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._save_current_scene()
        template_id = dialog.template_id
        template = next(template for template in TEMPLATES if template.template_id == template_id)
        slot_count = len(template.cells)
        generated: list[DocumentPage] = []
        width, height = self.project.page_size_mm
        base_margins = (
            self.project.margins.top,
            self.project.margins.right,
            self.project.margins.bottom,
            self.project.margins.left,
        )
        for offset in range(0, len(self.project.media), slot_count):
            paths = self.project.media[offset : offset + slot_count]
            page_number = len(generated) + 1
            page = DocumentPage(title=f"Halaman {page_number}")
            scene = DocumentScene()
            letterhead = self.project.letterhead if page_number == 1 else {**self.project.letterhead, "enabled": False}
            scene.configure_page(width, height, base_margins, page.background, letterhead)
            page.collage = {
                "template_id": template_id,
                "gap_mm": dialog.gap.value(),
                "width_percent": dialog.width_percent.value(),
                "height_percent": dialog.height_percent.value(),
            }
            scene.apply_template(
                template_id,
                paths,
                gap=dialog.gap.value(),
                width_percent=dialog.width_percent.value(),
                height_percent=dialog.height_percent.value(),
            )
            page.elements = scene.serialize_elements()
            generated.append(page)
        if dialog.replace_pages.isChecked():
            self.project.pages = generated
            self.current_page_index = 0
        else:
            start = len(self.project.pages)
            for index, page in enumerate(generated, start=start + 1):
                page.title = f"Halaman {index}"
            self.project.pages.extend(generated)
            self.current_page_index = start
        self._refresh_all()
        self._push_history()
        self._schedule_autosave()
        self.status_text(f"Kolase otomatis selesai: {len(generated)} halaman dari {len(self.project.media)} foto.")

    def import_photos(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Impor foto", "", IMAGE_FILTER)
        self._add_media_paths(files)

    def import_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Pilih folder foto")
        if not directory:
            return
        paths = [str(path) for path in sorted(Path(directory).iterdir()) if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}]
        self._add_media_paths(paths)

    def _add_media_paths(self, paths: list[str]) -> None:
        valid = []
        for path in paths:
            source = Path(path)
            if source.exists() and source.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                value = str(source.resolve())
                if value not in self.project.media:
                    self.project.media.append(value)
                    valid.append(value)
        if not valid:
            return
        self._refresh_media()
        self._push_history()
        self._schedule_autosave()
        self.status_text(f"{len(valid)} foto ditambahkan ke Media.")

    def _refresh_media(self) -> None:
        self.media_list.clear()
        current_paths = set(self.project.media)
        self._thumbnail_cache = {
            path: cached
            for path, cached in self._thumbnail_cache.items()
            if path in current_paths
        }
        for path in self.project.media:
            source = Path(path)
            try:
                modified = source.stat().st_mtime_ns
            except OSError:
                modified = 0
            cached = self._thumbnail_cache.get(path)
            if cached is None or cached[0] != modified:
                cached = (modified, QIcon(_scaled_pixmap(path, QSize(160, 120))))
                self._thumbnail_cache[path] = cached
            item = QListWidgetItem(cached[1], source.name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.media_list.addItem(item)

    def _assign_media_item(self, item: QListWidgetItem) -> None:
        self._assign_photo_path(str(item.data(Qt.ItemDataRole.UserRole)))

    def assign_selected_media(self) -> None:
        item = self.media_list.currentItem()
        if not item:
            QMessageBox.information(self, "Pilih foto", "Pilih satu foto di panel Media.")
            return
        self._assign_photo_path(str(item.data(Qt.ItemDataRole.UserRole)))

    def _assign_photo_path(self, path: str) -> None:
        selected = self.scene.selected_editable()
        target = selected if isinstance(selected, PhotoItem) else next(
            (item for item in reversed(self.scene.items()) if isinstance(item, PhotoItem) and not item.data.get("photo_path")),
            None,
        )
        if isinstance(target, PhotoItem):
            target.data["photo_path"] = path
            target._loaded_path = ""
            target.update()
        else:
            width = min(90.0, self.scene.page_width - 30)
            item = self.scene.add_element(PhotoElement(photo_path=path, x=20, y=25, width=width, height=width * 0.72).__dict__)
            item.setSelected(True)
        self.scene.content_changed.emit()

    def remove_selected_media(self) -> None:
        selected_paths = {str(item.data(Qt.ItemDataRole.UserRole)) for item in self.media_list.selectedItems()}
        if not selected_paths:
            return
        self.project.media = [path for path in self.project.media if path not in selected_paths]
        self._refresh_media()
        self._push_history()
        self._schedule_autosave()

    def replace_selected_photo(self) -> None:
        selected = self.scene.selected_editable()
        if not isinstance(selected, PhotoItem):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Ganti foto", "", IMAGE_FILTER)
        if path:
            self._add_media_paths([path])
            self._assign_photo_path(str(Path(path).resolve()))

    def add_text(self) -> None:
        self.scene.add_text()

    def delete_selected(self) -> None:
        if self._active_crop_item is not None:
            self._cancel_inline_crop()
            return
        self.scene.delete_selected()

    def _selection_changed(self) -> None:
        selected = self.scene.selected_editable()
        self.property_hint.setVisible(selected is None)
        for _, control in self.photo_controls:
            self._set_property_control_visible(control, isinstance(selected, PhotoItem))
        for _, control in self.text_controls:
            self._set_property_control_visible(control, isinstance(selected, TextItem))
        for _, control in self.common_controls:
            self._set_property_control_visible(control, selected is not None)
        if not selected:
            return
        blockers = [
            QSignalBlocker(control)
            for control in (
                self.fit_combo,
                self.caption_field,
                self.caption_check,
                self.border_spin,
                self.radius_spin,
                self.photo_width,
                self.photo_height,
                self.photo_aspect_lock,
                self.rotation_spin,
                self.lock_check,
                self.text_editor,
                self.font_combo,
                self.font_size,
                self.text_width,
                self.text_alignment,
                self.letter_spacing,
                self.line_height,
                self.text_opacity,
                self.text_effect,
                self.bold_check,
                self.italic_check,
                self.underline_check,
            )
        ]
        self.rotation_spin.setValue(float(selected.data.get("rotation", 0)))
        self.lock_check.setChecked(bool(selected.data.get("locked", False)))
        if isinstance(selected, PhotoItem):
            self.fit_combo.setCurrentText(str(selected.data.get("fit", "cover")))
            self.caption_field.setText(str(selected.data.get("caption", "")))
            self.caption_check.setChecked(bool(selected.data.get("show_caption", False)))
            self.border_spin.setValue(float(selected.data.get("border_width", 0.5)))
            self.radius_spin.setValue(float(selected.data.get("radius", 1.5)))
            self.photo_width.setValue(selected._rect.width())
            self.photo_height.setValue(selected._rect.height())
        elif isinstance(selected, TextItem):
            self.text_editor.setPlainText(selected.toPlainText())
            self.font_combo.setCurrentText(str(selected.data.get("font_family", "Arial")))
            self.font_size.setValue(float(selected.data.get("font_size", 14)))
            self.text_width.setValue(float(selected.data.get("width", 120)))
            self.text_alignment.setCurrentText(str(selected.data.get("alignment", "left")))
            self.letter_spacing.setValue(float(selected.data.get("letter_spacing", 0)))
            self.line_height.setValue(float(selected.data.get("line_height", 1.2)))
            self.text_opacity.setValue(round(float(selected.data.get("opacity", 1)) * 100))
            self.text_effect.setCurrentText(str(selected.data.get("effect", "none")))
            self.bold_check.setChecked(bool(selected.data.get("bold", False)))
            self.italic_check.setChecked(bool(selected.data.get("italic", False)))
            self.underline_check.setChecked(bool(selected.data.get("underline", False)))
        del blockers

    def _set_property_control_visible(self, control: QWidget, visible: bool) -> None:
        control.setVisible(visible)
        label = self.property_form.labelForField(control)
        if label:
            label.setVisible(visible)

    def _apply_photo_properties(self) -> None:
        item = self.scene.selected_editable()
        if not isinstance(item, PhotoItem):
            return
        item.data.update(
            fit=self.fit_combo.currentText(),
            caption=self.caption_field.text(),
            show_caption=self.caption_check.isChecked(),
            border_width=self.border_spin.value(),
            radius=self.radius_spin.value(),
        )
        item.update()
        self.scene.content_changed.emit()

    def _apply_photo_geometry(self) -> None:
        item = self.scene.selected_editable()
        if not isinstance(item, PhotoItem) or item.crop_mode:
            return
        width = self.photo_width.value()
        height = self.photo_height.value()
        ratio = item._rect.width() / max(PhotoItem.MIN_SIZE, item._rect.height())
        if self.photo_aspect_lock.isChecked():
            if self.sender() is self.photo_width:
                height = width / max(0.01, ratio)
            else:
                width = height * ratio
        width = min(width, max(PhotoItem.MIN_SIZE, self.scene.paper_rect.right() - item.pos().x()))
        height = min(height, max(PhotoItem.MIN_SIZE, self.scene.paper_rect.bottom() - item.pos().y()))
        blockers = (QSignalBlocker(self.photo_width), QSignalBlocker(self.photo_height))
        self.photo_width.setValue(width)
        self.photo_height.setValue(height)
        del blockers
        item.set_frame_size(width, height)
        self.scene.content_changed.emit()

    def _apply_common_properties(self) -> None:
        item = self.scene.selected_editable()
        if not item:
            return
        item.data["rotation"] = self.rotation_spin.value()
        item.setRotation(self.rotation_spin.value())
        item.set_locked(self.lock_check.isChecked())
        self.scene.content_changed.emit()

    def _apply_text_properties(self) -> None:
        item = self.scene.selected_editable()
        if not isinstance(item, TextItem):
            return
        item.data.update(
            text=self.text_editor.toPlainText(),
            font_family=self.font_combo.currentText(),
            font_size=self.font_size.value(),
            width=self.text_width.value(),
            alignment=self.text_alignment.currentText(),
            letter_spacing=self.letter_spacing.value(),
            line_height=self.line_height.value(),
            opacity=self.text_opacity.value() / 100,
            effect=self.text_effect.currentText(),
            bold=self.bold_check.isChecked(),
            italic=self.italic_check.isChecked(),
            underline=self.underline_check.isChecked(),
        )
        item.setPlainText(item.data["text"])
        item.setTextWidth(item.data["width"])
        item.setOpacity(item.data["opacity"])
        item.apply_font()
        self.scene.content_changed.emit()

    def _choose_text_color(self) -> None:
        item = self.scene.selected_editable()
        if not isinstance(item, TextItem):
            return
        color = QColorDialog.getColor(QColor(str(item.data.get("color", "#0f172a"))), self, "Pilih warna teks")
        if color.isValid():
            item.data["color"] = color.name()
            item.apply_font()
            self.scene.content_changed.emit()

    def _choose_text_background(self) -> None:
        item = self.scene.selected_editable()
        if not isinstance(item, TextItem):
            return
        initial = QColor(str(item.data.get("background", "#00ffffff")))
        color = QColorDialog.getColor(initial, self, "Pilih warna latar teks", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            item.data["background"] = color.name(QColor.NameFormat.HexArgb)
            item.update()
            self.scene.content_changed.emit()

    def _choose_text_effect_color(self) -> None:
        item = self.scene.selected_editable()
        if not isinstance(item, TextItem):
            return
        color = QColorDialog.getColor(QColor(str(item.data.get("effect_color", "#334155"))), self, "Pilih warna efek teks")
        if color.isValid():
            item.data["effect_color"] = color.name()
            item.apply_font()
            self.scene.content_changed.emit()

    def _crop_selected(self) -> None:
        item = self.scene.selected_editable()
        if isinstance(item, PhotoItem):
            self._begin_inline_crop(item)

    def _begin_inline_crop(self, item: PhotoItem) -> None:
        if not item.data.get("photo_path"):
            path, _ = QFileDialog.getOpenFileName(self, "Pilih foto", "", IMAGE_FILTER)
            if not path:
                return
            self._add_media_paths([path])
            item.data["photo_path"] = str(Path(path).resolve())
            item._loaded_path = ""
        if self._active_crop_item is not None and self._active_crop_item is not item:
            self._finish_inline_crop(True)
        if not self.scene.begin_crop(item):
            return
        self._active_crop_item = item
        item.crop_state_changed.connect(self._sync_inline_crop_controls)
        self._sync_inline_crop_controls(
            float(item.data.get("crop_x", 0.5)),
            float(item.data.get("crop_y", 0.5)),
            float(item.data.get("zoom", 1.0)),
        )
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.crop_toolbar.setVisible(True)
        self.resize_collage_button.setEnabled(False)
        self.status_text(
            "Mode crop aktif: seret foto di kanvas, gunakan roda mouse atau slider untuk zoom, lalu klik Selesai Crop."
        )

    def _sync_inline_crop_controls(self, _crop_x: float, _crop_y: float, zoom: float) -> None:
        blocker = QSignalBlocker(self.inline_crop_zoom)
        self.inline_crop_zoom.setValue(round(zoom * 100))
        del blocker

    def _set_inline_crop_zoom(self, value: int) -> None:
        if self._active_crop_item is not None:
            self._active_crop_item.set_crop_zoom(value / 100.0)

    def _rotate_inline_crop(self, degrees: int) -> None:
        if self._active_crop_item is not None:
            self._active_crop_item.rotate_crop_image(degrees)

    def _reset_inline_crop(self) -> None:
        if self._active_crop_item is not None:
            self._active_crop_item.reset_crop()

    def _apply_inline_crop(self) -> None:
        self._finish_inline_crop(True)

    def _cancel_inline_crop(self) -> None:
        self._finish_inline_crop(False)

    def _finish_inline_crop(self, commit: bool) -> None:
        item = self._active_crop_item
        if item is None:
            return
        try:
            item.crop_state_changed.disconnect(self._sync_inline_crop_controls)
        except (RuntimeError, TypeError):
            pass
        self.scene.finish_crop(commit)
        self._active_crop_item = None
        self._reset_editor_mode_ui()
        self.status_text("Crop foto diterapkan." if commit else "Perubahan crop dibatalkan.")

    def _toggle_collage_resize(self) -> None:
        if self._active_crop_item is not None:
            self._finish_inline_crop(True)
        if self.scene.collage_overlay is not None:
            self.scene.finish_collage_resize()
            self.resize_collage_button.setText("Ubah Ukuran Kolase")
            self.status_text("Ukuran dan posisi kolase diterapkan.")
            return
        overlay = self.scene.begin_collage_resize()
        if overlay is None:
            QMessageBox.information(
                self,
                "Kolase belum tersedia",
                "Tambahkan atau buat kolase foto terlebih dahulu.",
            )
            return
        self.resize_collage_button.setText("Selesai Ubah Ukuran")
        self.status_text(
            "Mode ukuran kolase aktif: seret bagian tengah untuk memindahkan atau pegangan ungu untuk mengubah ukuran. Tahan Shift agar rasio tetap."
        )

    def _reset_editor_mode_ui(self) -> None:
        self._active_crop_item = None
        if hasattr(self, "crop_toolbar"):
            self.crop_toolbar.setVisible(False)
        if hasattr(self, "resize_collage_button"):
            self.resize_collage_button.setEnabled(True)
            if self.scene.collage_overlay is None:
                self.resize_collage_button.setText("Ubah Ukuran Kolase")
        if hasattr(self, "view"):
            self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def _close_canvas_modes(self, *, commit_crop: bool, commit_collage: bool) -> None:
        if self._active_crop_item is not None:
            self._finish_inline_crop(commit_crop)
        if self.scene.collage_overlay is not None:
            self.scene.finish_collage_resize(commit_collage)
        self._reset_editor_mode_ui()

    def page_setup(self) -> None:
        dialog = PageSetupDialog(self.project, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._save_current_scene()
        old_width, old_height = self.project.page_size_mm
        self.project.paper_size = dialog.paper.currentText()
        self.project.orientation = dialog.orientation.currentText()
        self.project.custom_width_mm = dialog.custom_width.value()
        self.project.custom_height_mm = dialog.custom_height.value()
        self.project.margins.top = dialog.top.value()
        self.project.margins.right = dialog.right.value()
        self.project.margins.bottom = dialog.bottom.value()
        self.project.margins.left = dialog.left.value()
        new_width, new_height = self.project.page_size_mm
        scale_x = new_width / max(1.0, old_width)
        scale_y = new_height / max(1.0, old_height)
        for page in self.project.pages:
            for element in page.elements:
                element["x"] = float(element.get("x", 0.0)) * scale_x
                element["y"] = float(element.get("y", 0.0)) * scale_y
                element["width"] = float(element.get("width", 1.0)) * scale_x
                if element.get("kind") == "photo":
                    element["height"] = float(element.get("height", 1.0)) * scale_y
        self._load_current_scene()
        self._push_history()
        self._schedule_autosave()
        QTimer.singleShot(0, self._fit_page)

    def _update_project_title(self) -> None:
        self.project.title = self.project_title.text().strip() or "Dokumentasi Kegiatan"
        self._push_history()
        self._schedule_autosave()

    def new_project(self) -> None:
        if QMessageBox.question(self, "Proyek baru", "Buat proyek baru? Perubahan yang belum disimpan akan diganti.") != QMessageBox.StandardButton.Yes:
            return
        self.project = DocumentProject()
        self.current_path = None
        self.current_page_index = 0
        self.history.clear()
        self.history_index = -1
        self._refresh_all(push_history=True)

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Buka proyek Dokumentasi Foto", "", "Proyek DokuFoto (*.dokufoto.json *.zip);;JSON (*.json);;ZIP (*.zip)")
        if not path:
            return
        try:
            if Path(path).suffix.lower() == ".zip":
                self.project = self.exporter.import_archive(path, documentation_dir() / "imports")
                self.current_path = None
            else:
                self.project = DocumentProject.load(path)
                self.current_path = Path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Proyek tidak dapat dibuka", str(exc))
            return
        self.current_page_index = 0
        self.history.clear()
        self.history_index = -1
        self._refresh_all(push_history=True)
        self.status_text(f"Proyek {self.project.title} berhasil dibuka.")

    def save_project(self) -> None:
        self._save_current_scene()
        path = self.current_path
        if not path:
            filename = self._safe_name(self.project.title) + ".dokufoto.json"
            selected, _ = QFileDialog.getSaveFileName(self, "Simpan proyek", str(Path.home() / "Documents" / filename), "Proyek DokuFoto (*.dokufoto.json)")
            if not selected:
                return
            path = Path(selected)
            if not str(path).lower().endswith(".dokufoto.json"):
                path = Path(str(path) + ".dokufoto.json")
            self.current_path = path
        try:
            self.project.save(path)
        except Exception as exc:
            QMessageBox.critical(self, "Simpan gagal", str(exc))
            return
        self.status_text(f"Proyek tersimpan: {path.name}")

    def export_archive(self) -> None:
        self._save_current_scene()
        filename = self._safe_name(self.project.title) + ".zip"
        path, _ = QFileDialog.getSaveFileName(self, "Ekspor arsip proyek", str(Path.home() / "Documents" / filename), "Arsip ZIP (*.zip)")
        if not path:
            return
        try:
            target = self.exporter.export_archive(self.project, path)
        except Exception as exc:
            QMessageBox.critical(self, "Ekspor ZIP gagal", str(exc))
            return
        self.status_text(f"Arsip lengkap tersimpan: {target.name}")

    def preview(self) -> None:
        self._save_current_scene()
        PreviewDialog(self.project, self.exporter, self).exec()

    def export_docx(self) -> None:
        self._save_current_scene()
        filename = self._safe_name(self.project.title) + ".docx"
        path, _ = QFileDialog.getSaveFileName(self, "Ekspor DOCX", str(Path.home() / "Documents" / filename), "Word Document (*.docx)")
        if not path:
            return
        self._run_export(lambda: self.exporter.export_docx(self.project, path), "DOCX")

    def export_pdf(self) -> None:
        self._save_current_scene()
        filename = self._safe_name(self.project.title) + ".pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Ekspor PDF", str(Path.home() / "Documents" / filename), "PDF (*.pdf)")
        if not path:
            return
        self._run_export(lambda: self.exporter.export_pdf(self.project, path), "PDF")

    def _run_export(self, operation, label: str) -> None:
        self.setEnabled(False)
        self.status_text(f"Membuat {label} WYSIWYG 300 DPI…")
        try:
            target = operation()
        except Exception as exc:
            QMessageBox.critical(self, f"Ekspor {label} gagal", str(exc))
            self.status_text(f"Ekspor {label} gagal.", error=True)
        else:
            QMessageBox.information(self, "Ekspor selesai", f"File tersimpan di:\n{target}")
            self.status_text(f"Ekspor {label} selesai: {Path(target).name}")
        finally:
            self.setEnabled(True)

    def print_document(self) -> None:
        self._save_current_scene()
        try:
            printed = self.exporter.print_project(self.project, self)
        except Exception as exc:
            QMessageBox.critical(self, "Pencetakan gagal", str(exc))
            return
        if printed:
            self.status_text("Dokumentasi Foto dikirim ke printer yang dipilih.")

    def _fit_page(self) -> None:
        self.view.fit_page()

    def status_text(self, text: str, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setProperty("error", error)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    @staticmethod
    def _safe_name(name: str) -> str:
        return "".join(character if character.isalnum() or character in "-_" else "_" for character in name).strip("_") or "Dokumentasi_Foto"
