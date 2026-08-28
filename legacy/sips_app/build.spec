# build.spec
#
# Cara pakai:
#   pyinstaller build.spec
#
# Hasil build ada di dist/SIPS/ (mode --onedir, direkomendasikan supaya
# folder resources/ & user_data/ mudah diakses/di-diagnosa di sisi user).

import customtkinter
import os
import sys

block_cipher = None

# Folder asset bawaan customtkinter (theme json, font) wajib diikutkan,
# kalau tidak aplikasi akan crash saat dijalankan sebagai .exe.
ctk_path = os.path.dirname(customtkinter.__file__)

# Folder data internal matplotlib (font DejaVu, mplstyle, dll) -- dipakai
# oleh grafik di halaman Dashboard. Tanpa ini, render grafik bisa gagal
# saat dijalankan sebagai .exe walau tidak error saat `python main.py`.
try:
    import matplotlib
    mpl_data_path = matplotlib.get_data_path()
except Exception:
    mpl_data_path = None

# Deteksi folder PyMuPDF (fitz) — nama folder bisa 'fitz' atau 'pymupdf'
# tergantung versi yang terinstall.
try:
    import fitz as _fitz
    fitz_path = os.path.dirname(_fitz.__file__)
except Exception:
    fitz_path = None

extra_datas = [
    ('resources', 'resources'),
    (ctk_path, 'customtkinter'),
]
if fitz_path:
    extra_datas.append((fitz_path, os.path.basename(fitz_path)))
if mpl_data_path:
    extra_datas.append((mpl_data_path, 'matplotlib/mpl-data'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=extra_datas,
    hiddenimports=[
        # PIL / Pillow
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk',
        # PyMuPDF — nama modul berubah-ubah tergantung versi
        'fitz',
        'fitz.fitz',
        'pymupdf',
        # docx2pdf & COM (Word automation)
        'docx2pdf',
        'pythoncom',
        'pywintypes',
        'win32com',
        'win32com.client',
        'win32com.client.gencache',
        # python-docx / docxtpl
        'docx',
        'docxtpl',
        'lxml',
        'lxml.etree',
        # tkcalendar (opsional)
        'tkcalendar',
        'babel.numbers',
        # matplotlib (grafik di halaman Dashboard) -- backend TkAgg wajib
        # disebut eksplisit, PyInstaller tidak selalu mendeteksinya otomatis.
        'matplotlib',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_agg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SIPS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # Ubah ke True sementara jika ingin lihat traceback/error di jendela CMD
    console=False,
    icon='resources/icons/app_icon.ico',
)

# --onedir (direkomendasikan): hasil ada di dist/SIPS/ + folder pendukungnya
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='SIPS',
)
