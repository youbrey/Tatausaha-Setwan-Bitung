from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import fitz

from sekretariat_app.inventory.models import DIVISIONS, InventoryItem, IssueLine
from sekretariat_app.inventory.reports import InventoryReportService
from sekretariat_app.inventory.repository import InventoryRepository


class InventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repository = InventoryRepository(self.root / "inventory.sqlite3")
        self.item_id = self.repository.save_item(InventoryItem(
            None, "UJI-001", "Barang Uji", "Buah", "Pengujian",
        ))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _receipt(self, number: str, quantity: float, price: float, day: int) -> None:
        self.repository.record_receipt(
            item_id=self.item_id,
            document_number=number,
            book_date=date(2026, 9, day),
            transaction_type="Pembelian",
            quantity=quantity,
            unit_price=price,
        )

    def test_issue_consumes_oldest_batches_and_reports_correct_balance(self) -> None:
        self._receipt("IN-1", 5, 100, 1)
        self._receipt("IN-2", 5, 200, 2)
        header_id = self.repository.create_issue(
            document_number="OUT-1",
            book_date=date(2026, 9, 3),
            division=DIVISIONS[0],
            sender="Pengguna Barang",
            recipient="Pengurus Barang",
            address="Bitung",
            request_basis="Permintaan unit",
            transaction_type="Pemakaian",
            lines=[IssueLine(self.item_id, 7)],
            created_by="tester",
        )

        stock = self.repository.stock_for_item(self.item_id)
        self.assertIsNotNone(stock)
        self.assertEqual(stock.quantity, 3)
        self.assertEqual(stock.value, 600)
        document = self.repository.issue_document(header_id)
        self.assertEqual(document["lines"][0]["total_cost"], 900)

        rows = self.repository.card_rows(self.item_id)
        self.assertEqual(rows[-1].balance_quantity, 3)
        self.assertEqual(rows[-1].balance_value, 600)

    def test_insufficient_stock_rolls_back_entire_issue(self) -> None:
        self._receipt("IN-1", 2, 100, 1)
        with self.assertRaisesRegex(ValueError, "tidak mencukupi"):
            self.repository.create_issue(
                document_number="OUT-GAGAL",
                book_date=date(2026, 9, 2),
                division=DIVISIONS[0],
                sender="Pengguna Barang",
                recipient="Pengurus Barang",
                address="Bitung",
                request_basis="Permintaan unit",
                transaction_type="Pemakaian",
                lines=[IssueLine(self.item_id, 3)],
            )
        self.assertEqual(self.repository.issue_headers(), [])
        self.assertEqual(self.repository.stock_for_item(self.item_id).quantity, 2)

    def test_issue_report_is_a_readable_pdf(self) -> None:
        self._receipt("IN-1", 4, 1250, 1)
        header_id = self.repository.create_issue(
            document_number="OUT-PDF",
            book_date=date(2026, 9, 2),
            division=DIVISIONS[1],
            sender="Pengguna Barang",
            recipient="Pengurus Barang",
            address="Bitung",
            request_basis="Permintaan unit",
            transaction_type="Pemakaian",
            lines=[IssueLine(self.item_id, 1)],
        )
        target = self.root / "surat-pengeluaran.pdf"
        InventoryReportService(self.repository.settings()).build_issue_order(
            target,
            self.repository.issue_document(header_id),
        )
        with fitz.open(target) as document:
            self.assertGreaterEqual(len(document), 1)
            self.assertIn("SURAT PERINTAH", " ".join(page.get_text() for page in document))


if __name__ == "__main__":
    unittest.main()
