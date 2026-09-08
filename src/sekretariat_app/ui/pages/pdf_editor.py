from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget,
)

from sekretariat_app.ui.pdf_canvas import PDFCanvas
from sekretariat_app.ui.pdf_jobs import PDFJobs


class PDFEditorPage(QWidget):
    """Offline PDF workspace. All PDF processing is isolated from the UI process."""

    def __init__(self):
        super().__init__()
        self.workspace = tempfile.TemporaryDirectory(prefix="setwan-pdf-")
        self.revisions: list[Path] = []
        self.revision_counts: dict[str, int] = {}
        self.revision_index = -1
        self.original: Path | None = None
        self.dirty = False
        self.count = 0
        self.page = 0
        self.block = None
        self.image_path = ""
        self.request = None
        self.callback = None
        self._needs_render = False
        self.jobs = PDFJobs(self)
        self.jobs.finished.connect(self._done)
        self.jobs.progress.connect(self._progress)
        self.jobs.busy_changed.connect(self._busy_changed)
        self._build_ui()
        self._busy_changed(False)

    @property
    def source(self) -> str:
        return str(self.revisions[self.revision_index]) if self.revisions else ""

    def _path(self, suffix: str = ".pdf") -> str:
        return str(Path(self.workspace.name) / f"{uuid4().hex}{suffix}")

    @staticmethod
    def _button(text: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False: callback())
        return button

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        title = QLabel("Edit PDF")
        title.setStyleSheet("font-size:26px;font-weight:700;color:#102f4a;")
        layout.addWidget(title)
        self.filename = QLabel("Gabungkan, atur halaman, edit teks, dan konversi dokumen secara offline.")
        self.filename.setWordWrap(True)
        layout.addWidget(self.filename)

        self.controls = QWidget()
        toolbar = QHBoxLayout(self.controls)
        toolbar.setContentsMargins(0, 6, 0, 6)
        toolbar.addWidget(self._button("Buka PDF", self.open_pdf))
        self.save_button = self._button("Simpan Salinan…", self.save_pdf)
        toolbar.addWidget(self.save_button)
        self.undo_button = self._button("Urungkan", lambda: self._history(-1))
        self.redo_button = self._button("Ulangi", lambda: self._history(1))
        toolbar.addWidget(self.undo_button)
        toolbar.addWidget(self.redo_button)
        toolbar.addWidget(self._button("Muat ulang preview", self._render))
        toolbar.addStretch()
        layout.addWidget(self.controls)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 8, 0)
        self.navigation = QWidget()
        nav = QHBoxLayout(self.navigation)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.addWidget(self._button("‹", lambda: self._goto(self.page - 1)))
        self.page_number = QSpinBox()
        self.page_number.setRange(1, 1)
        self.page_number.setPrefix("Halaman ")
        self.page_number.valueChanged.connect(lambda value: self._goto(value - 1))
        nav.addWidget(self.page_number)
        self.total = QLabel("/ 0")
        nav.addWidget(self.total)
        nav.addWidget(self._button("›", lambda: self._goto(self.page + 1)))
        nav.addStretch()
        nav.addWidget(self._button("Pas lebar", self.fit_width))
        self.zoom = QComboBox()
        self.zoom.addItems(["50%", "75%", "100%", "125%", "150%", "200%"])
        self.zoom.setCurrentText("100%")
        self.zoom.currentTextChanged.connect(lambda text: self.canvas.set_zoom(int(text.rstrip("%")) / 100))
        nav.addWidget(self.zoom)
        center_layout.addWidget(self.navigation)
        self.canvas = PDFCanvas()
        self.canvas.area_selected.connect(self._area_selected)
        self.canvas.block_selected.connect(self._block_selected)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.scroll.setStyleSheet("QScrollArea{background:#e7edf4;border:1px solid #d5dfeb;border-radius:8px;}")
        center_layout.addWidget(self.scroll, 1)
        splitter.addWidget(center)

        inspector = QScrollArea()
        inspector.setWidgetResizable(True)
        inspector.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inspector.setMinimumWidth(290)
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(285)
        self.tabs.addTab(self._pages_tab(), "Halaman")
        self.tabs.addTab(self._edit_tab(), "Edit")
        self.tabs.addTab(self._convert_tab(), "Konversi")
        self.tabs.addTab(self._protect_tab(), "Kunci")
        inspector.setWidget(self.tabs)
        splitter.addWidget(inspector)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([800, 330])
        layout.addWidget(splitter, 1)
        footer = QHBoxLayout()
        self.status = QLabel("Siap. File sumber tidak ditimpa.")
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        self.cancel = self._button("Batalkan proses", self.jobs.cancel)
        self.cancel.setVisible(False)
        footer.addWidget(self.cancel)
        layout.addLayout(footer)

    def _tab(self, hint: str):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        label = QLabel(hint)
        label.setWordWrap(True)
        layout.addWidget(label)
        return widget, layout

    def _pages_tab(self):
        widget, layout = self._tab("Nomor halaman dimulai dari 1. Contoh rentang: 1,3,5-8.")
        self.pages_input = QLineEdit()
        self.pages_input.setPlaceholderText("Kosong = halaman yang sedang dibuka")
        layout.addWidget(self.pages_input)
        layout.addWidget(self._button("Putar kanan 90°", lambda: self._edit("rotate", pages=self._pages(), angle=90)))
        layout.addWidget(self._button("Putar kiri 90°", lambda: self._edit("rotate", pages=self._pages(), angle=-90)))
        layout.addWidget(self._button("Hapus halaman…", self.delete_pages))
        layout.addWidget(self._button("Atur urutan / duplikasi…", self.organize))
        layout.addWidget(self._button("Sisipkan halaman kosong", lambda: self._edit("blank", page=self.page)))
        layout.addWidget(self._button("Gabungkan PDF…", self.merge))
        layout.addWidget(self._button("Pisahkan PDF…", self.split))
        layout.addStretch()
        return widget

    def _edit_tab(self):
        widget, layout = self._tab("Pilih mode. Untuk teks baru atau gambar, tarik kotak penempatan pada kertas.")
        self.mode = QComboBox()
        for label, value in (("Lihat halaman", "view"), ("Ganti teks yang ada", "replace_text"),
                             ("Tambah teks", "text"), ("Sisipkan gambar", "image")):
            self.mode.addItem(label, value)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        layout.addWidget(self.mode)
        self.text = QTextEdit()
        self.text.setPlaceholderText("Pilih blok teks pada halaman, lalu ubah isinya…")
        self.text.setMinimumHeight(120)
        layout.addWidget(self.text)
        self.family = QComboBox()
        self.family.addItems(["sans-serif", "serif", "monospace"])
        layout.addWidget(self.family)
        row = QHBoxLayout()
        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(4, 144)
        self.font_size.setValue(12)
        self.font_size.setSuffix(" pt")
        row.addWidget(self.font_size)
        self.bold = QCheckBox("Tebal")
        self.italic = QCheckBox("Miring")
        row.addWidget(self.bold)
        row.addWidget(self.italic)
        layout.addLayout(row)
        self.color = QLineEdit("#000000")
        self.color.setPlaceholderText("Warna #RRGGBB")
        layout.addWidget(self.color)
        layout.addWidget(self._button("Pilih gambar…", self.choose_image))
        self.image_label = QLabel("Belum ada gambar dipilih")
        self.image_label.setWordWrap(True)
        layout.addWidget(self.image_label)
        layout.addWidget(self._button("Terapkan pada area pilihan", self.apply_content))
        note = QLabel("Penggantian memakai font standar dan kotak blok yang dipilih. Font khusus, reflow paragraf kompleks, dan OCR scan belum didukung. Simpan salinan dan periksa hasilnya.")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        return widget

    def _convert_tab(self):
        widget, layout = self._tab("Konversi berjalan lokal. Word/Excel ke PDF memerlukan Microsoft Office atau LibreOffice terpasang.")
        self.conversion = QComboBox()
        for label, action in (("PDF → Word (teks editable)", "word_text"),
                              ("PDF → Word (gambar halaman)", "word_image"),
                              ("PDF → Excel (ekstrak tabel)", "pdf_to_excel"),
                              ("PDF → gambar PNG", "pdf_to_images"),
                              ("Word → PDF", "word_to_pdf"),
                              ("Excel → PDF", "excel_to_pdf"),
                              ("Gambar → PDF A4", "images_to_pdf")):
            self.conversion.addItem(label, action)
        layout.addWidget(self.conversion)
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 300)
        self.dpi.setValue(150)
        self.dpi.setSuffix(" DPI (PDF → PNG)")
        layout.addWidget(self.dpi)
        layout.addWidget(self._button("Konversi…", self.convert))
        note = QLabel("PDF → Word editable mengambil teks; tata letak, gambar, dan tabel kompleks tidak disalin identik. Mode gambar mempertahankan tampilan halaman, tetapi teksnya tidak editable. PDF → Excel hanya mengekstrak tabel pada PDF bertulisan, tanpa OCR.")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        return widget

    def _protect_tab(self):
        widget, layout = self._tab("Simpan salinan terenkripsi AES-256, atau salinan tanpa password menggunakan password pemilik yang sah.")
        layout.addWidget(self._button("Proteksi PDF…", self.protect))
        layout.addWidget(self._button("Simpan tanpa proteksi…", self.unprotect))
        note = QLabel("PDF terlindungi meminta password pemilik saat dibuka untuk diedit. Fitur ini tidak membobol password. Pembatasan cetak/salin bergantung pada aplikasi pembaca PDF.")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        return widget

    def _progress(self, message: str):
        self.status.setText(message)

    def _busy_changed(self, busy: bool):
        self.controls.setEnabled(not busy)
        self.tabs.setEnabled(not busy)
        self.navigation.setEnabled(bool(self.source) and not busy)
        self.canvas.setEnabled(not busy)
        self.cancel.setVisible(busy)
        self.save_button.setEnabled(bool(self.source))
        self.undo_button.setEnabled(self.revision_index > 0)
        self.redo_button.setEnabled(self.revision_index + 1 < len(self.revisions))

    def _start(self, request: dict, callback):
        if self.jobs.busy:
            return
        self.request, self.callback = request, callback
        self.status.setText("Memproses dokumen…")
        try:
            self.jobs.start(request)
        except (OSError, RuntimeError, ValueError) as error:
            self.request = self.callback = None
            self.status.setText(str(error))
            QMessageBox.warning(self, "Tidak dapat memulai proses PDF", str(error))

    @staticmethod
    def _remove(path: str):
        target = Path(path)
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)

    def _done(self, message: dict):
        request, callback = self.request, self.callback
        self.request = self.callback = None
        try:
            if message.get("ok"):
                self.status.setText("Selesai.")
                callback(message["result"])
            else:
                if request:
                    self._remove(request["output"])
                password_path = message.get("password_path")
                if password_path:
                    password, ok = QInputDialog.getText(self, "Password PDF", f"{Path(password_path).name}\n{message['error']}", QLineEdit.EchoMode.Password)
                    if ok:
                        if request["action"] == "merge":
                            request.setdefault("passwords", {})[password_path] = password
                        else:
                            request["password"] = password
                        self._start(request, callback)
                        return
                self.status.setText(message.get("error", "Pekerjaan dibatalkan."))
                if not message.get("cancelled") and not password_path:
                    QMessageBox.warning(self, "Edit PDF", self.status.text())
        except (OSError, ValueError) as error:
            self.status.setText(str(error))
            QMessageBox.warning(self, "Edit PDF", str(error))
        finally:
            self._busy_changed(self.jobs.busy)

    def _require_pdf(self) -> bool:
        if self.source:
            return True
        QMessageBox.information(self, "Edit PDF", "Buka PDF terlebih dahulu.")
        return False

    def _discard(self) -> bool:
        return not self.dirty or QMessageBox.question(
            self, "Perubahan belum disimpan", "Lanjutkan tanpa menyimpan perubahan PDF?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def open_pdf(self):
        if not self._discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Buka PDF", "", "PDF (*.pdf)")
        if not path:
            return
        self._start({"action": "open", "source": path, "output": self._path()},
                    lambda result: self._opened(result, path))

    def _opened(self, result: dict, path: str):
        for revision in self.revisions:
            revision.unlink(missing_ok=True)
        self.revisions = [Path(result["path"])]
        self.revision_counts = {result["path"]: result["count"]}
        self.revision_index = 0
        self.original = Path(path)
        self.dirty = False
        self.count, self.page = result["count"], 0
        self.filename.setText(self.original.name + " — salinan kerja")
        self._render()

    def _render(self):
        if self.jobs.busy or not self.source:
            return
        self._clear_canvas()
        self.page = min(max(0, self.page), self.count - 1)
        with QSignalBlocker(self.page_number):
            self.page_number.setRange(1, self.count)
            self.page_number.setValue(self.page + 1)
        self.total.setText(f"/ {self.count}")
        self._needs_render = True
        if not self.isVisible():
            self.canvas.pixmap = QPixmap()
            self.canvas.update()
            return
        self._start({"action": "render", "source": self.source, "page": self.page,
                     "width": 1200, "output": self._path(".png")}, self._rendered)

    def _rendered(self, result: dict):
        if self.isVisible():
            self.canvas.load(result["path"], result)
            self._needs_render = False
            self.status.setText(f"Halaman {self.page + 1} / {self.count} · {result['width'] * 25.4 / 72:.1f} × {result['height'] * 25.4 / 72:.1f} mm")
        Path(result["path"]).unlink(missing_ok=True)

    def _goto(self, index: int):
        if self.jobs.busy or not self.source or index == self.page or not 0 <= index < self.count:
            return
        self.page = index
        self._render()

    def fit_width(self):
        width = max(200, self.scroll.viewport().width() - 44)
        self.canvas.set_zoom(min(2, width / self.canvas.page_size[0]))

    def _pages(self):
        return self.pages_input.text().strip() or str(self.page + 1)

    def _edit(self, action: str, **values):
        if not self._require_pdf():
            return
        self._start({"action": action, "source": self.source, "output": self._path(), **values}, self._edited)

    def _edited(self, result: dict):
        for path in self.revisions[self.revision_index + 1:]:
            path.unlink(missing_ok=True)
        self.revisions = self.revisions[:self.revision_index + 1] + [Path(result["path"])]
        # Disk history also has a byte budget; no full PDF snapshots in RAM.
        while len(self.revisions) > 1 and (len(self.revisions) > 8 or sum(p.stat().st_size for p in self.revisions) > 300 * 1024 * 1024):
            self.revisions.pop(0).unlink(missing_ok=True)
        self.revision_index = len(self.revisions) - 1
        self.revision_counts[result["path"]] = result["count"]
        self.revision_counts = {str(path): self.revision_counts[str(path)] for path in self.revisions}
        self.count = result["count"]
        self.dirty = True
        self._render()

    def _history(self, delta: int):
        index = self.revision_index + delta
        if not 0 <= index < len(self.revisions):
            return
        self.revision_index = index
        self.count = self.revision_counts[self.source]
        self.dirty = True
        self._render()

    def _clear_canvas(self):
        self.block = None
        self.canvas.selection = None
        self.canvas.blocks = []
        self.canvas.pixmap = QPixmap()
        self.canvas.update()

    def delete_pages(self):
        if self._require_pdf() and QMessageBox.question(self, "Hapus halaman", f"Hapus halaman {self._pages()} dari salinan kerja?") == QMessageBox.StandardButton.Yes:
            self._edit("delete", pages=self._pages())

    def organize(self):
        if not self._require_pdf():
            return
        order, ok = QInputDialog.getText(self, "Atur halaman", "Urutan baru, misalnya 3,1-2,2 (halaman 2 diduplikasi).\nHalaman yang tidak dicantumkan akan dikeluarkan.", text=f"1-{self.count}")
        if ok and order.strip():
            self._edit("organize", pages=order)

    def merge(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Pilih PDF untuk digabungkan", "", "PDF (*.pdf)")
        if not paths:
            return
        order, ok = QInputDialog.getText(self, "Urutan penggabungan",
            "\n".join(f"{i + 1}. {Path(p).name}" for i, p in enumerate(paths)) + "\n\nUrutan nomor file (pisahkan koma). PDF aktif, jika ada, ditempatkan pertama.",
            text=",".join(str(i + 1) for i in range(len(paths))))
        if not ok:
            return
        try:
            indexes = [int(n.strip()) - 1 for n in order.split(",")]
            if sorted(indexes) != list(range(len(paths))):
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Urutan file", "Cantumkan setiap nomor file tepat satu kali.")
            return
        sources = ([self.source] if self.source else []) + [paths[i] for i in indexes]
        self._start({"action": "merge", "sources": sources, "output": self._path()}, self._merged)

    def _merged(self, result: dict):
        if not self.source:
            self.filename.setText("Gabungan PDF — salinan kerja")
        self._edited(result)

    def _export(self, request: dict, suffix: str, *, directory: bool = False, saved: bool = False):
        if directory:
            parent = QFileDialog.getExistingDirectory(self, "Pilih folder hasil")
            if not parent:
                return
            target = Path(parent) / f"hasil-pdf-{uuid4().hex[:8]}"
        else:
            name = (self.original.stem if self.original else "dokumen") + "-hasil" + suffix
            path, _ = QFileDialog.getSaveFileName(self, "Simpan hasil", name, f"Dokumen (*{suffix})",
                                                options=QFileDialog.Option.DontConfirmOverwrite)
            if not path:
                return
            target = Path(path)
            if target.suffix.lower() != suffix:
                target = target.with_suffix(suffix)
            if self.original and target.resolve() == self.original.resolve():
                QMessageBox.warning(self, "Simpan salinan", "Gunakan nama berbeda untuk menjaga dokumen sumber.")
                return
            if target.exists() and QMessageBox.question(self, "Timpa hasil sebelumnya?", str(target),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        temporary = target.parent / f".{uuid4().hex}{suffix if not directory else ''}"
        def published(result):
            os.replace(result["path"], target)
            if saved:
                self.dirty = False
            self.status.setText(f"Tersimpan: {target}")
            QMessageBox.information(self, "Hasil tersimpan", str(target) + ("\n\n" + result["note"] if result.get("note") else ""))
        self._start({**request, "output": str(temporary)}, published)

    def save_pdf(self):
        if self._require_pdf():
            self._export({"action": "copy", "source": self.source}, ".pdf", saved=True)

    def split(self):
        if not self._require_pdf():
            return
        groups, ok = QInputDialog.getText(self, "Pisahkan PDF", "Kosong: satu file per halaman.\nAtau kelompok halaman dipisahkan titik koma, misalnya 1-3;4-6;7.")
        if ok:
            self._export({"action": "split", "source": self.source, "groups": groups}, "", directory=True)

    def _mode_changed(self):
        self.canvas.mode = self.mode.currentData()
        self.canvas.selection = None
        self.block = None
        self.canvas.update()

    def _area_selected(self, values):
        self.status.setText("Area dipilih. Atur isi lalu klik Terapkan.")

    def _block_selected(self, block: dict):
        self.block = block
        self.text.setPlainText(block["text"])
        self.font_size.setValue(block["size"])
        self.color.setText(block["color"])
        self.bold.setChecked(block["bold"])
        self.italic.setChecked(block["italic"])
        name = block["font"].lower()
        self.family.setCurrentText("monospace" if "courier" in name else "serif" if "times" in name else "sans-serif")
        self.status.setText("Blok dipilih. Penggantian menghapus teks lama pada area tersebut.")

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pilih gambar", "", "Gambar (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff)")
        if path:
            self.image_path = path
            self.image_label.setText(Path(path).name)
            self.mode.setCurrentIndex(self.mode.findData("image"))

    def apply_content(self):
        if not self._require_pdf():
            return
        action = self.mode.currentData()
        if action == "view" or not self.canvas.selection:
            QMessageBox.information(self, "Pilih area", "Pilih mode edit dan blok teks, atau tarik kotak pada kertas terlebih dahulu.")
            return
        values = {"page": self.page, "rect": self.canvas.selection, "text": self.text.toPlainText(),
                  "size": self.font_size.value(), "family": self.family.currentText(),
                  "color": self.color.text().strip(), "bold": self.bold.isChecked(), "italic": self.italic.isChecked()}
        if action == "replace_text":
            if not self.block:
                return
            values.update(block_id=self.block["id"], original=self.block["text"])
        if action == "image":
            if not self.image_path:
                self.choose_image()
                return
            values["image"] = self.image_path
        self._edit(action, **values)

    def convert(self):
        action = self.conversion.currentData()
        if action in {"word_to_pdf", "excel_to_pdf"}:
            mask = "Word (*.docx *.doc)" if action == "word_to_pdf" else "Excel (*.xlsx *.xls)"
            path, _ = QFileDialog.getOpenFileName(self, "Pilih dokumen", "", mask)
            if path:
                self._export({"action": "office_to_pdf", "source": path}, ".pdf")
        elif action == "images_to_pdf":
            paths, _ = QFileDialog.getOpenFileNames(self, "Pilih gambar (urut nama file)", "", "Gambar (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff)")
            if paths:
                self._export({"action": action, "sources": sorted(paths)}, ".pdf")
        elif self._require_pdf():
            request = {"source": self.source}
            if action.startswith("word_"):
                request.update(action="pdf_to_word", mode="appearance" if action == "word_image" else "text")
                self._export(request, ".docx")
            elif action == "pdf_to_excel":
                self._export({**request, "action": action}, ".xlsx")
            else:
                request.update(action=action, pages=self.pages_input.text().strip(), dpi=self.dpi.value())
                self._export(request, "", directory=True)

    def protect(self):
        if not self._require_pdf():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Proteksi PDF")
        form = QFormLayout(dialog)
        user, owner = QLineEdit(), QLineEdit()
        user.setEchoMode(QLineEdit.EchoMode.Password)
        owner.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password buka", user)
        form.addRow("Password pemilik (berbeda)", owner)
        printing, copying = QCheckBox("Izinkan cetak"), QCheckBox("Izinkan salin teks")
        printing.setChecked(True)
        form.addRow(printing)
        form.addRow(copying)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._export({"action": "protect", "source": self.source, "user_password": user.text(),
                          "owner_password": owner.text(), "allow_print": printing.isChecked(),
                          "allow_copy": copying.isChecked()}, ".pdf", saved=True)

    def unprotect(self):
        if self._require_pdf():
            self._export({"action": "unprotect", "source": self.source}, ".pdf", saved=True)

    def can_close(self) -> bool:
        if self.jobs.busy:
            QMessageBox.information(self, "Proses PDF masih berjalan", "Batalkan atau tunggu proses PDF selesai sebelum keluar.")
            return False
        return self._discard()

    def shutdown(self):
        self.workspace.cleanup()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.canvas.pixmap = QPixmap()
        self.canvas.blocks = []
        self._needs_render = bool(self.source)

    def showEvent(self, event):
        super().showEvent(event)
        if self._needs_render and not self.jobs.busy:
            QTimer.singleShot(0, self._render)
