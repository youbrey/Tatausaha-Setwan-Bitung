"""
Panel "Dashboard": ringkasan statistik seluruh surat yang pernah dibuat,
tampil sebagai kartu angka (KPI) + grafik, meniru gaya panel ringkasan pada
template Adminator (kartu putih bersih, aksen warna ungu-indigo, angka besar
di kiri-atas, grafik batang horizontal berlabel angka).

Panel ini ditampilkan LANGSUNG di area konten utama (menggantikan
middle_frame/right_frame/preview_frame lewat main_window.show_dashboard()),
persis seperti panel "Data Perjalanan Dinas" dkk -- BUKAN jendela terpisah.

Sumber data: app.core.dashboard_stats.compute_dashboard_stats(), yang murni
membaca app.history_data (file sips_history.json) -- data yang sama dipakai
oleh panel Riwayat Surat. Panel ini hanya membaca (read-only), tidak
mengubah data apa pun.
"""
import tkinter as tk

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from app.config.theme import (
    COLOR_BORDER,
    COLOR_CARD_BG,
    COLOR_DANGER,
    COLOR_DANGER_SOFT,
    COLOR_INFO,
    COLOR_INFO_SOFT,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_PRIMARY_SOFT,
    COLOR_SUCCESS,
    COLOR_SUCCESS_SOFT,
    COLOR_TEXT_BODY,
    COLOR_TEXT_DARK,
    COLOR_TEXT_MUTED,
    COLOR_WARNING,
    COLOR_WARNING_SOFT,
    FONT_FAMILY,
    font as themed_font,
)
from app.core.dashboard_stats import compute_dashboard_stats

# Palet berurutan dipakai utk batang grafik, supaya tiap kartu grafik
# punya nuansa warna sendiri tapi tetap dari keluarga warna Adminator.
_CHART_COLORS = [COLOR_PRIMARY, "#9C99EF", COLOR_INFO, "#5ED3C7", COLOR_WARNING, "#FF9F43", COLOR_DANGER, "#C084FC"]


class DashboardView(ctk.CTkFrame):
    """Panel Dashboard yang ditampilkan LANGSUNG di area konten utama
    (menggantikan middle_frame/right_frame/preview_frame), persis seperti
    panel "Data Perjalanan Dinas" dkk -- bukan jendela terpisah."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        self._chart_canvases = []  # simpan referensi supaya tidak digarbage-collect
        self._build_ui()
        self.refresh_data()

    # ------------------------------------------------------------------
    # BANGUN UI (kerangka statis; angka & grafik diisi oleh refresh_data)
    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = ctk.CTkScrollableFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=18, pady=18)
        self._outer = outer

        header_row = ctk.CTkFrame(outer, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 16))
        header_row.grid_columnconfigure(0, weight=1)

        title_box = ctk.CTkFrame(header_row, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            title_box, text="📊 Dashboard", font=themed_font(20, "bold"),
            text_color=COLOR_TEXT_DARK,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_box,
            text="Ringkasan jumlah surat, tujuan tersering, dan pelaksana tugas tersering.",
            font=themed_font(12), text_color=COLOR_TEXT_BODY,
        ).pack(anchor="w", pady=(2, 0))

        self.btn_refresh = ctk.CTkButton(
            header_row, text="🔄 Refresh", width=110, height=34,
            font=themed_font(12, "bold"), fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER, command=self.refresh_data,
        )
        self.btn_refresh.grid(row=0, column=1, sticky="e")

        # -- Baris kartu KPI (4 kolom sama lebar) --------------------------
        self.kpi_row = ctk.CTkFrame(outer, fg_color="transparent")
        self.kpi_row.pack(fill="x", pady=(0, 18))
        for c in range(4):
            self.kpi_row.grid_columnconfigure(c, weight=1, uniform="kpi")

        self._kpi_value_labels = {}
        kpi_defs = [
            ("total_surat_tugas", "📄", "Total Surat Tugas", COLOR_PRIMARY, COLOR_PRIMARY_SOFT),
            ("total_spd", "🧳", "Total Surat Perjalanan Dinas (SPD)", COLOR_SUCCESS, COLOR_SUCCESS_SOFT),
            ("total_undangan_paripurna", "📨", "Undangan Paripurna Dibuat", COLOR_INFO, COLOR_INFO_SOFT),
            ("total_undangan_biasa", "📋", "Undangan Rapat Biasa Dibuat", COLOR_WARNING, COLOR_WARNING_SOFT),
        ]
        for i, (key, icon, label, color, soft) in enumerate(kpi_defs):
            self._build_kpi_card(self.kpi_row, col=i, key=key, icon=icon, label=label, color=color, soft_bg=soft)

        # -- Grid 2x2 kartu grafik ------------------------------------------
        self.chart_grid = ctk.CTkFrame(outer, fg_color="transparent")
        self.chart_grid.pack(fill="both", expand=True)
        self.chart_grid.grid_columnconfigure(0, weight=1, uniform="chart")
        self.chart_grid.grid_columnconfigure(1, weight=1, uniform="chart")

        self.card_kabkota = self._build_chart_card(
            self.chart_grid, row=0, col=0,
            title="🗺️  Kabupaten/Kota Tujuan Paling Sering Dikunjungi",
        )
        self.card_kategori = self._build_chart_card(
            self.chart_grid, row=0, col=1,
            title="🏷️  Kategori Pelaksana Tugas Paling Sering",
        )
        self.card_dprd = self._build_chart_card(
            self.chart_grid, row=1, col=0,
            title="🧑‍⚖️  Anggota DPRD Paling Sering Melakukan Perjalanan Dinas",
        )
        self.card_asn = self._build_chart_card(
            self.chart_grid, row=1, col=1,
            title="🧑‍💼  ASN Paling Sering Melakukan Perjalanan Dinas",
        )

    def _build_kpi_card(self, parent, col, key, icon, label, color, soft_bg):
        card = ctk.CTkFrame(
            parent, fg_color=COLOR_CARD_BG, corner_radius=10,
            border_width=1, border_color=COLOR_BORDER,
        )
        card.grid(row=0, column=col, padx=(0 if col == 0 else 8, 0), sticky="nsew")

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(16, 6))

        icon_badge = ctk.CTkLabel(
            top_row, text=icon, font=themed_font(16), width=36, height=36,
            fg_color=soft_bg, corner_radius=10, text_color=color,
        )
        icon_badge.pack(side="left")

        value_lbl = ctk.CTkLabel(
            card, text="0", font=themed_font(28, "bold"), text_color=COLOR_TEXT_DARK,
            anchor="w",
        )
        value_lbl.pack(fill="x", padx=16, pady=(0, 0), anchor="w")
        self._kpi_value_labels[key] = value_lbl

        ctk.CTkLabel(
            card, text=label, font=themed_font(12), text_color=COLOR_TEXT_BODY,
            anchor="w", wraplength=230, justify="left",
        ).pack(fill="x", padx=16, pady=(0, 16), anchor="w")

        return card

    def _build_chart_card(self, parent, row, col, title):
        card = ctk.CTkFrame(
            parent, fg_color=COLOR_CARD_BG, corner_radius=10,
            border_width=1, border_color=COLOR_BORDER,
        )
        card.grid(
            row=row, column=col, sticky="nsew",
            padx=(0 if col == 0 else 8, 0 if col == 1 else 8),
            pady=(0 if row == 0 else 14, 14 if row == 0 else 0),
        )
        parent.grid_rowconfigure(row, weight=1, minsize=340)

        ctk.CTkLabel(
            card, text=title, font=themed_font(13, "bold"), text_color=COLOR_TEXT_DARK,
            anchor="w",
        ).pack(anchor="w", padx=18, pady=(14, 4))

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        return body

    # ------------------------------------------------------------------
    # ISI DATA
    # ------------------------------------------------------------------
    def refresh_data(self):
        """Hitung ulang statistik dari app.history_data terbaru lalu gambar
        ulang seluruh kartu KPI & grafik. Dipanggil saat jendela dibuka dan
        setiap kali tombol Refresh ditekan."""
        stats = compute_dashboard_stats(self.app.history_data)

        self._kpi_value_labels["total_surat_tugas"].configure(text=f'{stats["total_surat_tugas"]:,}'.replace(",", "."))
        self._kpi_value_labels["total_spd"].configure(text=f'{stats["total_spd"]:,}'.replace(",", "."))
        self._kpi_value_labels["total_undangan_paripurna"].configure(text=f'{stats["total_undangan_paripurna"]:,}'.replace(",", "."))
        self._kpi_value_labels["total_undangan_biasa"].configure(text=f'{stats["total_undangan_biasa"]:,}'.replace(",", "."))

        self._render_barh_chart(
            self.card_kabkota, stats["top_kabkota"],
            empty_text="Belum ada data tujuan perjalanan dinas.",
            color=COLOR_PRIMARY,
        )
        self._render_barh_chart(
            self.card_kategori, stats["top_kategori"],
            empty_text="Belum ada data kategori pelaksana.",
            color=COLOR_INFO,
        )
        self._render_barh_chart(
            self.card_dprd, stats["top_dprd"],
            empty_text="Belum ada data anggota DPRD yang bertugas.",
            color=COLOR_SUCCESS,
        )
        self._render_barh_chart(
            self.card_asn, stats["top_asn"],
            empty_text="Belum ada data ASN yang bertugas.",
            color=COLOR_WARNING,
        )

    def _render_barh_chart(self, body_frame, data_pairs, empty_text, color):
        """Gambar grafik batang horizontal berlabel angka di dalam
        `body_frame`. `data_pairs` adalah list [(label, jumlah), ...]
        terurut dari yang paling sering (hasil Counter.most_common)."""
        for w in body_frame.winfo_children():
            w.destroy()

        if not data_pairs:
            ctk.CTkLabel(
                body_frame, text=empty_text, font=themed_font(12),
                text_color=COLOR_TEXT_MUTED,
            ).pack(expand=True, pady=30)
            return

        # Urutkan menaik utk barh (Matplotlib menggambar barh dari bawah
        # ke atas), supaya item #1 (paling sering) tampil PALING ATAS.
        pairs = list(reversed(data_pairs))
        labels = [p[0] if len(p[0]) <= 28 else p[0][:25] + "..." for p in pairs]
        values = [p[1] for p in pairs]

        fig = Figure(figsize=(5.2, 3.1), dpi=100)
        fig.patch.set_facecolor(COLOR_CARD_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(COLOR_CARD_BG)

        bars = ax.barh(labels, values, color=color, height=0.6, zorder=3)

        max_val = max(values) if values else 1
        ax.set_xlim(0, max_val * 1.18)
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_width() + max_val * 0.02, bar.get_y() + bar.get_height() / 2,
                f"{val:,}".replace(",", "."), va="center", ha="left",
                fontsize=9, fontfamily=FONT_FAMILY, color="#313435",
            )

        ax.tick_params(axis="y", labelsize=9, length=0)
        ax.tick_params(axis="x", labelsize=8, colors=COLOR_TEXT_MUTED)
        for lbl in ax.get_yticklabels():
            lbl.set_fontfamily(FONT_FAMILY)
        for lbl in ax.get_xticklabels():
            lbl.set_fontfamily(FONT_FAMILY)
        ax.set_xticks([])
        for spine_name in ("top", "right", "bottom", "left"):
            ax.spines[spine_name].set_visible(False)
        ax.grid(False)
        fig.tight_layout(pad=0.6)

        canvas = FigureCanvasTkAgg(fig, master=body_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._chart_canvases.append(canvas)
