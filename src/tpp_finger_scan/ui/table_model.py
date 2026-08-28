from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

from tpp_finger_scan.application.services import RecapSession
from tpp_finger_scan.domain.calendar import day_name_id
from tpp_finger_scan.domain.models import AttendanceState, DayCalculation


class CalculationTableModel(QAbstractTableModel):
    headers = (
        "Tanggal", "Hari", "ID Finger", "Nama Pegawai", "Masuk", "Pulang",
        "Kode", "Tidak Masuk", "Terlambat", "Pulang Cepat", "Jumlah",
        "Status", "Catatan Review",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.session: RecapSession | None = None

    @property
    def calculations(self) -> list[DayCalculation]:
        return self.session.calculations if self.session else []

    def set_session(self, session: RecapSession | None) -> None:
        self.beginResetModel()
        self.session = session
        self.endResetModel()

    def refresh(self) -> None:
        self.beginResetModel()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.calculations)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self.headers[section]
            return section + 1
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.calculations)):
            return None
        calculation = self.calculations[index.row()]
        entry = calculation.entry
        override = None
        if self.session:
            override = self.session.overrides.get((entry.employee.finger_id, entry.work_date))

        if role == Qt.ItemDataRole.DisplayRole:
            values = (
                entry.work_date.strftime("%d/%m/%Y"),
                day_name_id(entry.work_date),
                entry.employee.finger_id,
                entry.employee.name,
                entry.in_time.strftime("%H:%M") if entry.in_time else "—",
                entry.out_time.strftime("%H:%M") if entry.out_time else "—",
                override.code.value if override else "",
                self._percent(calculation.deductions.absence),
                self._percent(calculation.deductions.late),
                self._percent(calculation.deductions.early),
                self._percent(calculation.deductions.total),
                calculation.status,
                " | ".join(issue.message for issue in calculation.issues),
            )
            return values[index.column()]
        if role == Qt.ItemDataRole.UserRole:
            return calculation
        if role == Qt.ItemDataRole.UserRole + 1:
            return (
                entry.state.value,
                not calculation.finalizable,
                calculation.deductions.total > 0,
            )
        if role == Qt.ItemDataRole.BackgroundRole:
            if calculation.highlight_yellow:
                return QColor("#FFF2CC")
            if not calculation.finalizable:
                return QColor("#FCE8E6")
        if role == Qt.ItemDataRole.ForegroundRole and not calculation.finalizable:
            return QColor("#8A1C13")
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in {0, 1, 2, 4, 5, 6, 7, 8, 9, 10}:
            return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole and calculation.issues:
            return "\n".join(issue.message for issue in calculation.issues)
        return None

    @staticmethod
    def _percent(value) -> str:
        return "" if not value else f"{value:.2f}%"


class CalculationFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.search_text = ""
        self.mode = "Semua"
        self.setDynamicSortFilter(True)

    def set_search_text(self, value: str) -> None:
        self.search_text = value.casefold().strip()
        self.invalidateFilter()

    def set_mode(self, value: str) -> None:
        self.mode = value
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return False
        state, needs_review, has_deduction = model.index(source_row, 0).data(Qt.ItemDataRole.UserRole + 1)
        if self.mode == "Perlu Review" and not needs_review:
            return False
        if self.mode == "Ada Potongan" and not has_deduction:
            return False
        if self.mode == "Finger Tidak Lengkap" and state not in {
            AttendanceState.MISSING_IN.value,
            AttendanceState.MISSING_OUT.value,
            AttendanceState.MISSING_BOTH.value,
        }:
            return False
        if not self.search_text:
            return True
        haystack = " ".join(
            str(model.index(source_row, column).data() or "")
            for column in (0, 2, 3, 11, 12)
        ).casefold()
        return self.search_text in haystack
