from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QRectF, Qt, Signal
from PySide6.QtGui import QImage, QPageSize, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrinterInfo
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sekretariat_app.inventory.models import (
    DIVISIONS,
    ISSUE_TYPES,
    RECEIPT_TYPES,
    InventoryItem,
    IssueLine,
)
from sekretariat_app.inventory.reports import (
    InventoryReportService,
    export_outgoing_xlsx,
    money,
    quantity,
)
from sekretariat_app.inventory.repository import DEFAULT_SETTINGS, InventoryRepository


def _date_edit(value: date | None = None) -> QDateEdit:
    widget = QDateEdit()
    widget.setCalendarPopup(True)
    widget.setDisplayFormat("dd/MM/yyyy")
    current = value or date.today()
    widget.setDate(QDate(current.year, current.month, current.day))
    return widget


def _python_date(widget: QDateEdit) -> date:
    value = widget.date()
    return date(value.year(), value.month(), value.day())


def _table(headers: list[str], *, stretch_column: int | None = None) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if stretch_column is not None:
        table.horizontalHeader().setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
    return table


def _set_row(table: QTableWidget, row: int, values: list[object], *, identity: int | None = None) -> None:
    table.insertRow(row)
    for column, value in enumerate(values):
        item = QTableWidgetItem(str(value))
        if column == 0 and identity is not None:
            item.setData(Qt.ItemDataRole.UserRole, identity)
        table.setItem(row, column, item)


def _selected_id(table: QTableWidget) -> int | None:
    row = table.currentRow()
    if row < 0 or not table.item(row, 0):
        return None
    value = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
    return int(value) if value is not None else None


def _editable_combo(items: list[InventoryItem]) -> QComboBox:
    combo = QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.setMaxVisibleItems(18)
    combo.setPlaceholderText("Ketik kode atau nama barang...")
    if combo.lineEdit():
        combo.lineEdit().setPlaceholderText("Ketik kode atau nama barang...")
    for item in items:
        combo.addItem(item.label, item.item_id)
    combo.setCurrentIndex(-1)
    completer = combo.completer()
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    return combo


class ItemDialog(QDialog):
    def __init__(self, item: InventoryItem | None = None, parent=None) -> None:
        super().__init__(parent)
        self.item = item
        self.setWindowTitle("Edit Referensi Barang" if item else "Tambah Referensi Barang")
        self.setMinimumWidth(520)
        layout = QFormLayout(self)
        self.code = QLineEdit(item.code if item else "")
        self.name = QLineEdit(item.name if item else "")
        self.unit = QLineEdit(item.unit if item else "")
        self.category = QLineEdit(item.category if item else "")
        self.specification = QLineEdit(item.specification if item else "")
        self.card_number = QLineEdit(item.card_number if item else "")
        self.price = QDoubleSpinBox()
        self.price.setRange(0, 999_999_999_999)
        self.price.setDecimals(0)
        self.price.setGroupSeparatorShown(True)
        self.price.setValue(item.standard_price if item else 0)
        self.active = QCheckBox("Barang aktif dan dapat dipilih pada transaksi")
        self.active.setChecked(item.active if item else True)
        layout.addRow("Kode barang", self.code)
        layout.addRow("Nama barang", self.name)
        layout.addRow("Satuan", self.unit)
        layout.addRow("Kategori", self.category)
        layout.addRow("Spesifikasi", self.specification)
        layout.addRow("Nomor kartu", self.card_number)
        layout.addRow("Harga standar (Rp)", self.price)
        layout.addRow("", self.active)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _accept(self) -> None:
        if not self.code.text().strip() or not self.name.text().strip() or not self.unit.text().strip():
            QMessageBox.warning(self, "Data belum lengkap", "Kode, nama barang, dan satuan wajib diisi.")
            return
        self.accept()

    def result_item(self) -> InventoryItem:
        return InventoryItem(
            self.item.item_id if self.item else None,
            self.code.text().strip(), self.name.text().strip(), self.unit.text().strip(),
            self.category.text().strip(), self.specification.text().strip(),
            self.card_number.text().strip(), self.price.value(), self.active.isChecked(),
        )


class InventoryDashboard(QWidget):
    def __init__(self, repository: InventoryRepository) -> None:
        super().__init__()
        self.repository = repository
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        self.cards: dict[str, QLabel] = {}
        cards = QGridLayout()
        for index, (key, label) in enumerate((
            ("items", "Barang aktif"), ("low_stock", "Stok 5 atau kurang"),
            ("issues", "Surat pengeluaran"), ("value", "Nilai persediaan"),
        )):
            frame = QFrame(); frame.setObjectName("StatCard")
            box = QVBoxLayout(frame)
            value = QLabel("0"); value.setObjectName("StatValue")
            caption = QLabel(label); caption.setObjectName("StatLabel")
            box.addWidget(value); box.addWidget(caption)
            cards.addWidget(frame, 0, index)
            self.cards[key] = value
        layout.addLayout(cards)
        title = QLabel("Ringkasan Saldo Barang"); title.setObjectName("SectionTitle")
        layout.addWidget(title)
        self.table = _table(["Kode", "Nama Barang", "Kategori", "Jumlah", "Harga Rata-rata", "Nilai"], stretch_column=1)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        stats = self.repository.dashboard_stats()
        self.cards["items"].setText(str(int(stats["items"])))
        self.cards["low_stock"].setText(str(int(stats["low_stock"])))
        self.cards["issues"].setText(str(int(stats["issues"])))
        self.cards["value"].setText(money(stats["value"], rupiah=True))
        self.table.setRowCount(0)
        for row_index, row in enumerate(self.repository.stock_summary()):
            _set_row(self.table, row_index, [
                row.code, row.name, row.category or "-", f"{quantity(row.quantity)} {row.unit}",
                money(row.average_price, rupiah=True), money(row.value, rupiah=True),
            ], identity=row.item_id)


class ItemsTab(QWidget):
    data_changed = Signal()

    def __init__(self, repository: InventoryRepository) -> None:
        super().__init__()
        self.repository = repository
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 12, 0, 0)
        actions = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Cari kode, nama, atau kategori...")
        self.search.textChanged.connect(self.refresh)
        add = QPushButton("Tambah Barang"); add.setObjectName("PrimaryButton"); add.clicked.connect(self._add)
        edit = QPushButton("Edit"); edit.clicked.connect(self._edit)
        delete = QPushButton("Hapus"); delete.setObjectName("DangerButton"); delete.clicked.connect(self._delete)
        actions.addWidget(self.search, 1); actions.addWidget(add); actions.addWidget(edit); actions.addWidget(delete)
        layout.addLayout(actions)
        self.table = _table(["Kode", "Nama Barang", "Satuan", "Kategori", "Spesifikasi", "No. Kartu", "Harga Standar", "Status"], stretch_column=1)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self, *_args) -> None:
        self.table.setRowCount(0)
        for index, item in enumerate(self.repository.items(search=self.search.text())):
            _set_row(self.table, index, [
                item.code, item.name, item.unit, item.category or "-", item.specification or "-",
                item.card_number or "-", money(item.standard_price, rupiah=True),
                "Aktif" if item.active else "Nonaktif",
            ], identity=item.item_id)

    def _add(self) -> None:
        self._open(None)

    def _edit(self, *_args) -> None:
        identity = _selected_id(self.table)
        if identity is None:
            QMessageBox.information(self, "Pilih barang", "Pilih satu barang yang akan diedit.")
            return
        self._open(self.repository.item(identity))

    def _open(self, item: InventoryItem | None) -> None:
        dialog = ItemDialog(item, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.save_item(dialog.result_item())
        except ValueError as exc:
            QMessageBox.warning(self, "Tidak dapat menyimpan", str(exc)); return
        self.refresh(); self.data_changed.emit()

    def _delete(self) -> None:
        identity = _selected_id(self.table)
        if identity is None:
            QMessageBox.information(self, "Pilih barang", "Pilih satu barang yang akan dihapus."); return
        if QMessageBox.question(self, "Hapus barang", "Hapus referensi barang terpilih?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.repository.delete_item(identity)
        except ValueError as exc:
            QMessageBox.warning(self, "Tidak dapat menghapus", str(exc)); return
        self.refresh(); self.data_changed.emit()


class ReceiptTab(QWidget):
    data_changed = Signal()

    def __init__(self, repository: InventoryRepository) -> None:
        super().__init__()
        self.repository = repository
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 12, 0, 0)
        form_card = QFrame(); form_card.setObjectName("Card")
        grid = QGridLayout(form_card); grid.setContentsMargins(18, 16, 18, 16); grid.setSpacing(10)
        self.item_combo = _editable_combo([])
        self.item_combo.currentIndexChanged.connect(self._item_changed)
        self.transaction_type = QComboBox(); self.transaction_type.addItems(RECEIPT_TYPES)
        self.book_date = _date_edit()
        self.document_number = QLineEdit(); self.document_number.setPlaceholderText("Contoh: 08/BAST/PPTK/SETWAN/2026")
        self.quantity = QDoubleSpinBox(); self.quantity.setRange(0.01, 999_999_999); self.quantity.setDecimals(2)
        self.unit_price = QDoubleSpinBox(); self.unit_price.setRange(0, 999_999_999_999); self.unit_price.setDecimals(0); self.unit_price.setGroupSeparatorShown(True)
        self.description = QLineEdit(); self.description.setPlaceholderText("Contoh: Pembelian di Maju Bersama")
        self.note = QLineEdit(); self.note.setPlaceholderText("Keterangan tambahan (opsional)")
        fields = [
            ("Barang", self.item_combo), ("Jenis transaksi", self.transaction_type),
            ("Tanggal buku", self.book_date), ("No. surat/bukti", self.document_number),
            ("Jumlah masuk", self.quantity), ("Harga satuan (Rp)", self.unit_price),
            ("Uraian", self.description), ("Keterangan", self.note),
        ]
        for index, (label, widget) in enumerate(fields):
            caption = QLabel(label); caption.setObjectName("FieldLabel")
            row, column = divmod(index, 2)
            cell = QVBoxLayout(); cell.addWidget(caption); cell.addWidget(widget)
            grid.addLayout(cell, row, column)
        save = QPushButton("Simpan Barang Masuk"); save.setObjectName("PrimaryButton"); save.clicked.connect(self._save)
        grid.addWidget(save, 4, 1, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(form_card)
        title = QLabel("Transaksi Masuk Terbaru"); title.setObjectName("SectionTitle"); layout.addWidget(title)
        self.table = _table(["Tanggal", "No. Bukti", "Kode", "Nama Barang", "Jenis", "Jumlah", "Harga", "Sisa", "Uraian"], stretch_column=3)
        layout.addWidget(self.table, 1)
        self.refresh()

    def _items(self) -> None:
        current = self.item_combo.currentData()
        self.item_combo.blockSignals(True); self.item_combo.clear()
        for item in self.repository.items(active_only=True):
            self.item_combo.addItem(item.label, item.item_id)
        index = self.item_combo.findData(current)
        self.item_combo.setCurrentIndex(index)
        if index < 0:
            self.item_combo.setEditText("")
        self.item_combo.blockSignals(False)

    def _item_changed(self) -> None:
        item_id = self.item_combo.currentData()
        item = self.repository.item(int(item_id)) if item_id is not None else None
        if item:
            self.unit_price.setValue(item.standard_price)

    def refresh(self) -> None:
        self._items()
        self.table.setRowCount(0)
        for index, row in enumerate(self.repository.recent_receipts()):
            _set_row(self.table, index, [
                date.fromisoformat(row["book_date"]).strftime("%d/%m/%Y"), row["document_number"] or "-",
                row["code"], row["name"], row["transaction_type"],
                f"{quantity(float(row['quantity']))} {row['unit']}", money(float(row["unit_price"]), rupiah=True),
                quantity(float(row["remaining_quantity"])), row["description"] or "-",
            ], identity=int(row["id"]))

    def _save(self) -> None:
        item_id = self.item_combo.currentData()
        if item_id is None:
            QMessageBox.warning(self, "Barang belum dipilih", "Pilih barang dari daftar referensi."); return
        try:
            self.repository.record_receipt(
                item_id=int(item_id), document_number=self.document_number.text(),
                book_date=_python_date(self.book_date), transaction_type=self.transaction_type.currentText(),
                quantity=self.quantity.value(), unit_price=self.unit_price.value(),
                description=self.description.text(), note=self.note.text(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Transaksi ditolak", str(exc)); return
        QMessageBox.information(self, "Tersimpan", "Transaksi persediaan masuk berhasil disimpan.")
        self.document_number.clear(); self.quantity.setValue(0.01); self.description.clear(); self.note.clear()
        self.refresh(); self.data_changed.emit()


class IssueTab(QWidget):
    data_changed = Signal()
    export_requested = Signal(int)
    print_requested = Signal(int)

    def __init__(self, repository: InventoryRepository, username: str) -> None:
        super().__init__()
        self.repository = repository
        self.username = username
        self.pending: list[IssueLine] = []
        root = QVBoxLayout(self); root.setContentsMargins(0, 12, 0, 0)
        splitter = QSplitter(Qt.Orientation.Vertical)
        editor = QFrame(); editor.setObjectName("Card")
        editor_layout = QVBoxLayout(editor); editor_layout.setContentsMargins(18, 16, 18, 16)
        header = QGridLayout(); header.setSpacing(10)
        self.document_number = QLineEdit(); self.document_number.setPlaceholderText("Contoh: 01/SP-PPB/SETWAN/2026")
        self.book_date = _date_edit()
        self.division = QComboBox(); self.division.addItems(DIVISIONS); self.division.setCurrentIndex(-1)
        self.division.currentTextChanged.connect(self._division_changed)
        self.transaction_type = QComboBox(); self.transaction_type.addItems(ISSUE_TYPES)
        settings = self.repository.settings()
        self.sender = QLineEdit(settings["issue_sender"])
        self.recipient = QLineEdit(settings["issue_recipient"])
        self.address = QLineEdit(settings["issue_address"])
        self.sender.setProperty("inventory_default", settings["issue_sender"])
        self.recipient.setProperty("inventory_default", settings["issue_recipient"])
        self.address.setProperty("inventory_default", settings["issue_address"])
        self.request_basis = QLineEdit(); self.request_basis.setPlaceholderText("Contoh: Berdasarkan permintaan Kepala Bagian...")
        self._automatic_basis = ""
        for index, (label, widget) in enumerate((
            ("Nomor Surat Perintah", self.document_number), ("Tanggal buku", self.book_date),
            ("Bagian tujuan/pemakai", self.division), ("Jenis transaksi", self.transaction_type),
            ("Dari", self.sender), ("Kepada", self.recipient),
            ("Alamat", self.address), ("Dasar permintaan", self.request_basis),
        )):
            caption = QLabel(label); caption.setObjectName("FieldLabel")
            box = QVBoxLayout(); box.addWidget(caption); box.addWidget(widget)
            row, column = divmod(index, 2); header.addLayout(box, row, column)
        editor_layout.addLayout(header)
        section_title = QLabel("Daftar Barang"); section_title.setObjectName("SectionTitle")
        editor_layout.addWidget(section_title)
        add_row = QHBoxLayout()
        self.item_combo = _editable_combo([]); self.item_combo.currentIndexChanged.connect(self._stock_changed)
        self.stock_label = QLabel("Saldo: -"); self.stock_label.setObjectName("MutedText")
        self.line_quantity = QDoubleSpinBox(); self.line_quantity.setRange(0.01, 999_999_999); self.line_quantity.setDecimals(2)
        self.line_note = QLineEdit(); self.line_note.setPlaceholderText("Ket. (opsional)")
        add = QPushButton("Tambahkan"); add.clicked.connect(self._add_line)
        add_row.addWidget(self.item_combo, 3); add_row.addWidget(self.stock_label, 1)
        add_row.addWidget(self.line_quantity); add_row.addWidget(self.line_note, 2); add_row.addWidget(add)
        editor_layout.addLayout(add_row)
        self.lines_table = _table(["Kode", "Nama Barang", "Jumlah", "Satuan", "Saldo", "Keterangan"], stretch_column=1)
        self.lines_table.setMaximumHeight(210); editor_layout.addWidget(self.lines_table)
        actions = QHBoxLayout()
        remove = QPushButton("Hapus Baris"); remove.setObjectName("DangerButton"); remove.clicked.connect(self._remove_line)
        clear = QPushButton("Kosongkan"); clear.clicked.connect(self._clear_lines)
        save = QPushButton("Simpan Surat Pengeluaran"); save.setObjectName("PrimaryButton"); save.clicked.connect(self._save)
        actions.addWidget(remove); actions.addWidget(clear); actions.addStretch(); actions.addWidget(save)
        editor_layout.addLayout(actions)
        splitter.addWidget(editor)
        history = QFrame(); history.setObjectName("Card")
        history_layout = QVBoxLayout(history); history_layout.setContentsMargins(18, 14, 18, 14)
        history_title = QLabel("Riwayat Surat Pengeluaran"); history_title.setObjectName("SectionTitle")
        history_layout.addWidget(history_title)
        self.history_table = _table(["Tanggal", "Nomor Surat", "Bagian", "Jumlah Jenis Barang", "Total Nilai"], stretch_column=2)
        history_layout.addWidget(self.history_table)
        history_actions = QHBoxLayout(); history_actions.addStretch()
        export = QPushButton("Ekspor PDF"); export.clicked.connect(self._export_selected)
        print_button = QPushButton("Cetak Langsung"); print_button.setObjectName("PrimaryButton"); print_button.clicked.connect(self._print_selected)
        history_actions.addWidget(export); history_actions.addWidget(print_button); history_layout.addLayout(history_actions)
        splitter.addWidget(history); splitter.setSizes([520, 280]); root.addWidget(splitter)
        self.refresh()

    def _division_changed(self, division: str) -> None:
        if self.request_basis.text().strip() not in {"", self._automatic_basis}:
            return
        if not division:
            self.request_basis.clear(); self._automatic_basis = ""; return
        office = self.repository.settings().get("office_full_name", "Sekretariat DPRD Kota Bitung")
        self._automatic_basis = f"Berdasarkan Permintaan Kepala {division} {office}"
        self.request_basis.setText(self._automatic_basis)

    def _reload_items(self) -> None:
        current = self.item_combo.currentData()
        self.item_combo.blockSignals(True); self.item_combo.clear()
        for item in self.repository.items(active_only=True): self.item_combo.addItem(item.label, item.item_id)
        self.item_combo.setCurrentIndex(self.item_combo.findData(current))
        if self.item_combo.currentIndex() < 0: self.item_combo.setEditText("")
        self.item_combo.blockSignals(False); self._stock_changed()

    def _stock_changed(self) -> None:
        value = self.item_combo.currentData()
        stock = self.repository.stock_for_item(int(value)) if value is not None else None
        self.stock_label.setText(f"Saldo: {quantity(stock.quantity)} {stock.unit}" if stock else "Saldo: -")

    def _add_line(self) -> None:
        value = self.item_combo.currentData()
        if value is None:
            QMessageBox.warning(self, "Barang belum dipilih", "Pilih barang dari daftar referensi."); return
        item_id = int(value)
        if any(line.item_id == item_id for line in self.pending):
            QMessageBox.warning(self, "Barang sudah ada", "Barang yang sama sudah berada dalam daftar surat."); return
        stock = self.repository.stock_for_item(item_id)
        if not stock or self.line_quantity.value() > stock.quantity + 1e-9:
            QMessageBox.warning(self, "Stok tidak mencukupi", f"Saldo tersedia hanya {quantity(stock.quantity if stock else 0)} {stock.unit if stock else ''}."); return
        self.pending.append(IssueLine(item_id, self.line_quantity.value(), self.line_note.text().strip()))
        self.line_quantity.setValue(0.01); self.line_note.clear(); self._refresh_lines()

    def _refresh_lines(self) -> None:
        self.lines_table.setRowCount(0)
        for index, line in enumerate(self.pending):
            item = self.repository.item(line.item_id); stock = self.repository.stock_for_item(line.item_id)
            if not item: continue
            _set_row(self.lines_table, index, [
                item.code, item.name, quantity(line.quantity), item.unit,
                quantity(stock.quantity if stock else 0), line.note or "-",
            ], identity=line.item_id)

    def _remove_line(self) -> None:
        row = self.lines_table.currentRow()
        if row >= 0 and row < len(self.pending): self.pending.pop(row); self._refresh_lines()

    def _clear_lines(self) -> None:
        self.pending.clear(); self._refresh_lines()

    def _save(self) -> None:
        try:
            header_id = self.repository.create_issue(
                document_number=self.document_number.text(), book_date=_python_date(self.book_date),
                division=self.division.currentText(), sender=self.sender.text(), recipient=self.recipient.text(),
                address=self.address.text(), request_basis=self.request_basis.text(),
                transaction_type=self.transaction_type.currentText(), lines=self.pending,
                created_by=self.username,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Transaksi ditolak", str(exc)); return
        self.pending.clear(); self.document_number.clear(); self.request_basis.clear()
        self._automatic_basis = ""
        self._division_changed(self.division.currentText())
        self._refresh_lines()
        self.refresh(); self.data_changed.emit()
        answer = QMessageBox.question(self, "Surat tersimpan", "Surat dan transaksi FIFO berhasil disimpan. Ekspor PDF sekarang?")
        if answer == QMessageBox.StandardButton.Yes: self.export_requested.emit(header_id)

    def refresh(self) -> None:
        self._reload_items(); self.history_table.setRowCount(0)
        for index, row in enumerate(self.repository.issue_headers()):
            _set_row(self.history_table, index, [
                date.fromisoformat(row["book_date"]).strftime("%d/%m/%Y"), row["document_number"], row["division"],
                row["line_count"], money(float(row["total_cost"]), rupiah=True),
            ], identity=int(row["id"]))

    def reload_defaults(self) -> None:
        """Muat identitas surat terbaru tanpa menimpa isian manual yang aktif."""
        settings = self.repository.settings()
        defaults = (
            (self.sender, "issue_sender"),
            (self.recipient, "issue_recipient"),
            (self.address, "issue_address"),
        )
        for widget, key in defaults:
            previous_default = widget.property("inventory_default")
            if not widget.text().strip() or widget.text() == previous_default:
                widget.setText(settings[key])
            widget.setProperty("inventory_default", settings[key])
        if not self.request_basis.text().strip() or self.request_basis.text() == self._automatic_basis:
            self.request_basis.clear()
            self._automatic_basis = ""
            self._division_changed(self.division.currentText())

    def _export_selected(self) -> None:
        identity = _selected_id(self.history_table)
        if identity is None: QMessageBox.information(self, "Pilih surat", "Pilih surat yang akan diekspor.")
        else: self.export_requested.emit(identity)

    def _print_selected(self) -> None:
        identity = _selected_id(self.history_table)
        if identity is None: QMessageBox.information(self, "Pilih surat", "Pilih surat yang akan dicetak.")
        else: self.print_requested.emit(identity)


class CardReportTab(QWidget):
    export_requested = Signal(int, object, object)
    print_requested = Signal(int, object, object)

    def __init__(self, repository: InventoryRepository) -> None:
        super().__init__(); self.repository = repository; self.rows = []
        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        self.item_combo = _editable_combo([]); self.start = _date_edit(date(date.today().year, 1, 1)); self.end = _date_edit()
        load = QPushButton("Tampilkan"); load.clicked.connect(self.refresh_data)
        filters.addWidget(QLabel("Barang:")); filters.addWidget(self.item_combo, 1)
        filters.addWidget(QLabel("Dari:")); filters.addWidget(self.start); filters.addWidget(QLabel("Sampai:")); filters.addWidget(self.end); filters.addWidget(load)
        layout.addLayout(filters)
        self.table = _table(["Tanggal", "No. Surat", "Uraian", "Masuk", "Keluar", "Sisa", "Harga", "Bertambah", "Berkurang", "Nilai Sisa"], stretch_column=2)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout(); actions.addStretch()
        export = QPushButton("Ekspor PDF"); export.clicked.connect(self._export)
        print_button = QPushButton("Cetak Langsung"); print_button.setObjectName("PrimaryButton"); print_button.clicked.connect(self._print)
        actions.addWidget(export); actions.addWidget(print_button); layout.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        current = self.item_combo.currentData(); self.item_combo.clear()
        for item in self.repository.items(): self.item_combo.addItem(item.label, item.item_id)
        self.item_combo.setCurrentIndex(self.item_combo.findData(current))
        if self.item_combo.currentIndex() < 0: self.item_combo.setEditText("")
        self.refresh_data()

    def refresh_data(self) -> None:
        start, end = _python_date(self.start), _python_date(self.end)
        if start > end:
            QMessageBox.warning(self, "Periode tidak valid", "Tanggal awal tidak boleh melebihi tanggal akhir.")
            return
        item_id = self.item_combo.currentData(); self.rows = [] if item_id is None else self.repository.card_rows(int(item_id), start, end)
        self.table.setRowCount(0)
        for index, row in enumerate(self.rows):
            _set_row(self.table, index, [
                row.book_date.strftime("%d/%m/%Y"), row.document_number, row.description,
                quantity(row.quantity_in, dash_zero=True), quantity(row.quantity_out, dash_zero=True), quantity(row.balance_quantity, dash_zero=True),
                money(row.unit_price, dash_zero=True), money(row.value_in, dash_zero=True), money(row.value_out, dash_zero=True), money(row.balance_value, dash_zero=True),
            ])

    def _request(self, signal: Signal) -> None:
        item_id = self.item_combo.currentData()
        if item_id is None: QMessageBox.information(self, "Pilih barang", "Pilih barang terlebih dahulu."); return
        signal.emit(int(item_id), _python_date(self.start), _python_date(self.end))

    def _export(self) -> None: self._request(self.export_requested)
    def _print(self) -> None: self._request(self.print_requested)


class MutationReportTab(QWidget):
    export_requested = Signal(object)
    print_requested = Signal(object)

    def __init__(self, repository: InventoryRepository) -> None:
        super().__init__(); self.repository = repository; self.rows = []
        layout = QVBoxLayout(self); filters = QHBoxLayout()
        self.as_of = _date_edit(date(date.today().year, 12, 31))
        load = QPushButton("Tampilkan"); load.clicked.connect(self.refresh_data)
        filters.addWidget(QLabel("Laporan sampai dengan:")); filters.addWidget(self.as_of); filters.addWidget(load); filters.addStretch(); layout.addLayout(filters)
        self.table = _table(["No", "Uraian", "Saldo Awal", "Harga Awal", "Nilai Awal", "Tambah", "Kurang", "Saldo Akhir", "Harga Akhir", "Nilai Akhir"], stretch_column=1)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout(); actions.addStretch()
        export = QPushButton("Ekspor PDF"); export.clicked.connect(lambda: self.export_requested.emit(_python_date(self.as_of)))
        print_button = QPushButton("Cetak Langsung"); print_button.setObjectName("PrimaryButton"); print_button.clicked.connect(lambda: self.print_requested.emit(_python_date(self.as_of)))
        actions.addWidget(export); actions.addWidget(print_button); layout.addLayout(actions); self.refresh_data()

    def refresh_data(self) -> None:
        self.rows = self.repository.mutation_rows(_python_date(self.as_of)); self.table.setRowCount(0)
        for index, row in enumerate(self.rows, start=1):
            _set_row(self.table, index - 1, [
                index, row.name, quantity(row.opening_quantity, dash_zero=True), money(row.opening_price, dash_zero=True), money(row.opening_value, dash_zero=True),
                quantity(row.quantity_in, dash_zero=True), quantity(row.quantity_out, dash_zero=True), quantity(row.closing_quantity, dash_zero=True),
                money(row.closing_price, dash_zero=True), money(row.closing_value, dash_zero=True),
            ], identity=row.item_id)


class OutgoingReportTab(QWidget):
    export_pdf_requested = Signal(object, object, str)
    print_requested = Signal(object, object, str)

    def __init__(self, repository: InventoryRepository) -> None:
        super().__init__(); self.repository = repository; self.rows = []
        layout = QVBoxLayout(self); filters = QHBoxLayout()
        self.start = _date_edit(date(date.today().year, 1, 1)); self.end = _date_edit()
        self.division = QComboBox(); self.division.addItem("Semua Bagian", "")
        for value in DIVISIONS: self.division.addItem(value, value)
        load = QPushButton("Tampilkan"); load.clicked.connect(self.refresh_data)
        filters.addWidget(QLabel("Dari:")); filters.addWidget(self.start); filters.addWidget(QLabel("Sampai:")); filters.addWidget(self.end)
        filters.addWidget(QLabel("Bagian:")); filters.addWidget(self.division, 1); filters.addWidget(load); layout.addLayout(filters)
        self.table = _table(["Tanggal", "No. Surat", "Kode", "Nama Barang", "Jumlah", "Satuan", "Harga Satuan", "Nilai", "Bagian", "Keterangan"], stretch_column=3)
        layout.addWidget(self.table, 1)
        self.total = QLabel("Total: Rp 0"); self.total.setObjectName("SectionTitle")
        actions = QHBoxLayout(); actions.addWidget(self.total); actions.addStretch()
        xlsx = QPushButton("Ekspor Excel"); xlsx.clicked.connect(self._xlsx)
        pdf = QPushButton("Ekspor PDF"); pdf.clicked.connect(lambda: self.export_pdf_requested.emit(_python_date(self.start), _python_date(self.end), str(self.division.currentData() or "")))
        print_button = QPushButton("Cetak Langsung"); print_button.setObjectName("PrimaryButton"); print_button.clicked.connect(lambda: self.print_requested.emit(_python_date(self.start), _python_date(self.end), str(self.division.currentData() or "")))
        actions.addWidget(xlsx); actions.addWidget(pdf); actions.addWidget(print_button); layout.addLayout(actions); self.refresh_data()

    def refresh_data(self) -> None:
        start, end = _python_date(self.start), _python_date(self.end)
        if start > end:
            QMessageBox.warning(self, "Periode tidak valid", "Tanggal awal tidak boleh melebihi tanggal akhir."); return
        division = str(self.division.currentData() or "")
        self.rows = self.repository.outgoing_rows(start, end, division); self.table.setRowCount(0)
        for index, row in enumerate(self.rows):
            _set_row(self.table, index, [
                row.book_date.strftime("%d/%m/%Y"), row.document_number, row.code, row.name,
                quantity(row.quantity), row.unit, money(row.unit_price), money(row.total_cost), row.division,
                row.note or row.description,
            ], identity=row.header_id)
        self.total.setText(f"Total: {money(sum(row.total_cost for row in self.rows), rupiah=True)}")

    def _xlsx(self) -> None:
        if not self.rows:
            QMessageBox.information(self, "Tidak ada data", "Tidak ada data pada periode dan bagian yang dipilih."); return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan Rekap Barang Keluar", "rekap-barang-keluar.xlsx", "Excel (*.xlsx)")
        if not path: return
        if not path.lower().endswith(".xlsx"): path += ".xlsx"
        try:
            export_outgoing_xlsx(path, self.rows, _python_date(self.start), _python_date(self.end), str(self.division.currentData() or ""))
        except Exception as exc:
            QMessageBox.critical(self, "Ekspor gagal", str(exc)); return
        QMessageBox.information(self, "Ekspor selesai", f"Laporan Excel disimpan di:\n{path}")


class ReportsTab(QWidget):
    def __init__(self, repository: InventoryRepository, owner: "InventoryPage") -> None:
        super().__init__(); self.repository = repository
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 12, 0, 0)
        intro = QLabel("Pilih kategori laporan. Format PDF mengikuti contoh Kartu Persediaan, Laporan Mutasi, dan Surat Pengeluaran yang dilampirkan.")
        intro.setObjectName("InfoBanner"); intro.setWordWrap(True); layout.addWidget(intro)
        tabs = QTabWidget(); self.card = CardReportTab(repository); self.mutation = MutationReportTab(repository); self.outgoing = OutgoingReportTab(repository)
        tabs.addTab(self.card, "Kartu Persediaan Barang"); tabs.addTab(self.mutation, "Laporan Mutasi Barang"); tabs.addTab(self.outgoing, "Rekap Barang Keluar per Bagian")
        layout.addWidget(tabs, 1)
        self.card.export_requested.connect(owner.export_card); self.card.print_requested.connect(owner.print_card)
        self.mutation.export_requested.connect(owner.export_mutation); self.mutation.print_requested.connect(owner.print_mutation)
        self.outgoing.export_pdf_requested.connect(owner.export_outgoing); self.outgoing.print_requested.connect(owner.print_outgoing)

    def refresh(self) -> None:
        self.card.refresh(); self.mutation.refresh_data(); self.outgoing.refresh_data()


class SettingsTab(QWidget):
    data_changed = Signal()

    LABELS = {
        "government_name": "Nama pemerintah daerah", "office_name": "Nama perangkat daerah pada kop",
        "office_full_name": "Nama lengkap perangkat daerah",
        "office_address": "Alamat dan telepon", "office_website": "Situs web",
        "office_postal_code": "Kode pos", "city": "Kota penandatanganan",
        "province": "Provinsi", "warehouse": "Nama gudang",
        "card_attachment": "Nomor/nama lampiran Kartu", "card_title": "Judul Kartu Persediaan",
        "mutation_title": "Judul Laporan Mutasi", "issue_title": "Judul Surat Pengeluaran",
        "issue_sender": "Dari (default)", "issue_recipient": "Kepada (default)",
        "issue_address": "Alamat (default)", "secretary_title": "Jabatan penandatangan kiri",
        "secretary_name": "Nama penandatangan kiri", "secretary_nip": "NIP penandatangan kiri",
        "manager_title": "Jabatan penandatangan kanan", "manager_name": "Nama penandatangan kanan",
        "manager_nip": "NIP penandatangan kanan", "logo_path": "Logo kop surat",
        "issue_blank_rows": "Baris kosong Surat Pengeluaran", "table_font_size": "Ukuran font tabel (pt)",
        "table_line_width": "Ketebalan garis tabel", "page_margin_mm": "Margin kiri/kanan (mm)",
    }

    def __init__(self, repository: InventoryRepository) -> None:
        super().__init__(); self.repository = repository; self.fields: dict[str, QLineEdit] = {}
        root = QVBoxLayout(self); root.setContentsMargins(0, 12, 0, 0)
        info = QLabel("Identitas kop, penandatangan, judul, margin, font, dan garis tabel dapat diubah tanpa mengedit source code.")
        info.setObjectName("InfoBanner"); info.setWordWrap(True); root.addWidget(info)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget(); form = QFormLayout(host); form.setContentsMargins(8, 8, 20, 8); form.setSpacing(10)
        values = repository.settings()
        for key, label in self.LABELS.items():
            field = QLineEdit(values.get(key, DEFAULT_SETTINGS.get(key, "")))
            if key == "logo_path":
                row = QHBoxLayout(); row.addWidget(field, 1)
                browse = QPushButton("Pilih..."); browse.clicked.connect(lambda _=False, target=field: self._browse_logo(target)); row.addWidget(browse)
                wrapper = QWidget(); wrapper.setLayout(row); form.addRow(label, wrapper)
            else:
                form.addRow(label, field)
            self.fields[key] = field
        save = QPushButton("Simpan Pengaturan Dokumen"); save.setObjectName("PrimaryButton"); save.clicked.connect(self._save)
        form.addRow("", save); scroll.setWidget(host); root.addWidget(scroll, 1)

    def _browse_logo(self, field: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Pilih Logo Kop", "", "Gambar (*.png *.jpg *.jpeg *.bmp *.ico)")
        if path: field.setText(path)

    def _save(self) -> None:
        try:
            float(self.fields["table_font_size"].text()); float(self.fields["table_line_width"].text()); float(self.fields["page_margin_mm"].text()); int(self.fields["issue_blank_rows"].text())
        except ValueError:
            QMessageBox.warning(self, "Nilai tidak valid", "Ukuran font, ketebalan garis, margin, dan baris kosong harus berupa angka."); return
        self.repository.save_settings({key: field.text() for key, field in self.fields.items()})
        QMessageBox.information(self, "Pengaturan tersimpan", "Pengaturan format dokumen berhasil disimpan."); self.data_changed.emit()


class InventoryPage(QWidget):
    """Workspace Persediaan Barang terpadu dengan FIFO dan empat laporan."""

    def __init__(self, username: str = "") -> None:
        super().__init__(); self.repository = InventoryRepository(); self.username = username
        root = QVBoxLayout(self); root.setContentsMargins(28, 22, 28, 20); root.setSpacing(12)
        heading = QHBoxLayout(); titles = QVBoxLayout()
        title = QLabel("Persediaan Barang"); title.setObjectName("PageTitle")
        subtitle = QLabel("Pencatatan FIFO, barang masuk/keluar, laporan resmi, dan pencetakan langsung."); subtitle.setObjectName("Subtitle")
        titles.addWidget(title); titles.addWidget(subtitle); heading.addLayout(titles); heading.addStretch()
        self.printers = QComboBox(); self.printers.setMinimumWidth(260)
        reload_printers = QPushButton("Muat Ulang Printer"); reload_printers.clicked.connect(self._load_printers)
        heading.addWidget(QLabel("Printer:")); heading.addWidget(self.printers); heading.addWidget(reload_printers); root.addLayout(heading)
        self.tabs = QTabWidget(); self.dashboard = InventoryDashboard(self.repository); self.items = ItemsTab(self.repository)
        self.receipts = ReceiptTab(self.repository); self.issues = IssueTab(self.repository, username)
        self.reports = ReportsTab(self.repository, self); self.settings = SettingsTab(self.repository)
        self.tabs.addTab(self.dashboard, "Dashboard Persediaan"); self.tabs.addTab(self.items, "Referensi Barang")
        self.tabs.addTab(self.receipts, "Persediaan Masuk"); self.tabs.addTab(self.issues, "Persediaan Keluar")
        self.tabs.addTab(self.reports, "Kategori Laporan"); self.tabs.addTab(self.settings, "Pengaturan Dokumen")
        root.addWidget(self.tabs, 1)
        self.items.data_changed.connect(self._refresh_all); self.receipts.data_changed.connect(self._refresh_all)
        self.issues.data_changed.connect(self._refresh_all); self.settings.data_changed.connect(self._settings_changed)
        self.issues.export_requested.connect(self.export_issue); self.issues.print_requested.connect(self.print_issue)
        self.tabs.currentChanged.connect(lambda _index: self.refresh())
        self._load_printers(); self.refresh()

    def _refresh_all(self) -> None:
        self.dashboard.refresh(); self.items.refresh(); self.receipts.refresh(); self.issues.refresh(); self.reports.refresh()

    def refresh(self) -> None:
        current = self.tabs.currentWidget()
        if hasattr(current, "refresh"): current.refresh()

    def _settings_changed(self) -> None:
        self.issues.reload_defaults()
        self.refresh()

    def _load_printers(self) -> None:
        current = self.printers.currentText(); names = QPrinterInfo.availablePrinterNames()
        self.printers.clear(); self.printers.addItems(names)
        index = self.printers.findText(current)
        if index >= 0: self.printers.setCurrentIndex(index)
        elif QPrinterInfo.defaultPrinter().printerName(): self.printers.setCurrentText(QPrinterInfo.defaultPrinter().printerName())
        if not names: self.printers.addItem("Printer tidak ditemukan")

    def _report_service(self) -> InventoryReportService:
        return InventoryReportService(self.repository.settings())

    def _export_pdf(self, default_name: str, builder) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Simpan Dokumen PDF", default_name, "PDF (*.pdf)")
        if not path: return
        if not path.lower().endswith(".pdf"): path += ".pdf"
        try: builder(path)
        except Exception as exc: QMessageBox.critical(self, "Dokumen gagal dibuat", str(exc)); return
        QMessageBox.information(self, "Dokumen selesai", f"PDF disimpan di:\n{path}")

    def _print_builder(self, builder) -> None:
        if not QPrinterInfo.availablePrinterNames():
            QMessageBox.warning(self, "Printer tidak ditemukan", "Windows tidak mendeteksi printer aktif."); return
        with tempfile.TemporaryDirectory(prefix="setwan-inventory-print-") as directory:
            path = Path(directory) / "inventory-report.pdf"
            try: builder(path); self._print_pdf(path)
            except Exception as exc: QMessageBox.critical(self, "Pencetakan gagal", str(exc))

    def _print_pdf(self, path: Path) -> None:
        import fitz
        selected_name = self.printers.currentText()
        info = next((candidate for candidate in QPrinterInfo.availablePrinters() if candidate.printerName() == selected_name), QPrinterInfo.defaultPrinter())
        printer = QPrinter(info, QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.NativeFormat); printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4)); printer.setFullPage(True)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted: return
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4)); printer.setFullPage(True)
        document = fitz.open(path)
        try:
            painter = QPainter(printer)
            if not painter.isActive(): raise RuntimeError("Driver printer tidak dapat memulai pekerjaan cetak.")
            try:
                target = QRectF(printer.pageRect(QPrinter.Unit.DevicePixel))
                for index, page in enumerate(document):
                    if index and not printer.newPage(): raise RuntimeError("Printer menolak membuat halaman berikutnya.")
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), alpha=False)
                    image = QImage(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, QImage.Format.Format_RGB888).copy()
                    painter.drawImage(target, image, QRectF(image.rect()))
            finally: painter.end()
        finally: document.close()

    def export_issue(self, header_id: int) -> None:
        document = self.repository.issue_document(header_id); number = str(document["header"]["document_number"]).replace("/", "-")
        self._export_pdf(f"surat-pengeluaran-{number}.pdf", lambda path: self._report_service().build_issue_order(path, document))

    def print_issue(self, header_id: int) -> None:
        document = self.repository.issue_document(header_id)
        self._print_builder(lambda path: self._report_service().build_issue_order(path, document))

    def export_card(self, item_id: int, start: date, end: date) -> None:
        item = self.repository.item(item_id); rows = self.repository.card_rows(item_id, start, end)
        if not item: return
        self._export_pdf(f"kartu-persediaan-{item.code}.pdf", lambda path: self._report_service().build_card(path, item, rows))

    def print_card(self, item_id: int, start: date, end: date) -> None:
        item = self.repository.item(item_id); rows = self.repository.card_rows(item_id, start, end)
        if item: self._print_builder(lambda path: self._report_service().build_card(path, item, rows))

    def export_mutation(self, as_of: date) -> None:
        rows = self.repository.mutation_rows(as_of)
        self._export_pdf(f"laporan-mutasi-{as_of.isoformat()}.pdf", lambda path: self._report_service().build_mutation(path, rows, as_of))

    def print_mutation(self, as_of: date) -> None:
        rows = self.repository.mutation_rows(as_of)
        self._print_builder(lambda path: self._report_service().build_mutation(path, rows, as_of))

    def export_outgoing(self, start: date, end: date, division: str) -> None:
        rows = self.repository.outgoing_rows(start, end, division)
        self._export_pdf(f"rekap-barang-keluar-{start.isoformat()}-{end.isoformat()}.pdf", lambda path: self._report_service().build_outgoing_recap(path, rows, start, end, division))

    def print_outgoing(self, start: date, end: date, division: str) -> None:
        rows = self.repository.outgoing_rows(start, end, division)
        self._print_builder(lambda path: self._report_service().build_outgoing_recap(path, rows, start, end, division))
