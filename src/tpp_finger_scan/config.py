from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "Rekapitulasi TPP PNS - Sekretariat DPRD Kota Bitung"


def application_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "TPPFingerScan"
    return Path.cwd() / ".tpp-finger-scan-data"


def database_path() -> Path:
    return application_data_dir() / "tpp_finger_scan.db"
