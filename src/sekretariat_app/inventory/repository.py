from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from sekretariat_app.config import database_path
from sekretariat_app.inventory.models import (
    CardRow,
    DIVISIONS,
    InventoryItem,
    IssueLine,
    MutationRow,
    OutgoingRow,
    StockSummary,
)


DEFAULT_SETTINGS = {
    "government_name": "PEMERINTAH KOTA BITUNG",
    "office_name": "SEKRETARIAT DPRD",
    "office_full_name": "Sekretariat DPRD Kota Bitung",
    "office_address": "Jl. R. E. Martadinata Kota Bitung  Telp. (0438) 30712, Fax. (0438) 36177",
    "office_website": "www.dprd.bitungkota.go.id",
    "office_postal_code": "Kode Pos 95511",
    "city": "Bitung",
    "province": "SULAWESI UTARA",
    "warehouse": "",
    "card_attachment": "LAMPIRAN 13",
    "card_title": "KARTU PERSEDIAAN BARANG",
    "mutation_title": "LAPORAN MUTASI BARANG",
    "issue_title": "SURAT PERINTAH PENGELUARAN/PENYALURAN BARANG",
    "issue_sender": "Pengguna/Kuasa Pengguna",
    "issue_recipient": "Pengurus Barang",
    "issue_address": "Jln. R.E Martadinata",
    "secretary_title": "SEKRETARIS DPRD KOTA BITUNG",
    "secretary_name": "Drs. ALBERT MARCELLUS SARESE, M.Si",
    "secretary_nip": "19681011 199010 1 002",
    "manager_title": "PENGURUS BARANG",
    "manager_name": "YOKTAN HELER",
    "manager_nip": "19810717 200604 1 015",
    "logo_path": "",
    "issue_blank_rows": "8",
    "table_font_size": "7.5",
    "table_line_width": "0.7",
    "page_margin_mm": "14",
}


DEFAULT_ITEMS = (
    ("ATK-001", "Pensil 2B", "Buah", "Alat Tulis Kantor", 2500),
    ("ATK-002", "Pulpen Standar", "Buah", "Alat Tulis Kantor", 3000),
    ("ATK-003", "Pulpen Gel", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-004", "Penghapus Pensil", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-005", "Penggaris 30 cm", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-006", "Spidol Whiteboard", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-007", "Spidol Permanent", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-008", "Stabilo / Highlighter", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-009", "Correction Pen (Tipe-X)", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-010", "Correction Tape", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-011", "Kertas HVS A4 70gr", "Rim", "Alat Tulis Kantor", 45000),
    ("ATK-012", "Kertas HVS F4 70gr", "Rim", "Alat Tulis Kantor", 50000),
    ("ATK-013", "Kertas HVS A4 80gr", "Rim", "Alat Tulis Kantor", 0),
    ("ATK-014", "Kertas Folio Bergaris", "Rim", "Alat Tulis Kantor", 0),
    ("ATK-015", "Amplop Coklat Besar", "Pak", "Alat Tulis Kantor", 0),
    ("ATK-016", "Amplop Putih Polos", "Pak", "Alat Tulis Kantor", 0),
    ("ATK-017", "Map Plastik", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-018", "Map Snelhecter Plastik", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-019", "Map Snelhecter Kertas", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-020", "Ordner / Map Besar", "Buah", "Alat Tulis Kantor", 35000),
    ("ATK-021", "Binder Clip Kecil", "Box", "Alat Tulis Kantor", 0),
    ("ATK-022", "Binder Clip Besar", "Box", "Alat Tulis Kantor", 0),
    ("ATK-023", "Paper Clip", "Box", "Alat Tulis Kantor", 0),
    ("ATK-024", "Stapler / Hecter Kecil", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-025", "Isi Stapler No. 10", "Box", "Alat Tulis Kantor", 0),
    ("ATK-026", "Isi Hecter Besar", "Box", "Alat Tulis Kantor", 0),
    ("ATK-027", "Perforator / Pelubang Kertas", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-028", "Gunting Kantor", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-029", "Cutter", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-030", "Lem Kertas (Glue Stick)", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-031", "Lem Kertas Cair", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-032", "Isolasi Bening (Selotip)", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-033", "Double Tape", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-034", "Post It / Sticky Notes", "Pak", "Alat Tulis Kantor", 0),
    ("ATK-035", "Buku Agenda", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-036", "Buku Folio", "Buah", "Alat Tulis Kantor", 30000),
    ("ATK-037", "Buku Tulis", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-038", "Kalkulator", "Buah", "Alat Tulis Kantor", 0),
    ("ATK-039", "Pensil Warna (Set)", "Set", "Alat Tulis Kantor", 0),
    ("ATK-040", "Karet Gelang", "Pak", "Alat Tulis Kantor", 0),
    ("HP-001", "Tinta Printer Hitam", "Botol", "Barang Habis Pakai", 120000),
    ("HP-002", "Tinta Printer Warna", "Botol", "Barang Habis Pakai", 140000),
    ("HP-003", "Toner Printer Laser Hitam", "Buah", "Barang Habis Pakai", 0),
    ("HP-004", "Toner Printer Laser Warna", "Buah", "Barang Habis Pakai", 0),
    ("HP-005", "Cartridge Printer Inkjet", "Buah", "Barang Habis Pakai", 0),
    ("HP-006", "Baterai AA", "Pak", "Barang Habis Pakai", 0),
    ("HP-007", "Baterai AAA", "Pak", "Barang Habis Pakai", 0),
    ("HP-008", "Baterai 9V", "Buah", "Barang Habis Pakai", 0),
    ("HP-009", "Lampu LED", "Buah", "Barang Habis Pakai", 0),
    ("HP-010", "Kabel Ties (Cable Tie)", "Pak", "Barang Habis Pakai", 0),
    ("HP-011", "Flashdisk 16GB", "Buah", "Barang Habis Pakai", 0),
    ("HP-012", "Flashdisk 32GB", "Buah", "Barang Habis Pakai", 0),
    ("HP-013", "CD / DVD Blank", "Pak", "Barang Habis Pakai", 0),
    ("HP-014", "Gas Elpiji 3kg", "Tabung", "Barang Habis Pakai", 0),
    ("HP-015", "Air Mineral Galon", "Galon", "Barang Habis Pakai", 0),
    ("HP-016", "Tisu Wajah (Facial Tissue)", "Box", "Barang Habis Pakai", 0),
    ("HP-017", "Materai Rp10.000", "Lembar", "Barang Habis Pakai", 10000),
    ("HP-018", "Kertas Thermal / Struk", "Roll", "Barang Habis Pakai", 0),
    ("KEB-001", "Sapu Lidi", "Buah", "Barang Kebersihan", 0),
    ("KEB-002", "Sapu Ijuk", "Buah", "Barang Kebersihan", 0),
    ("KEB-003", "Kain Pel", "Buah", "Barang Kebersihan", 0),
    ("KEB-004", "Ember Plastik", "Buah", "Barang Kebersihan", 0),
    ("KEB-005", "Cairan Pembersih Lantai", "Botol", "Barang Kebersihan", 0),
    ("KEB-006", "Cairan Pembersih Kaca", "Botol", "Barang Kebersihan", 0),
    ("KEB-007", "Pewangi Ruangan (Air Freshener)", "Botol", "Barang Kebersihan", 0),
    ("KEB-008", "Sabun Cuci Tangan", "Botol", "Barang Kebersihan", 0),
    ("KEB-009", "Kantong Plastik Sampah Besar", "Pak", "Barang Kebersihan", 0),
    ("KEB-010", "Kantong Plastik Sampah Kecil", "Pak", "Barang Kebersihan", 0),
    ("KEB-011", "Tisu Toilet", "Pak", "Barang Kebersihan", 0),
    ("KEB-012", "Pengharum Toilet", "Buah", "Barang Kebersihan", 0),
    ("KEB-013", "Sikat WC", "Buah", "Barang Kebersihan", 0),
    ("KEB-014", "Cairan Pembersih Toilet", "Botol", "Barang Kebersihan", 0),
    ("KEB-015", "Lap Pel / Lap Kain", "Buah", "Barang Kebersihan", 0),
    ("KEB-016", "Lap Meja Microfiber", "Buah", "Barang Kebersihan", 0),
    ("KEB-017", "Keset Kaki", "Buah", "Barang Kebersihan", 0),
    ("KEB-018", "Tempat Sampah Plastik", "Buah", "Barang Kebersihan", 0),
    ("KEB-019", "Cairan Disinfektan", "Botol", "Barang Kebersihan", 0),
    ("KEB-020", "Hand Sanitizer", "Botol", "Barang Kebersihan", 0),
    ("CTK-001", "Amplop Dinas Kop Surat", "Pak", "Cetakan/Formulir", 0),
    ("CTK-002", "Kertas Kop Surat", "Rim", "Cetakan/Formulir", 0),
    ("CTK-003", "Blanko Kwitansi", "Buku", "Cetakan/Formulir", 0),
    ("CTK-004", "Buku Tamu", "Buah", "Cetakan/Formulir", 0),
    ("CTK-005", "Buku Ekspedisi", "Buah", "Cetakan/Formulir", 0),
    ("CTK-006", "Stempel Dinas", "Buah", "Cetakan/Formulir", 0),
    ("CTK-007", "Tinta Stempel", "Botol", "Cetakan/Formulir", 0),
    ("CTK-008", "Bantalan Stempel", "Buah", "Cetakan/Formulir", 0),
    ("ELK-001", "Mouse Optik", "Buah", "Elektronik", 0),
    ("ELK-002", "Keyboard USB", "Buah", "Elektronik", 0),
    ("ELK-003", "Kabel USB Printer", "Buah", "Elektronik", 0),
    ("ELK-004", "Kabel HDMI", "Buah", "Elektronik", 0),
    ("ELK-005", "Stabilizer / UPS Kecil", "Buah", "Elektronik", 0),
    ("ELK-006", "Headset", "Buah", "Elektronik", 0),
    ("ELK-007", "Terminal Listrik / Stop Kontak", "Buah", "Elektronik", 0),
    ("LAIN-001", "Map Diamond", "Buah", "Lainnya", 6000),
    ("LAIN-002", "Bolpoint Elite Baliner Biru", "Buah", "Lainnya", 27500),
    ("LAIN-003", "Payung Kantor", "Buah", "Lainnya", 0),
    ("LAIN-004", "Vas Bunga", "Buah", "Lainnya", 0),
    ("LAIN-005", "Baterai Jam Dinding", "Buah", "Lainnya", 0),
    ("LAIN-006", "Gembok", "Buah", "Lainnya", 0),
)


class InventoryRepository:
    """Penyimpanan SQLite dan mesin FIFO persediaan.

    Semua mutasi memakai transaksi database. Satu surat pengeluaran dapat
    memuat banyak barang dan seluruh baris dibatalkan bila satu stok tidak
    mencukupi, sehingga dokumen dan saldo tidak pernah tersimpan sebagian.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or database_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 20000")
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS inventory_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    name TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    specification TEXT NOT NULL DEFAULT '',
                    card_number TEXT NOT NULL DEFAULT '',
                    standard_price REAL NOT NULL DEFAULT 0 CHECK(standard_price >= 0),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1))
                );
                CREATE TABLE IF NOT EXISTS inventory_receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL REFERENCES inventory_items(id),
                    document_number TEXT NOT NULL DEFAULT '',
                    book_date TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    quantity REAL NOT NULL CHECK(quantity > 0),
                    remaining_quantity REAL NOT NULL CHECK(remaining_quantity >= 0),
                    unit_price REAL NOT NULL CHECK(unit_price >= 0),
                    description TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inventory_issue_headers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_number TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    book_date TEXT NOT NULL,
                    division TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    address TEXT NOT NULL,
                    request_basis TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inventory_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    header_id INTEGER NOT NULL REFERENCES inventory_issue_headers(id) ON DELETE CASCADE,
                    item_id INTEGER NOT NULL REFERENCES inventory_items(id),
                    transaction_type TEXT NOT NULL,
                    quantity REAL NOT NULL CHECK(quantity > 0),
                    total_cost REAL NOT NULL CHECK(total_cost >= 0),
                    description TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    UNIQUE(header_id, item_id)
                );
                CREATE TABLE IF NOT EXISTS inventory_fifo_consumptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_id INTEGER NOT NULL REFERENCES inventory_issues(id) ON DELETE CASCADE,
                    receipt_id INTEGER NOT NULL REFERENCES inventory_receipts(id),
                    quantity REAL NOT NULL CHECK(quantity > 0),
                    unit_price REAL NOT NULL CHECK(unit_price >= 0),
                    subtotal REAL NOT NULL CHECK(subtotal >= 0)
                );
                CREATE TABLE IF NOT EXISTS inventory_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS ix_inventory_receipts_item_date
                    ON inventory_receipts(item_id, book_date, id);
                CREATE INDEX IF NOT EXISTS ix_inventory_issues_item_header
                    ON inventory_issues(item_id, header_id);
                CREATE INDEX IF NOT EXISTS ix_inventory_headers_date_division
                    ON inventory_issue_headers(book_date, division);
                """
            )
            db.executemany(
                "INSERT OR IGNORE INTO inventory_settings(key, value) VALUES (?, ?)",
                DEFAULT_SETTINGS.items(),
            )
            count = db.execute("SELECT COUNT(*) FROM inventory_items").fetchone()[0]
            if not count:
                db.executemany(
                    """INSERT INTO inventory_items
                       (code, name, unit, category, standard_price, active)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                    DEFAULT_ITEMS,
                )

    @staticmethod
    def _clean(value: object) -> str:
        return " ".join(str(value or "").split())

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _item(row: sqlite3.Row) -> InventoryItem:
        return InventoryItem(
            row["id"], row["code"], row["name"], row["unit"],
            row["category"], row["specification"], row["card_number"],
            float(row["standard_price"]), bool(row["active"]),
        )

    def items(self, *, active_only: bool = False, search: str = "") -> list[InventoryItem]:
        clauses: list[str] = []
        params: list[object] = []
        if active_only:
            clauses.append("active = 1")
        if search.strip():
            clauses.append("(code LIKE ? OR name LIKE ? OR category LIKE ?)")
            value = f"%{search.strip()}%"
            params.extend((value, value, value))
        query = "SELECT * FROM inventory_items"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY category, code"
        with self._connect() as db:
            return [self._item(row) for row in db.execute(query, params)]

    def item(self, item_id: int) -> InventoryItem | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,)).fetchone()
        return self._item(row) if row else None

    def save_item(self, item: InventoryItem) -> int:
        code, name, unit = map(self._clean, (item.code, item.name, item.unit))
        if not code or not name or not unit:
            raise ValueError("Kode, nama barang, dan satuan wajib diisi.")
        if item.standard_price < 0:
            raise ValueError("Harga standar tidak boleh negatif.")
        try:
            with self._connect() as db:
                if item.item_id is None:
                    cursor = db.execute(
                        """INSERT INTO inventory_items
                           (code, name, unit, category, specification, card_number,
                            standard_price, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (code, name, unit, self._clean(item.category),
                         self._clean(item.specification), self._clean(item.card_number),
                         float(item.standard_price), int(item.active)),
                    )
                    return int(cursor.lastrowid)
                db.execute(
                    """UPDATE inventory_items SET code=?, name=?, unit=?, category=?,
                       specification=?, card_number=?, standard_price=?, active=? WHERE id=?""",
                    (code, name, unit, self._clean(item.category),
                     self._clean(item.specification), self._clean(item.card_number),
                     float(item.standard_price), int(item.active), item.item_id),
                )
                return item.item_id
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Kode barang '{code}' sudah digunakan.") from exc

    def delete_item(self, item_id: int) -> None:
        with self._connect() as db:
            used = db.execute(
                """SELECT 1 FROM inventory_receipts WHERE item_id=?
                   UNION ALL SELECT 1 FROM inventory_issues WHERE item_id=? LIMIT 1""",
                (item_id, item_id),
            ).fetchone()
            if used:
                raise ValueError("Barang sudah memiliki transaksi dan tidak dapat dihapus. Nonaktifkan barang sebagai gantinya.")
            db.execute("DELETE FROM inventory_items WHERE id=?", (item_id,))

    def settings(self) -> dict[str, str]:
        with self._connect() as db:
            values = {row["key"]: row["value"] for row in db.execute("SELECT key, value FROM inventory_settings")}
        return {**DEFAULT_SETTINGS, **values}

    def save_settings(self, values: dict[str, str]) -> None:
        allowed = set(DEFAULT_SETTINGS)
        rows = [(key, str(value).strip()) for key, value in values.items() if key in allowed]
        with self._connect() as db:
            db.executemany(
                """INSERT INTO inventory_settings(key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                rows,
            )

    @staticmethod
    def _validate_book_date(db: sqlite3.Connection, item_id: int, book_date: date) -> None:
        row = db.execute(
            """SELECT MAX(book_date) AS last_date FROM (
                   SELECT book_date FROM inventory_receipts WHERE item_id=?
                   UNION ALL
                   SELECT h.book_date FROM inventory_issues i
                   JOIN inventory_issue_headers h ON h.id=i.header_id WHERE i.item_id=?
               )""",
            (item_id, item_id),
        ).fetchone()
        if row and row["last_date"] and book_date.isoformat() < row["last_date"]:
            raise ValueError(
                "Tanggal buku tidak boleh lebih awal dari transaksi terakhir barang "
                f"({date.fromisoformat(row['last_date']).strftime('%d/%m/%Y')})."
            )

    def record_receipt(
        self, *, item_id: int, document_number: str, book_date: date,
        transaction_type: str, quantity: float, unit_price: float,
        description: str = "", note: str = "",
    ) -> int:
        if quantity <= 0:
            raise ValueError("Jumlah barang masuk harus lebih dari nol.")
        if unit_price < 0:
            raise ValueError("Harga satuan tidak boleh negatif.")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._validate_book_date(db, item_id, book_date)
            cursor = db.execute(
                """INSERT INTO inventory_receipts
                   (item_id, document_number, book_date, transaction_type, quantity,
                    remaining_quantity, unit_price, description, note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_id, self._clean(document_number), book_date.isoformat(),
                 self._clean(transaction_type), float(quantity), float(quantity),
                 float(unit_price), self._clean(description), self._clean(note), self._timestamp()),
            )
            if unit_price:
                db.execute("UPDATE inventory_items SET standard_price=? WHERE id=?", (float(unit_price), item_id))
            return int(cursor.lastrowid)

    def create_issue(
        self, *, document_number: str, book_date: date, division: str,
        sender: str, recipient: str, address: str, request_basis: str,
        transaction_type: str, lines: Iterable[IssueLine], note: str = "",
        created_by: str = "",
    ) -> int:
        number = self._clean(document_number)
        if not number:
            raise ValueError("Nomor Surat Perintah wajib diisi.")
        if division not in DIVISIONS:
            raise ValueError("Pilih bagian tujuan/pemakai barang.")
        if not self._clean(sender) or not self._clean(recipient) or not self._clean(address):
            raise ValueError("Kolom Dari, Kepada, dan Alamat wajib diisi.")
        prepared = list(lines)
        if not prepared:
            raise ValueError("Tambahkan minimal satu barang yang akan dikeluarkan.")
        if any(line.quantity <= 0 for line in prepared):
            raise ValueError("Seluruh jumlah barang keluar harus lebih dari nol.")
        if len({line.item_id for line in prepared}) != len(prepared):
            raise ValueError("Barang yang sama tidak boleh ditambahkan dua kali dalam satu surat.")
        timestamp = self._timestamp()
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                for line in prepared:
                    self._validate_book_date(db, line.item_id, book_date)
                    available = db.execute(
                        "SELECT COALESCE(SUM(remaining_quantity), 0) FROM inventory_receipts WHERE item_id=?",
                        (line.item_id,),
                    ).fetchone()[0]
                    if float(available) + 1e-9 < line.quantity:
                        item = db.execute("SELECT name, unit FROM inventory_items WHERE id=?", (line.item_id,)).fetchone()
                        label = item["name"] if item else f"ID {line.item_id}"
                        unit = item["unit"] if item else ""
                        raise ValueError(
                            f"Stok {label} tidak mencukupi. Tersedia {_quantity(available)} {unit}, "
                            f"diminta {_quantity(line.quantity)} {unit}."
                        )
                header = db.execute(
                    """INSERT INTO inventory_issue_headers
                       (document_number, book_date, division, sender, recipient, address,
                        request_basis, note, created_by, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (number, book_date.isoformat(), division, self._clean(sender),
                     self._clean(recipient), self._clean(address), self._clean(request_basis),
                     self._clean(note), self._clean(created_by), timestamp),
                )
                header_id = int(header.lastrowid)
                for line in prepared:
                    batches = db.execute(
                        """SELECT id, remaining_quantity, unit_price FROM inventory_receipts
                           WHERE item_id=? AND remaining_quantity > 0
                           ORDER BY book_date, id""",
                        (line.item_id,),
                    ).fetchall()
                    remaining = float(line.quantity)
                    consumptions: list[tuple[int, float, float, float]] = []
                    total_cost = 0.0
                    for batch in batches:
                        if remaining <= 1e-9:
                            break
                        taken = min(float(batch["remaining_quantity"]), remaining)
                        subtotal = taken * float(batch["unit_price"])
                        db.execute(
                            "UPDATE inventory_receipts SET remaining_quantity=remaining_quantity-? WHERE id=?",
                            (taken, batch["id"]),
                        )
                        consumptions.append((int(batch["id"]), taken, float(batch["unit_price"]), subtotal))
                        total_cost += subtotal
                        remaining -= taken
                    issue = db.execute(
                        """INSERT INTO inventory_issues
                           (header_id, item_id, transaction_type, quantity, total_cost,
                            description, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (header_id, line.item_id, self._clean(transaction_type), float(line.quantity),
                         total_cost, f"Disalurkan ke {division}", self._clean(line.note), timestamp),
                    )
                    issue_id = int(issue.lastrowid)
                    db.executemany(
                        """INSERT INTO inventory_fifo_consumptions
                           (issue_id, receipt_id, quantity, unit_price, subtotal)
                           VALUES (?, ?, ?, ?, ?)""",
                        [(issue_id, *entry) for entry in consumptions],
                    )
                return header_id
        except sqlite3.IntegrityError as exc:
            if "document_number" in str(exc).lower() or "unique" in str(exc).lower():
                raise ValueError(f"Nomor Surat Perintah '{number}' sudah digunakan.") from exc
            raise

    def stock_summary(self, *, include_zero: bool = True) -> list[StockSummary]:
        query = """
            SELECT i.id, i.code, i.name, i.unit, i.category,
                   COALESCE(SUM(r.remaining_quantity), 0) AS quantity,
                   COALESCE(SUM(r.remaining_quantity * r.unit_price), 0) AS value
            FROM inventory_items i
            LEFT JOIN inventory_receipts r ON r.item_id=i.id AND r.remaining_quantity > 0
            WHERE i.active=1
            GROUP BY i.id ORDER BY i.category, i.code
        """
        with self._connect() as db:
            rows = [
                StockSummary(row["id"], row["code"], row["name"], row["unit"],
                             row["category"], float(row["quantity"]), float(row["value"]))
                for row in db.execute(query)
            ]
        return rows if include_zero else [row for row in rows if abs(row.quantity) > 1e-9]

    def stock_for_item(self, item_id: int) -> StockSummary | None:
        return next((row for row in self.stock_summary() if row.item_id == item_id), None)

    def card_rows(
        self, item_id: int, start: date | None = None, end: date | None = None,
    ) -> list[CardRow]:
        with self._connect() as db:
            incoming = db.execute(
                """SELECT book_date, created_at, document_number, transaction_type,
                          quantity, unit_price, description, note
                   FROM inventory_receipts WHERE item_id=?""",
                (item_id,),
            ).fetchall()
            outgoing = db.execute(
                """SELECT h.book_date, i.created_at, h.document_number, i.transaction_type,
                          i.quantity, i.total_cost, i.description, i.note
                   FROM inventory_issues i JOIN inventory_issue_headers h ON h.id=i.header_id
                   WHERE i.item_id=?""",
                (item_id,),
            ).fetchall()
        events: list[tuple[str, str, bool, sqlite3.Row]] = [
            (row["book_date"], row["created_at"], True, row) for row in incoming
        ] + [
            (row["book_date"], row["created_at"], False, row) for row in outgoing
        ]
        events.sort(key=lambda value: (value[0], value[1], not value[2]))
        balance_quantity = 0.0
        balance_value = 0.0
        result: list[CardRow] = []
        opening_added = False
        for date_text, _created, is_incoming, row in events:
            event_date = date.fromisoformat(date_text)
            quantity = float(row["quantity"])
            value = quantity * float(row["unit_price"]) if is_incoming else float(row["total_cost"])
            if start and event_date < start:
                balance_quantity += quantity if is_incoming else -quantity
                balance_value += value if is_incoming else -value
                continue
            if end and event_date > end:
                continue
            if start and not opening_added and (balance_quantity or balance_value):
                result.append(CardRow(
                    start, "-", "Saldo awal periode", balance_quantity, 0,
                    balance_quantity, balance_value / balance_quantity if balance_quantity else 0,
                    balance_value, 0, balance_value,
                ))
                opening_added = True
            balance_quantity += quantity if is_incoming else -quantity
            balance_value += value if is_incoming else -value
            result.append(CardRow(
                event_date,
                row["document_number"] or "-",
                row["description"] or row["transaction_type"],
                quantity if is_incoming else 0.0,
                0.0 if is_incoming else quantity,
                balance_quantity,
                float(row["unit_price"]) if is_incoming else (value / quantity if quantity else 0.0),
                value if is_incoming else 0.0,
                0.0 if is_incoming else value,
                balance_value,
                row["note"] or "",
            ))
        if start and not opening_added and not result and (balance_quantity or balance_value):
            result.append(CardRow(
                start, "-", "Saldo awal periode", balance_quantity, 0,
                balance_quantity, balance_value / balance_quantity if balance_quantity else 0,
                balance_value, 0, balance_value,
            ))
        return result

    def mutation_rows(self, as_of: date) -> list[MutationRow]:
        start = date(as_of.year, 1, 1).isoformat()
        end = as_of.isoformat()
        query = """
            SELECT i.*,
              COALESCE((SELECT SUM(quantity) FROM inventory_receipts r WHERE r.item_id=i.id AND r.book_date < ?),0)
              - COALESCE((SELECT SUM(x.quantity) FROM inventory_issues x JOIN inventory_issue_headers h ON h.id=x.header_id WHERE x.item_id=i.id AND h.book_date < ?),0) opening_qty,
              COALESCE((SELECT SUM(quantity*unit_price) FROM inventory_receipts r WHERE r.item_id=i.id AND r.book_date < ?),0)
              - COALESCE((SELECT SUM(x.total_cost) FROM inventory_issues x JOIN inventory_issue_headers h ON h.id=x.header_id WHERE x.item_id=i.id AND h.book_date < ?),0) opening_value,
              COALESCE((SELECT SUM(quantity) FROM inventory_receipts r WHERE r.item_id=i.id AND r.book_date BETWEEN ? AND ?),0) qty_in,
              COALESCE((SELECT SUM(x.quantity) FROM inventory_issues x JOIN inventory_issue_headers h ON h.id=x.header_id WHERE x.item_id=i.id AND h.book_date BETWEEN ? AND ?),0) qty_out,
              COALESCE((SELECT SUM(quantity*unit_price) FROM inventory_receipts r WHERE r.item_id=i.id AND r.book_date <= ?),0)
              - COALESCE((SELECT SUM(x.total_cost) FROM inventory_issues x JOIN inventory_issue_headers h ON h.id=x.header_id WHERE x.item_id=i.id AND h.book_date <= ?),0) closing_value
            FROM inventory_items i ORDER BY i.category, i.code
        """
        params = (start, start, start, start, start, end, start, end, end, end)
        result: list[MutationRow] = []
        with self._connect() as db:
            for row in db.execute(query, params):
                opening_qty = float(row["opening_qty"])
                opening_value = float(row["opening_value"])
                qty_in = float(row["qty_in"])
                qty_out = float(row["qty_out"])
                closing_qty = opening_qty + qty_in - qty_out
                closing_value = float(row["closing_value"])
                if not any(abs(value) > 1e-9 for value in (opening_qty, opening_value, qty_in, qty_out, closing_qty, closing_value)):
                    continue
                result.append(MutationRow(
                    row["id"], row["code"], row["name"], row["unit"], row["category"],
                    opening_qty, opening_value / opening_qty if opening_qty else 0.0,
                    opening_value, qty_in, qty_out, closing_qty,
                    closing_value / closing_qty if closing_qty else 0.0, closing_value,
                ))
        return result

    def outgoing_rows(self, start: date, end: date, division: str = "") -> list[OutgoingRow]:
        params: list[object] = [start.isoformat(), end.isoformat()]
        division_clause = ""
        if division:
            division_clause = " AND h.division=?"
            params.append(division)
        query = f"""
            SELECT h.id header_id, h.book_date, h.document_number, h.division,
                   b.code, b.name, b.unit, i.quantity, i.total_cost,
                   i.description, i.note
            FROM inventory_issue_headers h
            JOIN inventory_issues i ON i.header_id=h.id
            JOIN inventory_items b ON b.id=i.item_id
            WHERE h.book_date BETWEEN ? AND ? {division_clause}
            ORDER BY h.book_date, h.document_number, b.name
        """
        with self._connect() as db:
            return [
                OutgoingRow(
                    row["header_id"], date.fromisoformat(row["book_date"]),
                    row["document_number"], row["division"], row["code"], row["name"],
                    row["unit"], float(row["quantity"]),
                    float(row["total_cost"]) / float(row["quantity"]),
                    float(row["total_cost"]), row["description"], row["note"],
                )
                for row in db.execute(query, params)
            ]

    def issue_headers(self) -> list[dict[str, object]]:
        query = """
            SELECT h.*, COUNT(i.id) line_count, COALESCE(SUM(i.total_cost),0) total_cost
            FROM inventory_issue_headers h LEFT JOIN inventory_issues i ON i.header_id=h.id
            GROUP BY h.id ORDER BY h.book_date DESC, h.id DESC
        """
        with self._connect() as db:
            return [dict(row) for row in db.execute(query)]

    def issue_document(self, header_id: int) -> dict[str, object]:
        with self._connect() as db:
            header = db.execute("SELECT * FROM inventory_issue_headers WHERE id=?", (header_id,)).fetchone()
            if not header:
                raise ValueError("Surat Perintah tidak ditemukan.")
            lines = db.execute(
                """SELECT i.*, b.code, b.name, b.unit,
                          CASE WHEN i.quantity>0 THEN i.total_cost/i.quantity ELSE 0 END unit_price
                   FROM inventory_issues i JOIN inventory_items b ON b.id=i.item_id
                   WHERE i.header_id=? ORDER BY i.id""",
                (header_id,),
            ).fetchall()
        return {"header": dict(header), "lines": [dict(row) for row in lines]}

    def recent_receipts(self, limit: int = 100) -> list[dict[str, object]]:
        query = """
            SELECT r.*, b.code, b.name, b.unit FROM inventory_receipts r
            JOIN inventory_items b ON b.id=r.item_id
            ORDER BY r.book_date DESC, r.id DESC LIMIT ?
        """
        with self._connect() as db:
            return [dict(row) for row in db.execute(query, (limit,))]

    def dashboard_stats(self) -> dict[str, float]:
        with self._connect() as db:
            items = db.execute("SELECT COUNT(*) FROM inventory_items WHERE active=1").fetchone()[0]
            low = db.execute(
                """SELECT COUNT(*) FROM (
                       SELECT i.id, COALESCE(SUM(r.remaining_quantity),0) qty
                       FROM inventory_items i LEFT JOIN inventory_receipts r
                       ON r.item_id=i.id AND r.remaining_quantity>0
                       WHERE i.active=1 GROUP BY i.id HAVING qty <= 5
                   )"""
            ).fetchone()[0]
            issues = db.execute("SELECT COUNT(*) FROM inventory_issue_headers").fetchone()[0]
            value = db.execute(
                "SELECT COALESCE(SUM(remaining_quantity*unit_price),0) FROM inventory_receipts"
            ).fetchone()[0]
        return {"items": items, "low_stock": low, "issues": issues, "value": float(value)}


def _quantity(value: object) -> str:
    number = float(value or 0)
    return f"{number:,.2f}".rstrip("0").rstrip(".").replace(",", "_").replace(".", ",").replace("_", ".")
