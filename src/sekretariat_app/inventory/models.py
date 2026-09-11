from __future__ import annotations

from dataclasses import dataclass
from datetime import date


DIVISIONS = (
    "Bagian Umum dan Keuangan",
    "Bagian Perundang-Undangan Persidangan dan Humas",
    "Bagian Fasilitasi Penganggaran dan Pengawasan",
)

RECEIPT_TYPES = (
    "Pembelian",
    "Hibah",
    "Transfer Masuk",
    "Koreksi Penambahan",
    "Saldo Awal",
)

ISSUE_TYPES = (
    "Pemakaian",
    "Penyaluran",
    "Transfer Keluar",
    "Koreksi Pengurangan",
)


@dataclass(slots=True)
class InventoryItem:
    item_id: int | None
    code: str
    name: str
    unit: str
    category: str = ""
    specification: str = ""
    card_number: str = ""
    standard_price: float = 0.0
    active: bool = True

    @property
    def label(self) -> str:
        return f"{self.code} - {self.name}"


@dataclass(slots=True)
class StockSummary:
    item_id: int
    code: str
    name: str
    unit: str
    category: str
    quantity: float
    value: float

    @property
    def average_price(self) -> float:
        return self.value / self.quantity if self.quantity else 0.0


@dataclass(slots=True)
class IssueLine:
    item_id: int
    quantity: float
    note: str = ""


@dataclass(slots=True)
class CardRow:
    book_date: date
    document_number: str
    description: str
    quantity_in: float
    quantity_out: float
    balance_quantity: float
    unit_price: float
    value_in: float
    value_out: float
    balance_value: float
    note: str = ""


@dataclass(slots=True)
class MutationRow:
    item_id: int
    code: str
    name: str
    unit: str
    category: str
    opening_quantity: float
    opening_price: float
    opening_value: float
    quantity_in: float
    quantity_out: float
    closing_quantity: float
    closing_price: float
    closing_value: float


@dataclass(slots=True)
class OutgoingRow:
    header_id: int
    book_date: date
    document_number: str
    division: str
    code: str
    name: str
    unit: str
    quantity: float
    unit_price: float
    total_cost: float
    description: str = ""
    note: str = ""
