"""
ToastManager -- notifikasi "toast" melayang non-blocking di pojok window.

Dipakai antara lain oleh StepLockManager (app/ui/components/step_lock.py)
untuk memberi tahu pengguna saat mereka mencoba melangkahi urutan pengisian
formulir. Sengaja dibuat generik (bukan cuma untuk step-lock) supaya bisa
dipakai ulang untuk notifikasi ringan lain di masa depan (mis. "Draft
tersimpan", "Import selesai", dsb).

Desain:
- Tidak memakai CTkToplevel/messagebox supaya TIDAK modal -- pengguna tetap
  bisa lanjut bekerja, toast hilang sendiri setelah beberapa detik.
- Beberapa toast bisa tampil bertumpuk (stacked) di pojok kanan-bawah.
- Bila widget induk sudah dihancurkan (window ditutup saat toast masih
  jalan), semua operasi dibungkus try/except supaya tidak melempar error
  yang mengganggu proses keluar aplikasi.
"""
import customtkinter as ctk

_KIND_COLORS = {
    "info": ("#2563EB", "#FFFFFF"),
    "success": ("#059669", "#FFFFFF"),
    "warning": ("#F59E0B", "#1F2937"),
    "error": ("#DC2626", "#FFFFFF"),
}

_TOAST_GAP = 0.085  # jarak vertikal relatif antar toast yang bertumpuk


class ToastManager:
    def __init__(self, root):
        self.root = root
        self._active = []  # list of CTkFrame yang sedang tampil (urutan lama -> baru)

    def show(self, message, kind="info", duration_ms=2800):
        """Tampilkan satu toast. `kind`: info | success | warning | error."""
        try:
            bg, fg = _KIND_COLORS.get(kind, _KIND_COLORS["info"])
            frame = ctk.CTkFrame(self.root, fg_color=bg, corner_radius=8, border_width=0)
            icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "⛔"}.get(kind, "ℹ️")
            lbl = ctk.CTkLabel(
                frame, text=f"{icon}  {message}", text_color=fg,
                font=("Arial", 12, "bold"), wraplength=340, justify="left",
            )
            lbl.pack(padx=16, pady=10)
            frame.lift()
            self._active.append(frame)
            self._reflow()

            def _remove():
                try:
                    if frame in self._active:
                        self._active.remove(frame)
                    frame.destroy()
                    self._reflow()
                except Exception:
                    pass

            self.root.after(duration_ms, _remove)
        except Exception:
            # Toast murni kosmetik -- jangan pernah sampai mengganggu alur
            # utama aplikasi (mis. saat window sedang dalam proses ditutup).
            pass

    def show_center(self, message, kind="warning", duration_ms=3200):
        """Toast yang muncul TEPAT DI TENGAH LAYAR/window, dipakai untuk
        peringatan yang harus benar-benar dilihat pengguna (mis. judul/
        materi kegiatan yang sudah pernah dibuat sebelumnya) -- beda dari
        `show()` biasa yang muncul di pojok dan mudah terlewat."""
        try:
            bg, fg = _KIND_COLORS.get(kind, _KIND_COLORS["warning"])
            frame = ctk.CTkFrame(self.root, fg_color=bg, corner_radius=12, border_width=0)
            icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "⛔"}.get(kind, "⚠️")
            lbl = ctk.CTkLabel(
                frame, text=f"{icon}  {message}", text_color=fg,
                font=("Arial", 13, "bold"), wraplength=420, justify="center",
            )
            lbl.pack(padx=24, pady=16)
            frame.place(relx=0.5, rely=0.5, anchor="center")
            frame.lift()

            def _remove():
                try:
                    frame.destroy()
                except Exception:
                    pass

            self.root.after(duration_ms, _remove)
        except Exception:
            pass

    def _reflow(self):
        try:
            for i, frame in enumerate(reversed(self._active)):
                frame.place(relx=0.99, rely=0.97 - _TOAST_GAP * i, anchor="se")
        except Exception:
            pass
