"""
StepLockManager -- mengunci bagian formulir secara BERURUTAN.

Kebutuhan: pada form "Perjalanan Dinas", pengguna wajib menentukan
Pelaksana Perjalanan Dinas (checklist personel di panel kanan) terlebih
dahulu, baru kemudian boleh mengisi bagian-bagian formulir berikutnya
satu per satu sesuai urutan tampilan (dari atas ke bawah) -- tidak boleh
melompat mengisi bagian bawah kalau bagian di atasnya belum lengkap.

Cara kerja:
- Setiap "bagian" (section) formulir didaftarkan lewat `register()` dengan:
    * sebuah frame kontainer yang membungkus widget-widget bagian itu,
    * fungsi `is_complete()` yang mengembalikan True/False,
    * (opsional) daftar widget yang ikut di-nonaktifkan (state="disabled")
      saat terkunci, sebagai lapisan pertahanan kedua selain overlay.
- `refresh()` dipanggil setiap kali ada perubahan input (lihat pemanggilan
  di main_window.schedule_preview_refresh). Bagian pertama yang belum
  lengkap akan MENGUNCI seluruh bagian setelahnya dengan menampilkan
  overlay abu-abu + ikon gembok di atas frame tersebut.
- Overlay menangkap klik (event "<Button-1>") dan membatalkannya
  (return "break") sambil memicu toast peringatan -- jadi pengguna selalu
  tahu KENAPA bagian itu belum bisa diisi.
- Bagian yang tidak butuh overlay visual (misalnya panel pelaksana yang
  memang selalu menjadi gerbang pertama, tidak pernah dikunci oleh apa
  pun) bisa didaftarkan dengan `frame=None` -- hanya dipakai sebagai
  syarat logis dalam urutan, tanpa elemen visual.

Kelas ini sengaja tidak tahu apa pun soal isi formulir SIPS secara
spesifik (nomor surat, tanggal, dst) -- semua pengetahuan itu ada di
closure `is_complete` yang dikirim oleh main_window.py. Ini supaya
komponen ini bisa dipakai ulang untuk form lain di masa depan.
"""
import customtkinter as ctk


def _set_widget_state(widget, state):
    """Set state widget dengan aman -- berbagai jenis widget CTk/ttk
    punya keanehan masing-masing, jadi semua dibungkus try/except supaya
    satu widget yang gagal tidak menghentikan widget lain ikut terkunci."""
    try:
        widget.configure(state=state)
        return
    except Exception:
        pass
    # tkcalendar.DateEntry (berbasis ttk) kadang perlu 'readonly' bukan 'disabled'
    try:
        widget.configure(state=("readonly" if state == "disabled" else "normal"))
    except Exception:
        pass


class StepLockManager:
    def __init__(self, toast_show):
        """`toast_show`: callable(message: str, kind: str) -> None"""
        self._toast_show = toast_show
        self._sections = []  # list of dict: key,label,frame,is_complete,widgets,overlay

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def reset(self):
        for sec in self._sections:
            try:
                if sec["overlay"] is not None:
                    sec["overlay"].destroy()
            except Exception:
                pass
        self._sections = []

    def register(self, key, label, frame, is_complete, widgets=None):
        """Daftarkan satu bagian formulir sesuai urutan pemanggilan
        (urutan pendaftaran = urutan wajib pengisian)."""
        overlay = None
        if frame is not None:
            overlay = self._build_overlay(frame, label)
        self._sections.append({
            "key": key,
            "label": label,
            "frame": frame,
            "is_complete": is_complete,
            "widgets": widgets or [],
            "overlay": overlay,
        })

    def _build_overlay(self, frame, label):
        overlay = ctk.CTkFrame(frame, fg_color=("#E8EAEE", "#31353D"), corner_radius=8)
        lbl = ctk.CTkLabel(
            overlay,
            text=f"🔒  Lengkapi bagian sebelumnya untuk membuka \"{label}\"",
            font=("Arial", 11, "bold"), text_color=("#6B7280", "#9CA3AF"),
            wraplength=320, justify="center",
        )
        lbl.place(relx=0.5, rely=0.5, anchor="center")

        def _blocked(_event=None):
            self._toast_show(
                f"Selesaikan dahulu bagian sebelumnya sebelum mengisi \"{label}\".",
                "warning",
            )
            return "break"

        overlay.bind("<Button-1>", _blocked)
        lbl.bind("<Button-1>", _blocked)
        return overlay

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def first_incomplete(self):
        """Kembalikan dict section pertama yang belum lengkap, atau None
        kalau semua sudah lengkap."""
        for sec in self._sections:
            try:
                complete = bool(sec["is_complete"]())
            except Exception:
                complete = False
            if not complete:
                return sec
        return None

    def is_all_complete(self):
        return self.first_incomplete() is None

    # ------------------------------------------------------------------
    # Refresh (dipanggil tiap ada perubahan input)
    # ------------------------------------------------------------------
    def refresh(self):
        unlocked_so_far = True
        for sec in self._sections:
            frame = sec["frame"]
            if unlocked_so_far:
                if sec["overlay"] is not None:
                    try:
                        sec["overlay"].place_forget()
                    except Exception:
                        pass
                for w in sec["widgets"]:
                    _set_widget_state(w, "normal")
            else:
                if sec["overlay"] is not None:
                    try:
                        sec["overlay"].place(relx=0, rely=0, relwidth=1, relheight=1)
                        sec["overlay"].lift()
                    except Exception:
                        pass
                for w in sec["widgets"]:
                    _set_widget_state(w, "disabled")

            try:
                complete = bool(sec["is_complete"]())
            except Exception:
                complete = False
            if not complete:
                unlocked_so_far = False

    # ------------------------------------------------------------------
    # Dipanggil sebelum aksi akhir (mis. tombol "Cetak Surat")
    # ------------------------------------------------------------------
    def notify_if_incomplete(self):
        """Kalau ada bagian yang belum lengkap, tampilkan toast error dan
        kembalikan True (artinya: BLOKIR aksi). Kalau semua lengkap,
        kembalikan False (aksi boleh lanjut)."""
        sec = self.first_incomplete()
        if sec is None:
            return False
        self._toast_show(
            f"Lengkapi dahulu bagian \"{sec['label']}\" sebelum mencetak.",
            "error",
        )
        try:
            frame = sec["frame"]
            if frame is None and sec["widgets"]:
                frame = sec["widgets"][0]
        except Exception:
            frame = None
        if frame is not None:
            try:
                frame.focus_set()
            except Exception:
                pass
        return True
