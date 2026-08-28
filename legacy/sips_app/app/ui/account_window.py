"""
Jendela Manajemen Akun Pengguna (khusus role superadmin): tambah, ubah
peran/status aktif, reset password, dan hapus akun. Logika hashing/akses
file akun ada di app.core.auth, file ini hanya UI + validasi input.
"""
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from app.core.auth import _hash_password, load_accounts, save_accounts
from app.config.theme import COLOR_PRIMARY, font as themed_font


class ManajemenAkunWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Manajemen Akun Pengguna")
        self.geometry("700x560")
        self.resizable(False, False)
        self.grab_set()  # modal
        self.focus()

        self.accounts = load_accounts()
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Header ──────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text="👤  Manajemen Akun Pengguna SIPS",
                     font=themed_font(15, "bold"), text_color="white").pack(padx=20, pady=12)

        # ── Body ─────────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, padx=20, pady=15, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Daftar akun
        list_frame = ctk.CTkFrame(body, fg_color="#F3F4F6", corner_radius=8)
        list_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        self.scroll_accounts = ctk.CTkScrollableFrame(list_frame, fg_color="transparent")
        self.scroll_accounts.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.scroll_accounts.grid_columnconfigure((0,1,2,3), weight=1)

        # Tombol aksi
        btn_frame = ctk.CTkFrame(body, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew")
        ctk.CTkButton(btn_frame, text="➕ Tambah Akun Baru",
                      fg_color="#10B981", hover_color="#059669",
                      command=self._dialog_tambah).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="🔑 Ganti Password",
                      fg_color="#F59E0B", hover_color="#D97706",
                      command=self._dialog_ganti_password).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="🗑 Hapus Akun",
                      fg_color="#EF4444", hover_color="#DC2626",
                      command=self._hapus_akun).pack(side="left")
        ctk.CTkButton(btn_frame, text="Tutup",
                      fg_color="#64748B", hover_color="#475569",
                      command=self.destroy).pack(side="right")

    def _refresh_list(self):
        for w in self.scroll_accounts.winfo_children():
            w.destroy()

        headers = ["Username", "Nama Lengkap", "Role", "Status"]
        cols_w = [140, 220, 110, 90]
        for ci, (h, w) in enumerate(zip(headers, cols_w)):
            ctk.CTkLabel(self.scroll_accounts, text=h,
                         font=themed_font(11, "bold"),
                         width=w, anchor="w").grid(row=0, column=ci, padx=6, pady=(4, 6), sticky="w")

        self.selected_username = tk.StringVar(value="")
        self._row_frames = {}

        self.accounts = load_accounts()
        for ri, (uname, info) in enumerate(self.accounts.items(), start=1):
            role_label = "Super Admin" if info.get("role") == "superadmin" else "Pengguna"
            status_label = "✅ Aktif" if info.get("aktif", True) else "🚫 Nonaktif"
            status_color = "#10B981" if info.get("aktif", True) else "#EF4444"

            row_bg = "#FFFFFF" if ri % 2 == 0 else "#EEF2FF"
            row_f = ctk.CTkFrame(self.scroll_accounts, fg_color=row_bg, corner_radius=4)
            row_f.grid(row=ri, column=0, columnspan=4, sticky="ew", padx=2, pady=1)
            row_f.grid_columnconfigure((0,1,2,3), weight=1)

            rb = ctk.CTkRadioButton(row_f, text=uname,
                                    variable=self.selected_username, value=uname,
                                    font=themed_font(11), width=140)
            rb.grid(row=0, column=0, padx=8, pady=6, sticky="w")
            ctk.CTkLabel(row_f, text=info.get("nama_lengkap", "-"),
                         font=themed_font(11), width=220, anchor="w").grid(row=0, column=1, padx=4, sticky="w")
            ctk.CTkLabel(row_f, text=role_label,
                         font=themed_font(11), width=110, anchor="w").grid(row=0, column=2, padx=4, sticky="w")
            ctk.CTkLabel(row_f, text=status_label, text_color=status_color,
                         font=themed_font(11, "bold"), width=90, anchor="w").grid(row=0, column=3, padx=4, sticky="w")

            self._row_frames[uname] = row_f

    # ── Dialog Tambah Akun ───────────────────────────────────────────────────
    def _dialog_tambah(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Tambah Akun Baru")
        dlg.geometry("420x380")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.focus()

        ctk.CTkLabel(dlg, text="Tambah Akun Pengguna Baru",
                     font=themed_font(13, "bold")).pack(pady=(18, 6))

        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="x", padx=30)

        fields = {}
        for label, key, show in [
            ("Username", "username", ""),
            ("Nama Lengkap", "nama", ""),
            ("Password", "password", "●"),
            ("Konfirmasi Password", "konfirmasi", "●"),
        ]:
            ctk.CTkLabel(form, text=label, anchor="w",
                         font=themed_font(11, "bold")).pack(fill="x", pady=(8, 1))
            ent = ctk.CTkEntry(form, show=show)
            ent.pack(fill="x")
            fields[key] = ent

        role_var = tk.StringVar(value="user")
        role_frame = ctk.CTkFrame(form, fg_color="transparent")
        role_frame.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(role_frame, text="Role:", font=themed_font(11, "bold")).pack(side="left")
        ctk.CTkRadioButton(role_frame, text="Pengguna", variable=role_var, value="user").pack(side="left", padx=10)
        ctk.CTkRadioButton(role_frame, text="Super Admin", variable=role_var, value="superadmin").pack(side="left")

        lbl_err = ctk.CTkLabel(dlg, text="", text_color="#EF4444", font=themed_font(11))
        lbl_err.pack(pady=(8, 0))

        def _simpan():
            uname  = fields["username"].get().strip().lower()
            nama   = fields["nama"].get().strip()
            pwd    = fields["password"].get()
            konfirm = fields["konfirmasi"].get()

            if not uname or not nama or not pwd:
                lbl_err.configure(text="Semua field wajib diisi."); return
            if uname in self.accounts:
                lbl_err.configure(text="Username sudah terdaftar."); return
            if pwd != konfirm:
                lbl_err.configure(text="Password tidak cocok."); return
            if len(pwd) < 6:
                lbl_err.configure(text="Password minimal 6 karakter."); return

            hashed, salt = _hash_password(pwd)
            self.accounts[uname] = {
                "hashed": hashed, "salt": salt,
                "role": role_var.get(),
                "nama_lengkap": nama,
                "aktif": True,
            }
            save_accounts(self.accounts)
            self._refresh_list()
            dlg.destroy()
            messagebox.showinfo("Berhasil", f"Akun '{uname}' berhasil dibuat.", parent=self)

        ctk.CTkButton(dlg, text="💾 Simpan Akun",
                      fg_color="#10B981", hover_color="#059669",
                      command=_simpan).pack(pady=14)

    # ── Dialog Ganti Password ────────────────────────────────────────────────
    def _dialog_ganti_password(self):
        uname = self.selected_username.get()
        if not uname:
            messagebox.showwarning("Pilih Akun", "Pilih akun terlebih dahulu.", parent=self)
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Ganti Password — {uname}")
        dlg.geometry("380x260")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.focus()

        ctk.CTkLabel(dlg, text=f"Ganti Password untuk: {uname}",
                     font=themed_font(13, "bold")).pack(pady=(18, 6))
        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="x", padx=30)

        fields = {}
        for label, key in [("Password Baru", "baru"), ("Konfirmasi Password", "konfirmasi")]:
            ctk.CTkLabel(form, text=label, anchor="w", font=themed_font(11, "bold")).pack(fill="x", pady=(8, 1))
            ent = ctk.CTkEntry(form, show="●")
            ent.pack(fill="x")
            fields[key] = ent

        lbl_err = ctk.CTkLabel(dlg, text="", text_color="#EF4444", font=themed_font(11))
        lbl_err.pack(pady=(8, 0))

        def _simpan():
            pwd = fields["baru"].get()
            konfirm = fields["konfirmasi"].get()
            if len(pwd) < 6:
                lbl_err.configure(text="Password minimal 6 karakter."); return
            if pwd != konfirm:
                lbl_err.configure(text="Password tidak cocok."); return
            hashed, salt = _hash_password(pwd)
            self.accounts[uname]["hashed"] = hashed
            self.accounts[uname]["salt"]   = salt
            save_accounts(self.accounts)
            dlg.destroy()
            messagebox.showinfo("Berhasil", f"Password akun '{uname}' berhasil diubah.", parent=self)

        ctk.CTkButton(dlg, text="💾 Simpan Password",
                      fg_color="#F59E0B", hover_color="#D97706",
                      command=_simpan).pack(pady=14)

    # ── Hapus Akun ───────────────────────────────────────────────────────────
    def _hapus_akun(self):
        uname = self.selected_username.get()
        if not uname:
            messagebox.showwarning("Pilih Akun", "Pilih akun terlebih dahulu.", parent=self); return
        if self.accounts.get(uname, {}).get("role") == "superadmin":
            messagebox.showerror("Tidak Diizinkan", "Akun Super Admin tidak dapat dihapus.", parent=self); return
        if not messagebox.askyesno("Konfirmasi Hapus",
                                   f"Hapus akun '{uname}'?\nTindakan ini tidak dapat dibatalkan.",
                                   parent=self):
            return
        del self.accounts[uname]
        save_accounts(self.accounts)
        self.selected_username.set("")
        self._refresh_list()
        messagebox.showinfo("Berhasil", f"Akun '{uname}' telah dihapus.", parent=self)


