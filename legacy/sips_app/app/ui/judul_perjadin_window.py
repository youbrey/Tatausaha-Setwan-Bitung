"""
Panel "Judul Perjadin": ditampilkan LANGSUNG di area konten utama
(menggantikan middle_frame/right_frame/preview_frame lewat
main_window.show_judul_perjadin()), mengikuti pola panel "Riwayat Surat" /
"Dashboard" -- BUKAN jendela terpisah.

Menampilkan satu tabel ringkasan seluruh Surat Tugas & SPD yang pernah
dibuat (dari data yang sama dengan Riwayat Surat), dengan 4 kolom sesuai
permintaan:
    1. Judul Perjadin      -- diambil dari Materi/Agenda Kegiatan
    2. Kategori Pelaksana  -- mis. "Pimpinan DPRD, Anggota" / "Pelaksana ASN"
    3. Tanggal Pelaksanaan -- format ringkas "06-10 Juli 2026"
    4. Tempat Tujuan       -- daftar kota/tempat tujuan bertugas

Data disusun oleh app/data/history_repository.daftar_judul_perjadin(),
yang membaca dari file riwayat BERSAMA -- kalau mode jaringan aktif,
tabel ini otomatis berisi surat yang dibuat dari komputer mana pun.
"""
import customtkinter as ctk
from tkinter import ttk

from app.config.theme import (
    COLOR_BORDER,
    COLOR_CARD_BG,
    COLOR_PRIMARY,
    COLOR_TEXT_BODY,
    COLOR_TEXT_DARK,
    FONT_FAMILY,
    font as themed_font,
)
from app.data.history_repository import daftar_judul_perjadin


class JudulPerjadinView(ctk.CTkFrame):
    """Panel 'Judul Perjadin' -- tabel ringkasan judul/materi kegiatan
    perjalanan dinas yang sudah pernah dibuat, supaya penyusun surat bisa
    cepat mengecek judul mana yang sudah pernah dipakai sebelum membuat
    surat baru (melengkapi peringatan toast otomatis di formulir)."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._all_rows = []
        self._build_ui()
        self.refresh_data()

    def _build_ui(self):
        outer = ctk.CTkScrollableFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=18, pady=18)

        lbl_title = ctk.CTkLabel(
            outer, text="🗂️ Judul Perjadin", font=themed_font(20, "bold"),
            text_color=COLOR_TEXT_DARK,
        )
        lbl_title.pack(anchor="w", pady=(0, 4))
        lbl_sub = ctk.CTkLabel(
            outer,
            text=("Daftar judul/agenda perjalanan dinas yang sudah pernah dibuat -- "
                  "cek dulu di sini sebelum menulis judul baru supaya tidak dobel."),
            font=themed_font(12), text_color=COLOR_TEXT_BODY,
        )
        lbl_sub.pack(anchor="w", pady=(0, 16))

        card = ctk.CTkFrame(
            outer, fg_color=COLOR_CARD_BG, corner_radius=10,
            border_width=1, border_color=COLOR_BORDER,
        )
        card.pack(fill="both", expand=True, pady=(0, 20))

        search_row = ctk.CTkFrame(card, fg_color="transparent")
        search_row.pack(fill="x", padx=18, pady=(16, 10))
        self.search_entry = ctk.CTkEntry(
            search_row, placeholder_text="🔎 Ketik minimal 3 karakter untuk mencari judul/tempat...",
            font=themed_font(12), height=34,
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_search(self.search_entry.get().strip()))

        table_frame = ctk.CTkFrame(card, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=18, pady=(0, 6))

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "JudulPerjadin.Treeview", rowheight=30, font=(FONT_FAMILY, 10),
            background="#FFFFFF", fieldbackground="#FFFFFF", borderwidth=0,
        )
        style.configure("JudulPerjadin.Treeview.Heading", font=(FONT_FAMILY, 10, "bold"))
        style.map("JudulPerjadin.Treeview", background=[("selected", COLOR_PRIMARY)],
                  foreground=[("selected", "#FFFFFF")])

        columns = [
            ("judul", "Judul Perjadin (Materi/Agenda)", 340),
            ("kategori_pelaksana", "Kategori Pelaksana", 220),
            ("tanggal_pelaksanaan", "Tanggal Pelaksanaan", 170),
            ("tempat_tujuan", "Tempat Tujuan", 220),
        ]
        col_ids = [c[0] for c in columns]
        self.tree = ttk.Treeview(
            table_frame, columns=col_ids, show="headings",
            style="JudulPerjadin.Treeview", height=14, selectmode="browse",
        )
        for cid, label, width in columns:
            self.tree.heading(cid, text=label)
            self.tree.column(cid, width=width, anchor="w")
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.lbl_info = ctk.CTkLabel(card, text="", font=themed_font(11), text_color=COLOR_TEXT_BODY)
        self.lbl_info.pack(anchor="w", padx=18, pady=(6, 14))

    # ------------------------------------------------------------------
    def refresh_data(self):
        """Ambil ulang data terbaru dari riwayat (dipanggil saat panel ini
        dibuka, dan setiap kali ada surat perjalanan dinas baru disimpan --
        lihat main_window._refresh_riwayat_window_if_open)."""
        self._all_rows = daftar_judul_perjadin()
        query = self.search_entry.get().strip()
        if query:
            self._on_search(query)
        else:
            self._render(self._all_rows)

    def _render(self, rows):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            self.tree.insert("", "end", iid=str(i), values=(
                r["judul"], r["kategori_pelaksana"], r["tanggal_pelaksanaan"], r["tempat_tujuan"],
            ))
        self.lbl_info.configure(
            text=f"Menampilkan {len(rows)} dari {len(self._all_rows)} judul perjalanan dinas"
        )

    def _on_search(self, query):
        if len(query) < 3:
            self._render(self._all_rows)
            return
        q = query.lower()
        filtered = [
            r for r in self._all_rows
            if q in str(r["judul"]).lower()
            or q in str(r["tempat_tujuan"]).lower()
            or q in str(r["kategori_pelaksana"]).lower()
        ]
        self._render(filtered)
