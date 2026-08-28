from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "SIPS Terpadu - Sekretariat DPRD Kota Bitung"
ORGANIZATION = "Sekretariat DPRD Kota Bitung"


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.cwd()
    target = root / "SekretariatDPRDBitung"
    target.mkdir(parents=True, exist_ok=True)
    return target


def database_path() -> Path:
    return data_dir() / "sekretariat.db"


def documentation_dir() -> Path:
    target = data_dir() / "dokumentasi_foto"
    target.mkdir(parents=True, exist_ok=True)
    return target


def autosave_path() -> Path:
    return documentation_dir() / "autosave.dokufoto.json"
