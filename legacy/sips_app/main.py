"""
Entry point aplikasi SIPS.

Jalankan dengan:
    python main.py

Alur:
1. Tampilkan LoginWindow (autentikasi username/password).
2. Jika berhasil login, buka SIPSApp (window utama).
3. Tambahkan info user, tombol Kelola Akun (khusus superadmin), dan Logout
   ke sidebar window utama.
"""
from tkinter import messagebox

import customtkinter as ctk

from app.config.settings import configure_theme
from app.config.theme import (
    COLOR_DANGER,
    COLOR_DANGER_HOVER,
    COLOR_GREY_DARK,
    COLOR_GREY_DARK_HOVER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_TEXT_DARK,
    font as themed_font,
)
from app.core.auth import load_accounts
from app.ui.account_window import ManajemenAkunWindow
from app.ui.login_window import LoginWindow
from app.ui.main_window import SIPSApp


def run():
    configure_theme()

    # 1. Tampilkan Login
    login = LoginWindow()
    login.mainloop()

    if not login.logged_in:
        # User menutup jendela tanpa login
        import sys
        sys.exit(0)

    # 2. Buka aplikasi utama
    app = SIPSApp()

    # Simpan info user yang login ke app
    app._current_user = login.current_user
    app._current_role = login.current_role

    # Tampilkan nama user di sidebar dan tombol manajemen akun (khusus superadmin)
    user_info = load_accounts().get(login.current_user, {})
    nama_user = user_info.get("nama_lengkap", login.current_user)

    # Label selamat datang -- ditempel rapat tepat di atas tombol Kelola Akun/
    # Logout (baris 13), karena baris kosong "spacer" sudah diatur di
    # row=11 pada sidebar_frame (lihat main_window.setup_ui).
    welcome_lbl = ctk.CTkLabel(
        app.sidebar_frame,
        text=f"👤 {nama_user}",
        font=themed_font(10, "bold"),
        text_color=COLOR_TEXT_DARK,
        wraplength=180,
        justify="center"
    )
    welcome_lbl.grid(row=13, column=0, padx=20, pady=(0, 4), sticky="ew")

    # Tombol Manajemen Akun (khusus superadmin)
    if login.current_role == "superadmin":
        btn_kelola = ctk.CTkButton(
            app.sidebar_frame,
            text="⚙️ Kelola Akun Pengguna",
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            font=themed_font(11),
            corner_radius=6,
            height=32,
            command=lambda: ManajemenAkunWindow(app)
        )
        btn_kelola.grid(row=14, column=0, padx=20, pady=(0, 4), sticky="ew")

    # Tombol logout
    def _logout():
        if messagebox.askyesno("Logout", "Keluar dari aplikasi dan kembali ke halaman login?"):
            app.on_close()
            # Restart ke login
            import sys, os
            os.execv(sys.executable, [sys.executable] + sys.argv)

    btn_logout = ctk.CTkButton(
        app.sidebar_frame,
        text="🚪 Logout",
        fg_color=COLOR_GREY_DARK,
        hover_color=COLOR_GREY_DARK_HOVER,
        font=themed_font(11),
        corner_radius=6,
        height=32,
        command=_logout
    )
    btn_logout.grid(row=15, column=0, padx=20, pady=(0, 12), sticky="ew")

    app.mainloop()


if __name__ == "__main__":
    run()
