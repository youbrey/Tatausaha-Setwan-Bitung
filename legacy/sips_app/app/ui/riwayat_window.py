"""
Panel "Riwayat Surat": ditampilkan LANGSUNG di area konten utama
(menggantikan middle_frame/right_frame/preview_frame lewat
main_window.show_riwayat_surat()), persis seperti panel "Data Perjalanan
Dinas" dkk -- BUKAN jendela terpisah. Menampilkan riwayat SEMUA surat yang
pernah dibuat, dipisah jadi 2 tabel:

1. Surat Perjalanan Dinas -- Nama Surat, Tanggal Surat, Nomor Surat,
   Pelaksana Tugas, Tanggal Dibuat, Dibuat Oleh, + tombol Edit.
2. Surat Undangan Rapat   -- Tanggal Surat, Nomor Surat,
   Nama Kegiatan/Isi Surat, Akun Pembuat, Tanggal Pembuatan, + tombol Edit.

Masing-masing tabel punya kotak pencarian di atasnya yang memfilter baris
secara realtime setelah pengguna mengetik minimal 4 karakter (di bawah itu,
seluruh data ditampilkan lagi).

Karena Tkinter/ttk tidak mendukung tombol per-baris di dalam Treeview,
alur "Edit" di sini memakai pola pilih-baris lalu klik tombol "Edit Surat
Terpilih" (atau dobel klik baris) -- setara secara fungsional dengan tombol
edit per baris di tabel web, hanya beda cara memicunya. Mengklik Edit akan
otomatis berpindah panel kembali ke form terkait (lewat
app.load_riwayat_perjalanan / app.load_riwayat_undangan).
"""
import tkinter as tk
from tkinter import ttk, messagebox

import customtkinter as ctk

from app.config.theme import (
    COLOR_BORDER,
    COLOR_CARD_BG,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_TEXT_BODY,
    COLOR_TEXT_DARK,
    FONT_FAMILY,
    font as themed_font,
)


class RiwayatSuratView(ctk.CTkFrame):
    """Panel Riwayat Surat yang ditampilkan LANGSUNG di area konten utama
    (menggantikan middle_frame/right_frame/preview_frame), persis seperti
    panel "Data Perjalanan Dinas" dkk -- bukan jendela terpisah."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        self._build_ui()
        self.refresh_data()

    # ------------------------------------------------------------------
    # BANGUN UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = ctk.CTkScrollableFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=18, pady=18)

        lbl_title = ctk.CTkLabel(
            outer, text="📜 Riwayat Surat", font=themed_font(20, "bold"),
            text_color=COLOR_TEXT_DARK,
        )
        lbl_title.pack(anchor="w", pady=(0, 4))
        lbl_sub = ctk.CTkLabel(
            outer,
            text="Cari dan buka kembali surat yang pernah dibuat sebelumnya.",
            font=themed_font(12), text_color=COLOR_TEXT_BODY,
        )
        lbl_sub.pack(anchor="w", pady=(0, 16))

        (self.search_perjalanan, self.tree_perjalanan,
         self.lbl_info_perjalanan) = self._build_table_card(
            outer, "✈️  Surat Perjalanan Dinas",
            columns=[
                ("nama_surat", "Nama Surat", 230),
                ("tanggal_surat", "Tanggal Surat", 110),
                ("nomor_surat", "Nomor Surat", 150),
                ("pelaksana", "Pelaksana Tugas", 210),
                ("tanggal_dibuat", "Tanggal Dibuat", 130),
                ("dibuat_oleh", "Dibuat Oleh", 120),
            ],
            on_search=self._on_search_perjalanan,
            on_edit=self._edit_perjalanan,
        )

        (self.search_undangan, self.tree_undangan,
         self.lbl_info_undangan) = self._build_table_card(
            outer, "📨  Surat Undangan Rapat",
            columns=[
                ("tanggal_surat", "Tanggal Surat", 110),
                ("nomor_surat", "Nomor Surat", 150),
                ("isi_surat", "Nama Kegiatan / Isi Surat", 280),
                ("dibuat_oleh", "Akun Pembuat", 140),
                ("tanggal_dibuat", "Tanggal Pembuatan", 140),
            ],
            on_search=self._on_search_undangan,
            on_edit=self._edit_undangan,
        )

    def _build_table_card(self, parent, title, columns, on_search, on_edit):
        card = ctk.CTkFrame(
            parent, fg_color=COLOR_CARD_BG, corner_radius=10,
            border_width=1, border_color=COLOR_BORDER,
        )
        card.pack(fill="both", expand=True, pady=(0, 20))

        header = ctk.CTkLabel(
            card, text=title, font=themed_font(15, "bold"),
            text_color=COLOR_TEXT_DARK,
        )
        header.pack(anchor="w", padx=18, pady=(16, 8))

        search_row = ctk.CTkFrame(card, fg_color="transparent")
        search_row.pack(fill="x", padx=18, pady=(0, 10))
        search_entry = ctk.CTkEntry(
            search_row, placeholder_text="🔎 Ketik minimal 4 karakter untuk mencari...",
            font=themed_font(12), height=34,
        )
        search_entry.pack(side="left", fill="x", expand=True)
        search_entry.bind("<KeyRelease>", lambda e: on_search(search_entry.get().strip()))

        btn_edit = ctk.CTkButton(
            search_row, text="✏️ Edit Surat Terpilih", width=180, height=34,
            font=themed_font(12), fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
            command=on_edit,
        )
        btn_edit.pack(side="left", padx=(10, 0))

        table_frame = ctk.CTkFrame(card, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=18, pady=(0, 6))

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Riwayat.Treeview", rowheight=30, font=(FONT_FAMILY, 10),
            background="#FFFFFF", fieldbackground="#FFFFFF", borderwidth=0,
        )
        style.configure("Riwayat.Treeview.Heading", font=(FONT_FAMILY, 10, "bold"))
        style.map("Riwayat.Treeview", background=[("selected", COLOR_PRIMARY)],
                  foreground=[("selected", "#FFFFFF")])

        col_ids = [c[0] for c in columns]
        tree = ttk.Treeview(
            table_frame, columns=col_ids, show="headings",
            style="Riwayat.Treeview", height=8, selectmode="browse",
        )
        for cid, label, width in columns:
            tree.heading(cid, text=label)
            tree.column(cid, width=width, anchor="w")
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        tree.bind("<Double-1>", lambda e: on_edit())

        info_lbl = ctk.CTkLabel(
            card, text="", font=themed_font(11), text_color=COLOR_TEXT_BODY,
        )
        info_lbl.pack(anchor="w", padx=18, pady=(6, 14))

        return search_entry, tree, info_lbl

    # ------------------------------------------------------------------
    # MUAT / RENDER DATA
    # ------------------------------------------------------------------
    def refresh_data(self):
        """Ambil ulang data riwayat terbaru dari app (dipanggil saat jendela
        dibuka, dan setiap kali ada surat baru yang dibuat/diedit)."""
        self._all_perjalanan = self.app.history_data.get("perjalanan_dinas", {})
        self._all_undangan = self.app.history_data.get("undangan_rapat", {})

        q1 = self.search_perjalanan.get().strip()
        self._on_search_perjalanan(q1) if q1 else self._render_perjalanan(self._all_perjalanan)

        q2 = self.search_undangan.get().strip()
        self._on_search_undangan(q2) if q2 else self._render_undangan(self._all_undangan)

    def _render_perjalanan(self, data_dict):
        self.tree_perjalanan.delete(*self.tree_perjalanan.get_children())
        rows = sorted(data_dict.items(), key=lambda kv: kv[1].get("tanggal_dibuat", ""), reverse=True)
        for nomor, d in rows:
            self.tree_perjalanan.insert("", "end", iid=nomor, values=(
                d.get("nama_surat", "-"),
                d.get("tanggal_surat", "-"),
                d.get("nomor_surat", nomor),
                d.get("pelaksana_display", "-"),
                d.get("tanggal_dibuat", "-"),
                d.get("dibuat_oleh", "-"),
            ))
        self.lbl_info_perjalanan.configure(
            text=f"Menampilkan {len(rows)} dari {len(self._all_perjalanan)} surat perjalanan dinas"
        )

    def _render_undangan(self, data_dict):
        self.tree_undangan.delete(*self.tree_undangan.get_children())
        rows = sorted(data_dict.items(), key=lambda kv: kv[1].get("tanggal_dibuat", ""), reverse=True)
        for key, d in rows:
            isi_singkat = (d.get("isi_surat", "") or "-")
            if len(isi_singkat) > 70:
                isi_singkat = isi_singkat[:67] + "..."
            self.tree_undangan.insert("", "end", iid=key, values=(
                d.get("tanggal_surat", "-"),
                d.get("nomor_surat", "-"),
                isi_singkat,
                d.get("dibuat_oleh", "-"),
                d.get("tanggal_dibuat", "-"),
            ))
        self.lbl_info_undangan.configure(
            text=f"Menampilkan {len(rows)} dari {len(self._all_undangan)} surat undangan rapat"
        )

    # ------------------------------------------------------------------
    # PENCARIAN REALTIME (minimal 4 karakter)
    # ------------------------------------------------------------------
    def _on_search_perjalanan(self, query):
        if len(query) < 4:
            self._render_perjalanan(self._all_perjalanan)
            return
        q = query.lower()
        filtered = {
            k: v for k, v in self._all_perjalanan.items()
            if q in str(v.get("nama_surat", "")).lower()
            or q in str(v.get("nomor_surat", k)).lower()
            or q in str(v.get("pelaksana_display", "")).lower()
            or q in str(v.get("dibuat_oleh", "")).lower()
            or q in str(v.get("tanggal_surat", "")).lower()
        }
        self._render_perjalanan(filtered)

    def _on_search_undangan(self, query):
        if len(query) < 4:
            self._render_undangan(self._all_undangan)
            return
        q = query.lower()
        filtered = {
            k: v for k, v in self._all_undangan.items()
            if q in str(v.get("isi_surat", "")).lower()
            or q in str(v.get("nomor_surat", "")).lower()
            or q in str(v.get("dibuat_oleh", "")).lower()
            or q in str(v.get("tanggal_surat", "")).lower()
        }
        self._render_undangan(filtered)

    # ------------------------------------------------------------------
    # AKSI EDIT (pilih baris -> muat ulang ke formulir induk)
    # ------------------------------------------------------------------
    def _edit_perjalanan(self):
        sel = self.tree_perjalanan.selection()
        if not sel:
            messagebox.showinfo(
                "Pilih Surat",
                "Pilih dulu salah satu baris surat perjalanan dinas yang ingin di-edit.",
                parent=self.app,
            )
            return
        self.app.load_riwayat_perjalanan(sel[0])

    def _edit_undangan(self):
        sel = self.tree_undangan.selection()
        if not sel:
            messagebox.showinfo(
                "Pilih Surat",
                "Pilih dulu salah satu baris surat undangan yang ingin di-edit.",
                parent=self.app,
            )
            return
        self.app.load_riwayat_undangan(sel[0])
