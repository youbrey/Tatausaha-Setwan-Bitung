from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from html import escape

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from tpp_finger_scan.application.services import RecapSession
from tpp_finger_scan.domain.calendar import schedule_for
from tpp_finger_scan.domain.models import ZERO


class PrinterService:
    @staticmethod
    def available_printers() -> list[str]:
        return sorted(info.printerName() for info in QPrinterInfo.availablePrinters())

    def print_summary(self, session: RecapSession, printer_name: str) -> None:
        if not printer_name:
            raise RuntimeError("Pilih printer sebelum mencetak.")
        available = self.available_printers()
        if printer_name not in available:
            raise RuntimeError(f"Printer tidak lagi tersedia: {printer_name}")

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPrinterName(printer_name)
        printer.setDocName(
            f"Rekap TPP {session.import_result.period_start:%Y%m%d}-"
            f"{session.import_result.period_end:%Y%m%d}"
        )
        printer.setPageLayout(QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Landscape,
            QMarginsF(8, 8, 8, 8),
            QPageLayout.Unit.Millimeter,
        ))

        document = QTextDocument()
        document.setDocumentMargin(18)
        document.setHtml(self._summary_html(session))
        document.print_(printer)

    @staticmethod
    def _summary_html(session: RecapSession) -> str:
        start = session.import_result.period_start
        end = session.import_result.period_end
        if (end - start).days >= 2:
            start += timedelta(days=1)
            end -= timedelta(days=1)
        report_dates = set()
        current = start
        while current <= end:
            if schedule_for(current).workday and current not in session.holidays:
                report_dates.add(current)
            current += timedelta(days=1)
        grouped = defaultdict(list)
        for calculation in session.calculations:
            if calculation.entry.work_date in report_dates:
                grouped[calculation.entry.employee.finger_id].append(calculation)

        rows = []
        for number, employee in enumerate(session.import_result.employees, start=1):
            calculations = grouped[employee.finger_id]
            absence = sum((item.deductions.absence for item in calculations), ZERO)
            late = sum((item.deductions.late for item in calculations), ZERO)
            early = sum((item.deductions.early for item in calculations), ZERO)
            review = sum(not item.finalizable for item in calculations)
            rows.append(
                "<tr>"
                f"<td>{number}</td><td>{escape(employee.finger_id)}</td>"
                f"<td>{escape(employee.name)}</td><td>{absence:.2f}%</td>"
                f"<td>{late:.2f}%</td><td>{early:.2f}%</td>"
                f"<td>{absence + late + early:.2f}%</td><td>{review}</td>"
                "</tr>"
            )
        report_blocking_count = (
            sum(
                not calculation.finalizable
                for calculation in session.calculations
                if calculation.entry.work_date in report_dates
            )
            + len(session.import_result.issues)
        )
        draft = "DRAFT — PERLU REVIEW" if report_blocking_count else "FINAL"
        return f"""
        <html><head><style>
        body {{ font-family: 'Segoe UI'; color: #17324d; font-size: 9pt; }}
        h1 {{ font-size: 15pt; margin: 0; }}
        .meta {{ margin: 4px 0 12px; color: #52606d; }}
        .draft {{ color: #b42318; font-weight: bold; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th {{ background: #1d73e8; color: white; padding: 5px; }}
        td {{ border: 1px solid #cfd8e3; padding: 4px; }}
        td:nth-child(1), td:nth-child(4), td:nth-child(5), td:nth-child(6),
        td:nth-child(7), td:nth-child(8) {{ text-align: center; }}
        </style></head><body>
        <h1>REKAPITULASI POTONGAN DISIPLIN KERJA</h1>
        <div class="meta">Periode {start:%d-%m-%Y} s/d
        {end:%d-%m-%Y} · <span class="draft">{draft}</span></div>
        <table><thead><tr><th>No</th><th>ID Finger</th><th>Nama Pegawai</th>
        <th>Tidak Masuk</th><th>Terlambat</th><th>Pulang Cepat</th>
        <th>Jumlah</th><th>Review</th></tr></thead>
        <tbody>{''.join(rows)}</tbody></table></body></html>
        """
