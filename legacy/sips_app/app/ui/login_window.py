"""
Jendela Login (gerbang masuk sebelum SIPSApp utama dibuka). Mengautentikasi
username/password terhadap data akun dari app.core.auth.

Tampilan: kartu putih dengan panel form di kiri dan panel aksen warna di
kanan ("Welcome Back"), mengikuti gaya split-card pada referensi desain,
dipadukan dengan palet warna & font tema Adminator (app/config/theme.py).
"""
import customtkinter as ctk
from tkinter import messagebox

from app.core.auth import _verify_password, load_accounts
from app.config.theme import (
    COLOR_BODY_BG,
    COLOR_BORDER,
    COLOR_CARD_BG,
    COLOR_DANGER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_SECONDARY,
    COLOR_TEXT_BODY,
    COLOR_TEXT_DARK,
    COLOR_TEXT_MUTED,
    font as themed_font,
)


class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SIPS Sekretariat DPRD Kota Bitung — Login")
        self.geometry("780x480")
        self.resizable(False, False)
        self._center_window(780, 480)
        self.logged_in = False
        self.accounts = load_accounts()
        self._build_ui()
        self.bind("<Return>", lambda e: self._do_login())

    def _center_window(self, w, h):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Background utama
        self.configure(fg_color=COLOR_BODY_BG)

        # Kartu split: kiri = form, kanan = panel aksen warna
        card = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG, corner_radius=16,
                             border_width=1, border_color=COLOR_BORDER)
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.88)
        card.grid_columnconfigure(0, weight=3)
        card.grid_columnconfigure(1, weight=2)
        card.grid_rowconfigure(0, weight=1)

        # --- Panel kiri: form login ---
        form_panel = ctk.CTkFrame(card, fg_color="transparent")
        form_panel.grid(row=0, column=0, sticky="nsew", padx=(40, 20), pady=30)

        ctk.CTkLabel(form_panel, text="Hello!", font=themed_font(28, "bold"), text_color=COLOR_TEXT_DARK, anchor="w").pack(fill="x")
        ctk.CTkLabel(form_panel, text="Masuk ke akun SIPS Anda", font=themed_font(13), text_color=COLOR_TEXT_BODY, anchor="w").pack(fill="x", pady=(0, 22))

        ctk.CTkLabel(form_panel, text="Username", anchor="w",
                     font=themed_font(12, "bold"), text_color=COLOR_TEXT_DARK).pack(fill="x")
        self.ent_username = ctk.CTkEntry(form_panel, placeholder_text="Masukkan username...",
                                         height=40, corner_radius=8,
                                         border_color=COLOR_BORDER)
        self.ent_username.pack(fill="x", pady=(4, 14))

        ctk.CTkLabel(form_panel, text="Password", anchor="w",
                     font=themed_font(12, "bold"), text_color=COLOR_TEXT_DARK).pack(fill="x")
        pwd_frame = ctk.CTkFrame(form_panel, fg_color="transparent")
        pwd_frame.pack(fill="x", pady=(4, 0))
        pwd_frame.grid_columnconfigure(0, weight=1)

        self.ent_password = ctk.CTkEntry(pwd_frame, placeholder_text="Masukkan password...",
                                          show="●", height=40, corner_radius=8,
                                          border_color=COLOR_BORDER)
        self.ent_password.grid(row=0, column=0, sticky="ew")

        self._show_pwd = False
        self.btn_toggle_pwd = ctk.CTkButton(pwd_frame, text="👁", width=42, height=40,
                                             fg_color=COLOR_BODY_BG, text_color=COLOR_TEXT_BODY,
                                             hover_color=COLOR_BORDER, corner_radius=8,
                                             command=self._toggle_password)
        self.btn_toggle_pwd.grid(row=0, column=1, padx=(6, 0))

        # Error label
        self.lbl_error = ctk.CTkLabel(form_panel, text="", text_color=COLOR_DANGER,
                                       font=themed_font(11))
        self.lbl_error.pack(fill="x", pady=(10, 0))

        # Tombol login
        self.btn_login = ctk.CTkButton(form_panel, text="SIGN IN",
                                        height=42, corner_radius=8,
                                        font=themed_font(13, "bold"),
                                        fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
                                        command=self._do_login)
        self.btn_login.pack(fill="x", pady=(18, 0))

        ctk.CTkLabel(form_panel, text="v8.0 © Sekretariat DPRD Kota Bitung",
                     font=themed_font(9), text_color=COLOR_TEXT_MUTED).pack(side="bottom", pady=(20, 0))

        # --- Panel kanan: aksen warna "Welcome Back" ---
        accent_panel = ctk.CTkFrame(card, fg_color=COLOR_PRIMARY, corner_radius=12)
        accent_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 20), pady=20)
        accent_panel.grid_propagate(False)

        ctk.CTkLabel(accent_panel, text="🏛️", font=themed_font(40)).pack(pady=(50, 6))
        ctk.CTkLabel(accent_panel, text="Welcome Back!", font=themed_font(20, "bold"), text_color="white").pack(pady=(0, 8))
        ctk.CTkLabel(
            accent_panel,
            text="Sistem Informasi Persuratan\nSekretariat DPRD Kota Bitung",
            font=themed_font(11), text_color="#EDEBFD", justify="center",
        ).pack(padx=20)

        self.ent_username.focus()

    def _toggle_password(self):
        self._show_pwd = not self._show_pwd
        self.ent_password.configure(show="" if self._show_pwd else "●")
        self.btn_toggle_pwd.configure(text="🙈" if self._show_pwd else "👁")

    def _do_login(self):
        uname = self.ent_username.get().strip().lower()
        pwd   = self.ent_password.get()

        if not uname or not pwd:
            self._shake_error("Username dan password wajib diisi.")
            return

        self.accounts = load_accounts()
        info = self.accounts.get(uname)

        if info is None:
            self._shake_error("Username tidak ditemukan.")
            return
        if not info.get("aktif", True):
            self._shake_error("Akun ini telah dinonaktifkan.")
            return
        if not _verify_password(pwd, info["hashed"], info["salt"]):
            self._shake_error("Password salah.")
            return

        # Login sukses
        self.logged_in = True
        self.current_user = uname
        self.current_role = info.get("role", "user")
        self.destroy()

    def _shake_error(self, msg: str):
        self.lbl_error.configure(text=msg)
        # Efek shake sederhana
        orig_x = self.winfo_x()
        orig_y = self.winfo_y()
        for dx in [8, -8, 6, -6, 4, -4, 0]:
            self.geometry(f"+{orig_x + dx}+{orig_y}")
            self.update()
            self.after(30)


