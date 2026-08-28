from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from tpp_finger_scan.application.services import AttendanceApplicationService, RecapSession
from tpp_finger_scan.config import database_path
from tpp_finger_scan.domain.models import SpecialCode
from tpp_finger_scan.infrastructure.excel_exporter import ExcelExporter
from tpp_finger_scan.infrastructure.employee_master import EmployeeMaster
from tpp_finger_scan.infrastructure.pdf_parser import PdfParseError
from tpp_finger_scan.infrastructure.printing import PrinterService
from tpp_finger_scan.infrastructure.repository import SQLiteRepository
from tpp_finger_scan.ui.table_model import CalculationFilterProxy, CalculationTableModel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TPP Finger Scan")
        self.resize(1480, 860)
        self.setMinimumSize(1100, 700)

        self.service = AttendanceApplicationService()
        self.exporter = ExcelExporter()
        self.printers = PrinterService()
        self.repository = SQLiteRepository(database_path())
        self.employee_master = EmployeeMaster()
        self.session: RecapSession | None = None

        self.table_model = CalculationTableModel(self)
        self.proxy_model = CalculationFilterProxy(self)
        self.proxy_model.setSourceModel(self.table_model)

        self._build_ui()
        self._load_stylesheet()
        self._refresh_printers()
        self._set_actions_enabled(False)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("TPP Finger Scan")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Rekap potongan disiplin kerja · 100% offline")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        offline = QLabel("●  OFFLINE")
        offline.setObjectName("OfflineBadge")
        header.addWidget(offline, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

        import_card = QFrame()
        import_card.setObjectName("Card")
        import_layout = QHBoxLayout(import_card)
        import_layout.setContentsMargins(18, 16, 18, 16)
        import_layout.setSpacing(10)
        source_label = QLabel("Dokumen finger scan")
        source_label.setObjectName("FieldLabel")
        import_layout.addWidget(source_label)
        self.path_field = QLineEdit()
        self.path_field.setPlaceholderText("Pilih PDF hasil finger scan…")
        self.path_field.returnPressed.connect(self._import_pdf)
        import_layout.addWidget(self.path_field, 1)
        browse_button = QPushButton("Pilih PDF")
        browse_button.clicked.connect(self._browse_pdf)
        import_layout.addWidget(browse_button)
        self.import_button = QPushButton("Proses Dokumen")
        self.import_button.setObjectName("PrimaryButton")
        self.import_button.clicked.connect(self._import_pdf)
        import_layout.addWidget(self.import_button)
        layout.addWidget(import_card)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.stat_values: dict[str, QLabel] = {}
        for key, caption in (
            ("employees", "Pegawai"),
            ("period", "Hari dalam periode"),
            ("entries", "Data kehadiran"),
            ("review", "Perlu review"),
        ):
            card, value_label = self._stat_card(caption)
            self.stat_values[key] = value_label
            stats.addWidget(card, 1)
        layout.addLayout(stats)

        control_card = QFrame()
        control_card.setObjectName("Card")
        controls = QHBoxLayout(control_card)
        controls.setContentsMargins(14, 12, 14, 12)
        controls.setSpacing(9)
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Cari nama, ID, tanggal, atau status…")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self.proxy_model.set_search_text)
        controls.addWidget(self.search_field, 2)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(("Semua", "Perlu Review", "Ada Potongan", "Finger Tidak Lengkap"))
        self.filter_combo.currentTextChanged.connect(self.proxy_model.set_mode)
        controls.addWidget(self.filter_combo)
        controls.addSpacing(8)
        controls.addWidget(QLabel("Kode pilihan:"))
        self.code_combo = QComboBox()
        self.code_combo.addItems(("— Hapus kode —", "TL", "WFH", "W", "I", "S"))
        self.code_combo.currentTextChanged.connect(self._code_changed)
        controls.addWidget(self.code_combo)
        self.inpatient_checkbox = QCheckBox("Rawat inap")
        self.inpatient_checkbox.setEnabled(False)
        controls.addWidget(self.inpatient_checkbox)
        self.apply_code_button = QPushButton("Terapkan")
        self.apply_code_button.clicked.connect(self._apply_code)
        controls.addWidget(self.apply_code_button)
        self.position_button = QPushButton("Isi Jabatan")
        self.position_button.clicked.connect(self._edit_position)
        controls.addWidget(self.position_button)
        self.holiday_button = QPushButton("Atur Hari Libur")
        self.holiday_button.clicked.connect(self._toggle_holiday)
        controls.addWidget(self.holiday_button)
        layout.addWidget(control_card)

        self.table = QTableView()
        self.table.setObjectName("ResultTable")
        self.table.setModel(self.proxy_model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 102)
        self.table.setColumnWidth(1, 84)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 220)
        self.table.setColumnWidth(4, 72)
        self.table.setColumnWidth(5, 72)
        self.table.setColumnWidth(6, 65)
        self.table.setColumnWidth(7, 100)
        self.table.setColumnWidth(8, 90)
        self.table.setColumnWidth(9, 105)
        self.table.setColumnWidth(10, 80)
        self.table.setColumnWidth(11, 155)
        self.table.setColumnWidth(12, 360)
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        self.status_label = QLabel("Pilih PDF untuk memulai.")
        self.status_label.setObjectName("StatusLabel")
        footer.addWidget(self.status_label, 1)
        self.printer_combo = QComboBox()
        self.printer_combo.setMinimumWidth(220)
        footer.addWidget(self.printer_combo)
        refresh_printer = QPushButton("Muat Ulang Printer")
        refresh_printer.clicked.connect(self._refresh_printers)
        footer.addWidget(refresh_printer)
        self.print_button = QPushButton("Cetak Ringkasan")
        self.print_button.clicked.connect(self._print_summary)
        footer.addWidget(self.print_button)
        self.export_button = QPushButton("Ekspor Excel")
        self.export_button.setObjectName("PrimaryButton")
        self.export_button.clicked.connect(self._export_excel)
        footer.addWidget(self.export_button)
        layout.addLayout(footer)

    @staticmethod
    def _stat_card(caption: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("StatCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        value = QLabel("—")
        value.setObjectName("StatValue")
        label = QLabel(caption)
        label.setObjectName("StatLabel")
        card_layout.addWidget(value)
        card_layout.addWidget(label)
        return card, value

    def _browse_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih dokumen finger scan",
            "",
            "PDF (*.pdf)",
        )
        if path:
            self.path_field.setText(path)
            self._import_pdf()

    def _import_pdf(self) -> None:
        path = self.path_field.text().strip()
        if not path:
            QMessageBox.information(self, "Belum ada dokumen", "Pilih PDF finger scan terlebih dahulu.")
            return
        self.import_button.setEnabled(False)
        self.status_label.setText("Membaca struktur PDF dan menghitung potongan…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            session = self.service.import_pdf(path)
            employees = session.import_result.employees
            stored_positions = self.repository.employee_positions(
                [employee.finger_id for employee in employees]
            )
            reference_positions = self.employee_master.resolve_positions(employees)
            session.employee_positions = {**reference_positions, **stored_positions}
            for employee in employees:
                if employee.finger_id not in stored_positions:
                    position = reference_positions.get(employee.finger_id, "")
                    if position:
                        self.repository.save_employee_position(
                            employee.finger_id,
                            employee.name,
                            position,
                        )
            self.repository.save_session(session)
        except (PdfParseError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Dokumen tidak dapat diproses", str(exc))
            self.status_label.setText("Impor gagal. Periksa format PDF.")
            return
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Kesalahan aplikasi",
                f"Terjadi kesalahan yang tidak terduga:\n{exc}",
            )
            self.status_label.setText("Impor gagal.")
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.import_button.setEnabled(True)

        self.session = session
        self.table_model.set_session(session)
        self._update_summary()
        self._set_actions_enabled(True)
        self.status_label.setText(
            f"Selesai memproses {len(session.import_result.employees)} pegawai. "
            f"{session.blocking_count} baris memerlukan review."
        )

    def _update_summary(self) -> None:
        if not self.session:
            return
        result = self.session.import_result
        self.stat_values["employees"].setText(str(len(result.employees)))
        self.stat_values["period"].setText(str(result.date_count))
        self.stat_values["entries"].setText(f"{len(result.entries):,}".replace(",", "."))
        self.stat_values["review"].setText(str(self.session.blocking_count))
        self.stat_values["review"].setProperty("alert", self.session.blocking_count > 0)
        self.stat_values["review"].style().unpolish(self.stat_values["review"])
        self.stat_values["review"].style().polish(self.stat_values["review"])

    def _code_changed(self, text: str) -> None:
        is_sick = text == "S"
        self.inpatient_checkbox.setEnabled(is_sick)
        if not is_sick:
            self.inpatient_checkbox.setChecked(False)

    def _apply_code(self) -> None:
        if not self.session:
            return
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "Belum ada pilihan", "Pilih satu atau beberapa baris terlebih dahulu.")
            return
        text = self.code_combo.currentText()
        code = SpecialCode.NONE if text.startswith("—") else SpecialCode(text)
        inpatient = code == SpecialCode.S and self.inpatient_checkbox.isChecked()

        keys = set()
        for proxy_index in selected:
            source_index = self.proxy_model.mapToSource(proxy_index)
            calculation = self.table_model.calculations[source_index.row()]
            keys.add((calculation.entry.employee.finger_id, calculation.entry.work_date))
        for finger_id, work_date in keys:
            self.service.set_override(
                self.session,
                finger_id,
                work_date,
                code,
                inpatient=inpatient,
            )
        self.table_model.refresh()
        self._update_summary()
        self.status_label.setText(f"Kode {code.value or 'dihapus'} diterapkan ke {len(keys)} baris.")

    def _edit_position(self) -> None:
        if not self.session:
            return
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(
                self,
                "Belum ada pilihan",
                "Pilih baris pegawai yang jabatannya akan diisi.",
            )
            return
        employees = {}
        for proxy_index in selected:
            source_index = self.proxy_model.mapToSource(proxy_index)
            employee = self.table_model.calculations[source_index.row()].entry.employee
            employees[employee.finger_id] = employee
        first = next(iter(employees.values()))
        current = self.session.employee_positions.get(first.finger_id, "")
        position, accepted = QInputDialog.getText(
            self,
            "Jabatan Pegawai",
            (
                f"Masukkan jabatan untuk {first.name}:"
                if len(employees) == 1
                else f"Masukkan jabatan yang sama untuk {len(employees)} pegawai:"
            ),
            text=current,
        )
        if not accepted:
            return
        position = position.strip()
        for employee in employees.values():
            if position:
                self.session.employee_positions[employee.finger_id] = position
            else:
                self.session.employee_positions.pop(employee.finger_id, None)
            self.repository.save_employee_position(employee.finger_id, employee.name, position)
        self.status_label.setText(f"Jabatan diperbarui untuk {len(employees)} pegawai.")

    def _toggle_holiday(self) -> None:
        if not self.session:
            return
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(
                self,
                "Belum ada pilihan",
                "Pilih satu atau beberapa baris tanggal terlebih dahulu.",
            )
            return
        dates = set()
        for proxy_index in selected:
            source_index = self.proxy_model.mapToSource(proxy_index)
            dates.add(self.table_model.calculations[source_index.row()].entry.work_date)
        remove = all(work_date in self.session.holidays for work_date in dates)
        for work_date in dates:
            if remove:
                self.session.holidays.discard(work_date)
            else:
                self.session.holidays.add(work_date)
        self.service.recalculate(self.session)
        self.table_model.refresh()
        self._update_summary()
        action = "dihapus dari hari libur" if remove else "ditandai sebagai hari libur"
        self.status_label.setText(f"{len(dates)} tanggal {action}.")

    def _export_excel(self) -> None:
        if not self.session:
            return
        result = self.session.import_result
        suggested = (
            f"Rekap_TPP_{result.period_start:%Y%m%d}_{result.period_end:%Y%m%d}.xlsx"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Ekspor rekap Excel",
            str(Path.home() / "Documents" / suggested),
            "Excel Workbook (*.xlsx)",
        )
        if not path:
            return
        try:
            target = self.exporter.export(self.session, path)
            self.repository.save_session(self.session)
        except Exception as exc:
            QMessageBox.critical(self, "Ekspor gagal", str(exc))
            return
        draft_note = (
            f"\n\nDokumen masih memiliki {self.session.blocking_count} baris review dan "
            "ditandai sebagai data yang perlu diperiksa."
            if self.session.blocking_count else ""
        )
        QMessageBox.information(
            self,
            "Ekspor selesai",
            f"File Excel tersimpan di:\n{target}{draft_note}",
        )
        self.status_label.setText(f"Ekspor selesai: {target.name}")

    def _refresh_printers(self) -> None:
        previous = self.printer_combo.currentText() if self.printer_combo.count() else ""
        self.printer_combo.clear()
        names = self.printers.available_printers()
        if names:
            self.printer_combo.addItems(names)
            if previous in names:
                self.printer_combo.setCurrentText(previous)
        else:
            self.printer_combo.addItem("Printer tidak ditemukan")
        if hasattr(self, "print_button"):
            self.print_button.setEnabled(bool(names) and self.session is not None)

    def _print_summary(self) -> None:
        if not self.session:
            return
        if self.session.blocking_count:
            answer = QMessageBox.question(
                self,
                "Cetak sebagai draft?",
                f"Masih ada {self.session.blocking_count} baris yang memerlukan review. "
                "Dokumen akan diberi label DRAFT. Lanjutkan?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self.printers.print_summary(self.session, self.printer_combo.currentText())
        except Exception as exc:
            QMessageBox.critical(self, "Pencetakan gagal", str(exc))
            return
        self.status_label.setText(f"Dokumen dikirim ke {self.printer_combo.currentText()}.")

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.export_button.setEnabled(enabled)
        self.apply_code_button.setEnabled(enabled)
        self.position_button.setEnabled(enabled)
        self.holiday_button.setEnabled(enabled)
        has_printer = self.printer_combo.count() and self.printer_combo.currentText() != "Printer tidak ditemukan"
        self.print_button.setEnabled(enabled and bool(has_printer))

    @staticmethod
    def _load_stylesheet() -> None:
        stylesheet = files("tpp_finger_scan.resources").joinpath("style.qss").read_text(encoding="utf-8")
        QApplication.instance().setStyleSheet(stylesheet)

    def closeEvent(self, event: QCloseEvent) -> None:
        event.accept()
