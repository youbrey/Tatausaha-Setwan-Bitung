from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path
from typing import Callable

import fitz
from PySide6.QtCore import QSignalBlocker, QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sekretariat_app.sips.preview import DocxPreviewConverter


DocumentGenerator = Callable[[str, str], list[Path]]
PreviewDocuments = list[tuple[str, str]]


class _LivePreviewWorker(QThread):
    """Membuat dokumen dan PDF tanpa memblokir event loop Qt."""

    succeeded = Signal(int, str, object, str, str)
    failed = Signal(int, str, str)

    def __init__(
        self,
        request_id: int,
        temporary_directory: str,
        generator: DocumentGenerator,
        selected_document: str,
        preferred_document: str,
    ) -> None:
        super().__init__()
        self.request_id = request_id
        self.temporary_directory = temporary_directory
        self.generator = generator
        self.selected_document = selected_document
        self.preferred_document = preferred_document

    def run(self) -> None:
        try:
            documents = [
                Path(path)
                for path in self.generator(self.temporary_directory, self.selected_document)
            ]
            if not documents:
                raise ValueError("Tidak ada dokumen yang dapat ditampilkan.")
            if self.isInterruptionRequested():
                shutil.rmtree(self.temporary_directory, ignore_errors=True)
                return
            source = next(
                (path for path in documents if path.name == self.preferred_document),
                documents[0],
            )
            pdf_path = DocxPreviewConverter().convert(source, self.temporary_directory)
            if self.isInterruptionRequested():
                shutil.rmtree(self.temporary_directory, ignore_errors=True)
                return
            self.succeeded.emit(
                self.request_id,
                self.temporary_directory,
                [str(path) for path in documents],
                str(source),
                str(pdf_path),
            )
        except Exception as exc:
            if self.isInterruptionRequested():
                shutil.rmtree(self.temporary_directory, ignore_errors=True)
            else:
                self.failed.emit(self.request_id, self.temporary_directory, str(exc))


class LiveDocumentPreview(QFrame):
    """Panel preview DOCX/PDF yang diperbarui otomatis dengan debounce."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LivePreviewPanel")
        self.setMinimumWidth(390)
        self._active = False
        self._request_id = 0
        self._last_generator: DocumentGenerator | None = None
        self._last_state_key: str | None = None
        self._last_documents: PreviewDocuments = []
        self._pending_generator: DocumentGenerator | None = None
        self._pending_request_key: tuple[str, str] | None = None
        self._working_request_key: tuple[str, str] | None = None
        self._rendered_request_key: tuple[str, str] | None = None
        self._worker: _LivePreviewWorker | None = None
        self._temporary_directory: str | None = None
        self._documents: list[Path] = []
        self._source_path: Path | None = None
        self._pdf_path: Path | None = None
        self._pdf_document: fitz.Document | None = None
        self._page_index = 0
        self._zoom = 1.0

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(900)
        self._timer.timeout.connect(self._start_update)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(90)
        self._resize_timer.timeout.connect(self._render_page)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        heading = QHBoxLayout()
        title = QLabel("Live Preview")
        title.setObjectName("PanelTitle")
        badge = QLabel("OTOMATIS")
        badge.setObjectName("LiveBadge")
        heading.addWidget(title)
        heading.addStretch()
        heading.addWidget(badge)
        layout.addLayout(heading)

        self.status = QLabel("Lengkapi formulir untuk menampilkan dokumen.")
        self.status.setObjectName("PreviewStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.document_selector = QComboBox()
        self.document_selector.setToolTip("Pilih dokumen yang ditampilkan")
        self.document_selector.setEnabled(False)
        self.document_selector.currentTextChanged.connect(self._change_document)
        layout.addWidget(self.document_selector)

        self.canvas = QLabel("Preview dokumen akan muncul di sini")
        self.canvas.setObjectName("PreviewCanvas")
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setWordWrap(True)
        self.canvas.setMinimumSize(300, 420)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("PreviewScroll")
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.canvas)
        layout.addWidget(self.scroll, 1)

        navigation = QHBoxLayout()
        self.previous = QPushButton("‹")
        self.previous.setToolTip("Halaman sebelumnya")
        self.next = QPushButton("›")
        self.next.setToolTip("Halaman berikutnya")
        self.page_counter = QLabel("—")
        self.page_counter.setObjectName("PreviewCounter")
        self.zoom_out = QPushButton("−")
        self.zoom_out.setToolTip("Perkecil")
        self.zoom_in = QPushButton("+")
        self.zoom_in.setToolTip("Perbesar")
        self.zoom_value = QLabel("100%")
        self.zoom_value.setObjectName("PreviewCounter")
        self.previous.clicked.connect(lambda: self._move_page(-1))
        self.next.clicked.connect(lambda: self._move_page(1))
        self.zoom_out.clicked.connect(lambda: self._change_zoom(-0.15))
        self.zoom_in.clicked.connect(lambda: self._change_zoom(0.15))
        for button in (self.previous, self.next, self.zoom_out, self.zoom_in):
            button.setFixedWidth(36)
        navigation.addWidget(self.previous)
        navigation.addWidget(self.next)
        navigation.addWidget(self.page_counter)
        navigation.addStretch()
        navigation.addWidget(self.zoom_out)
        navigation.addWidget(self.zoom_value)
        navigation.addWidget(self.zoom_in)
        layout.addLayout(navigation)

        self.open_document = QPushButton("Buka DOCX di Word")
        self.open_document.setEnabled(False)
        self.open_document.clicked.connect(self._open_source)
        layout.addWidget(self.open_document)
        self._update_controls()

    def schedule(
        self,
        generator: DocumentGenerator,
        state_key: str,
        documents: PreviewDocuments,
    ) -> None:
        """Render hanya dokumen terpilih dan abaikan state yang sudah tersedia."""

        self._last_generator = generator
        self._last_state_key = state_key
        self._last_documents = list(documents)
        self._set_document_options(self._last_documents)
        self._queue_selected_document()

    def _set_document_options(self, documents: PreviewDocuments) -> None:
        current_key = str(self.document_selector.currentData() or "")
        existing = [
            (
                str(self.document_selector.itemData(index) or ""),
                self.document_selector.itemText(index),
            )
            for index in range(self.document_selector.count())
        ]
        if existing == documents:
            return
        blocker = QSignalBlocker(self.document_selector)
        self.document_selector.clear()
        for key, name in documents:
            self.document_selector.addItem(name, key)
        selected_index = next(
            (
                index
                for index in range(self.document_selector.count())
                if self.document_selector.itemData(index) == current_key
            ),
            0,
        )
        if self.document_selector.count():
            self.document_selector.setCurrentIndex(selected_index)
        del blocker
        self.document_selector.setEnabled(bool(documents))

    def _queue_selected_document(self, delay_ms: int | None = None) -> None:
        if self._last_generator is None or self._last_state_key is None:
            return
        selected_key = str(self.document_selector.currentData() or "")
        if not selected_key:
            return
        request_key = (self._last_state_key, selected_key)
        if request_key == self._rendered_request_key and self._pdf_path and self._pdf_path.exists():
            if self._active and self._pdf_document is None:
                self._open_cached_pdf()
            return
        if request_key == self._pending_request_key:
            if self._active:
                self._timer.start(self._timer.interval() if delay_ms is None else delay_ms)
            return
        if request_key == self._working_request_key:
            if self._worker is not None and self._worker.isInterruptionRequested():
                self._pending_generator = self._last_generator
                self._pending_request_key = request_key
                if self._active:
                    self._timer.start(self._timer.interval() if delay_ms is None else delay_ms)
            return

        self._pending_generator = self._last_generator
        self._pending_request_key = request_key
        self._request_id += 1
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
        if self._active:
            self.status.setText("Menunggu perubahan selesai…")
            self._timer.start(self._timer.interval() if delay_ms is None else delay_ms)

    def show_waiting(self, message: str) -> None:
        """Kosongkan preview ketika formulir belum valid."""

        self._last_generator = None
        self._last_state_key = None
        self._last_documents = []
        self._pending_generator = None
        self._pending_request_key = None
        self._request_id += 1
        self._timer.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
        self._clear_preview()
        self.status.setText(message)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._active = True
        selected_key = str(self.document_selector.currentData() or "")
        current_request_key = (
            (self._last_state_key, selected_key)
            if self._last_state_key is not None and selected_key
            else None
        )
        if (
            current_request_key == self._rendered_request_key
            and self._pdf_path
            and self._pdf_path.exists()
        ):
            self._open_cached_pdf()
        elif self._last_generator is not None:
            self._queue_selected_document(120)

    def hideEvent(self, event) -> None:
        self._active = False
        self._request_id += 1
        self._timer.stop()
        self._resize_timer.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
        self._close_pdf()
        self.canvas.clear()
        super().hideEvent(event)

    def _start_update(self) -> None:
        if (
            not self._active
            or self._pending_generator is None
            or self._pending_request_key is None
        ):
            return
        if self._worker is not None and self._worker.isRunning():
            self.status.setText("Perubahan baru menunggu proses preview sebelumnya…")
            return

        generator = self._pending_generator
        request_key = self._pending_request_key
        self._pending_generator = None
        self._pending_request_key = None
        self._working_request_key = request_key
        request_id = self._request_id
        temporary_directory = tempfile.mkdtemp(prefix="sips-live-preview-")
        self.status.setText("Membuat dan merender dokumen…")
        self.document_selector.setEnabled(False)
        preferred_name = next(
            (name for key, name in self._last_documents if key == request_key[1]),
            self.document_selector.currentText(),
        )

        self._worker = _LivePreviewWorker(
            request_id,
            temporary_directory,
            generator,
            request_key[1],
            preferred_name,
        )
        self._worker.succeeded.connect(self._preview_ready)
        self._worker.failed.connect(self._preview_failed)
        self._worker.finished.connect(self._worker_finished)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start(QThread.Priority.LowPriority)

    def _preview_ready(
        self,
        request_id: int,
        temporary_directory: str,
        documents: object,
        source_path: str,
        pdf_path: str,
    ) -> None:
        if request_id != self._request_id or not self._active:
            shutil.rmtree(temporary_directory, ignore_errors=True)
            return

        previous_document_key = (
            self._rendered_request_key[1] if self._rendered_request_key else None
        )
        completed_request_key = self._working_request_key
        self._replace_temporary_directory(temporary_directory)
        self._documents = [Path(value) for value in documents]
        self._source_path = Path(source_path)
        self._pdf_path = Path(pdf_path)
        self._close_pdf()
        self._pdf_document = fitz.open(self._pdf_path)
        if completed_request_key and completed_request_key[1] != previous_document_key:
            self._page_index = 0
        self._page_index = min(self._page_index, max(0, len(self._pdf_document) - 1))
        self._rendered_request_key = completed_request_key

        self.document_selector.setEnabled(bool(self._last_documents))
        self.open_document.setEnabled(True)
        self.status.setText("Preview diperbarui otomatis.")
        self._render_page()

    def _preview_failed(self, request_id: int, temporary_directory: str, message: str) -> None:
        shutil.rmtree(temporary_directory, ignore_errors=True)
        if request_id != self._request_id or not self._active:
            return
        self.document_selector.setEnabled(bool(self._last_documents))
        self.status.setText(f"Live preview belum tersedia: {message}")

    def _worker_finished(self) -> None:
        self._worker = None
        self._working_request_key = None
        if self._active and self._pending_generator is not None:
            self._timer.start(120)

    def _change_document(self, _name: str) -> None:
        if self.document_selector.currentIndex() < 0 or self._last_generator is None:
            return
        self._queue_selected_document(80)

    def _move_page(self, delta: int) -> None:
        if self._pdf_document is None:
            return
        self._page_index = max(0, min(len(self._pdf_document) - 1, self._page_index + delta))
        self._render_page()

    def _change_zoom(self, delta: float) -> None:
        self._zoom = max(0.55, min(2.2, self._zoom + delta))
        self._render_page()

    def _open_cached_pdf(self) -> None:
        if not self._pdf_path or not self._pdf_path.exists():
            return
        self._close_pdf()
        self._pdf_document = fitz.open(self._pdf_path)
        self._page_index = min(self._page_index, max(0, len(self._pdf_document) - 1))
        self.open_document.setEnabled(bool(self._source_path and self._source_path.exists()))
        self.document_selector.setEnabled(bool(self._last_documents))
        self.status.setText("Preview siap.")
        self._render_page()

    def _render_page(self) -> None:
        if self._pdf_document is None or len(self._pdf_document) == 0:
            self._update_controls()
            return
        page = self._pdf_document[self._page_index]
        viewport_width = max(300, self.scroll.viewport().width() - 28)
        fit_width = viewport_width / max(1.0, float(page.rect.width))
        scale = max(0.45, min(2.8, fit_width * self._zoom))
        estimated_pixels = float(page.rect.width * page.rect.height) * scale * scale
        max_pixels = 3_500_000
        if estimated_pixels > max_pixels:
            scale *= math.sqrt(max_pixels / estimated_pixels)
        rendered = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = QImage(
            rendered.samples,
            rendered.width,
            rendered.height,
            rendered.stride,
            QImage.Format.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(image)
        del image, rendered
        self.canvas.setText("")
        self.canvas.setPixmap(pixmap)
        self.canvas.setFixedSize(pixmap.size())
        self._update_controls()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._active and self._pdf_document is not None:
            self._resize_timer.start()

    def _update_controls(self) -> None:
        count = len(self._pdf_document) if self._pdf_document is not None else 0
        self.previous.setEnabled(count > 0 and self._page_index > 0)
        self.next.setEnabled(count > 0 and self._page_index < count - 1)
        self.zoom_out.setEnabled(count > 0 and self._zoom > 0.55)
        self.zoom_in.setEnabled(count > 0 and self._zoom < 2.2)
        self.page_counter.setText(
            f"{self._page_index + 1} / {count}" if count else "—"
        )
        self.zoom_value.setText(f"{round(self._zoom * 100):.0f}%")

    def _open_source(self) -> None:
        if self._source_path and self._source_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._source_path.resolve())))

    def _clear_preview(self) -> None:
        self._close_pdf()
        self._cleanup_temporary_directory()
        self._documents = []
        self._source_path = None
        self._pdf_path = None
        self._rendered_request_key = None
        blocker = QSignalBlocker(self.document_selector)
        self.document_selector.clear()
        del blocker
        self.document_selector.setEnabled(False)
        self.open_document.setEnabled(False)
        self.canvas.clear()
        self.canvas.setText("Preview dokumen akan muncul di sini")
        self.canvas.setMinimumSize(300, 420)
        self.canvas.setMaximumSize(16777215, 16777215)
        self._page_index = 0
        self._zoom = 1.0
        self._update_controls()

    def _close_pdf(self) -> None:
        if self._pdf_document is not None:
            self._pdf_document.close()
            self._pdf_document = None

    def _replace_temporary_directory(self, value: str) -> None:
        self._close_pdf()
        self._cleanup_temporary_directory()
        self._temporary_directory = value

    def _cleanup_temporary_directory(self) -> None:
        if self._temporary_directory:
            shutil.rmtree(self._temporary_directory, ignore_errors=True)
            self._temporary_directory = None

    def shutdown(self) -> None:
        self._timer.stop()
        self._resize_timer.stop()
        self._active = False
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            if not self._worker.wait(10_000):
                self._worker.terminate()
                self._worker.wait(2_000)
        self._close_pdf()
        self._cleanup_temporary_directory()

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)
