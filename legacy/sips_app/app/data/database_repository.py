"""
Repository untuk data master DPRD & ASN: membaca dari file Excel/CSV master,
serta menyimpan/memuat cache lokal (sips_data.json). Tidak ada kode UI di
sini -- semua fungsi murni menerima/mengembalikan data biasa (list of dict)
supaya mudah diuji dan dipakai ulang.
"""
import os

import pandas as pd

from app.config.settings import DATA_FILE, DATABASE_XLSX
from app.data.shared_store import locked_read_json, locked_write_json, SharedStoreError


def normalize_keys(data_list):
    """Ubah semua key dict jadi lowercase + strip, supaya konsisten dipakai
    di seluruh aplikasi (mis. 'Nama' / 'NAMA' / 'nama' -> 'nama')."""
    normalized = []
    for d in data_list:
        if isinstance(d, dict):
            normalized.append({str(k).lower().strip(): v for k, v in d.items()})
    return normalized


def read_dprd_asn_from_excel_file(path):
    """Baca sheet DPRD & ASN dari satu file Excel. Nama sheet dicari secara
    fleksibel (mengandung kata 'dprd'/'anggota' untuk DPRD, 'asn'/'pendamping'
    untuk ASN)."""
    xls = pd.ExcelFile(path)
    sheet_dprd = next((s for s in xls.sheet_names if "dprd" in s.lower() or "anggota" in s.lower()), None)
    sheet_asn = next((s for s in xls.sheet_names if "asn" in s.lower() or "pendamping" in s.lower()), None)

    raw_dprd, raw_asn = [], []
    if sheet_dprd:
        df = pd.read_excel(xls, sheet_name=sheet_dprd)
        df.columns = [str(c).strip() for c in df.columns]
        for _, row in df.iterrows():
            raw_dprd.append({
                "nama": str(row.get("Nama", row.get("NAMA", ""))).strip(),
                "jabatan": str(row.get("Jabatan", row.get("JABATAN", ""))).strip(),
                "kategori": str(row.get("Kategori", row.get("KATEGORI", "Custom"))).strip()
            })
    if sheet_asn:
        df = pd.read_excel(xls, sheet_name=sheet_asn)
        df.columns = [str(c).strip() for c in df.columns]
        for _, row in df.iterrows():
            raw_asn.append({
                "nama": str(row.get("NAMA", row.get("Nama", ""))).strip(),
                "nip": str(row.get("NIP", "-")).strip(),
                "pangkat": str(row.get("PANGKAT/GOLONGAN", row.get("Pangkat", "-"))).strip(),
                "jabatan": str(row.get("JABATAN", row.get("Jabatan", "-"))).strip()
            })
    return raw_dprd, raw_asn


def read_dprd_asn_from_csv_file(path):
    """Baca data DPRD ATAU ASN dari satu file CSV (formatnya ditebak dari
    keberadaan kolom NIP: ada NIP -> dianggap data ASN, tidak ada -> DPRD)."""
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    cols_lower = [c.lower() for c in df.columns]

    raw_dprd, raw_asn = [], []
    if "nip" in cols_lower:
        for _, row in df.iterrows():
            raw_asn.append({
                "nama": str(row.get("NAMA", row.get("Nama", ""))).strip(),
                "nip": str(row.get("NIP", "-")).strip(),
                "pangkat": str(row.get("PANGKAT/GOLONGAN", row.get("Pangkat", "-"))).strip(),
                "jabatan": str(row.get("JABATAN", row.get("Jabatan", "-"))).strip()
            })
    else:
        for _, row in df.iterrows():
            raw_dprd.append({
                "nama": str(row.get("Nama", row.get("NAMA", ""))).strip(),
                "jabatan": str(row.get("Jabatan", row.get("JABATAN", ""))).strip(),
                "kategori": str(row.get("Kategori", row.get("KATEGORI", "Custom"))).strip()
            })
    return raw_dprd, raw_asn


def read_dprd_asn_from_file(path):
    """Dispatcher otomatis berdasarkan ekstensi file (.xlsx/.xls -> Excel,
    selain itu -> CSV)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return read_dprd_asn_from_excel_file(path)
    return read_dprd_asn_from_csv_file(path)


DEFAULT_DB_DPRD = [
    {"nama": "VIVY JEANET GANAP, S.E.", "jabatan": "KETUA", "kategori": "Pimpinan DPRD"}
]
DEFAULT_DB_ASN = [
    {"nama": "Drs. ALBERT M. SARESE, M.Si.", "nip": "19681011 199010 1 002",
     "pangkat": "PEMBINA UTAMA MUDA IV/c", "jabatan": "Sekretaris DPRD"}
]


def load_database():
    """Muat database DPRD & ASN. Urutan prioritas (DIUBAH utk mode
    jaringan):
    1) sips_data.json (cache -- kalau mode jaringan aktif, ini file
       BERSAMA yang dipakai semua komputer, jadi hasil "Kelola Database"/
       import di satu komputer langsung terlihat di komputer lain).
    2) database_dprd_asn.xlsx (master resource bawaan) -- HANYA dipakai
       untuk pengisian AWAL saat cache belum pernah ada sama sekali.
    3) data contoh default.

    Dulu urutan #1/#2 terbalik (xlsx SELALU dibaca ulang & menimpa cache
    tiap start) -- itu membuat perubahan nama pelaksana lewat "Kelola
    Database" hilang lagi setelah restart, dan membuat tiap komputer
    memakai xlsx lokalnya sendiri-sendiri alih-alih data bersama.

    Mengembalikan tuple (db_dprd, db_asn).
    """
    cache = locked_read_json(DATA_FILE, None)
    if isinstance(cache, dict) and (cache.get("dprd") or cache.get("asn")):
        return normalize_keys(cache.get("dprd", [])), list(cache.get("asn", []))

    if os.path.exists(DATABASE_XLSX):
        try:
            raw_dprd, raw_asn = read_dprd_asn_from_excel_file(DATABASE_XLSX)
            if raw_dprd or raw_asn:
                db_dprd = normalize_keys(raw_dprd) if raw_dprd else []
                db_asn = normalize_keys(raw_asn) if raw_asn else []
                save_database(db_dprd, db_asn)
                return db_dprd, db_asn
        except Exception:
            pass

    save_database(DEFAULT_DB_DPRD, DEFAULT_DB_ASN)
    return list(DEFAULT_DB_DPRD), list(DEFAULT_DB_ASN)


def save_database(db_dprd, db_asn):
    try:
        locked_write_json(DATA_FILE, {"dprd": db_dprd, "asn": db_asn})
    except Exception:
        pass
