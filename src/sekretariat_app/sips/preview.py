from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class DocxPreviewConverter:
    """Konversi DOCX ke PDF memakai Microsoft Word atau LibreOffice lokal."""

    @staticmethod
    def available() -> bool:
        return os.name == "nt" or bool(shutil.which("soffice") or shutil.which("libreoffice"))

    def convert(self, document_path: str | Path, output_directory: str | Path) -> Path:
        source = Path(document_path).resolve()
        target_directory = Path(output_directory).resolve()
        target_directory.mkdir(parents=True, exist_ok=True)
        target = target_directory / f"{source.stem}.pdf"
        if os.name == "nt":
            try:
                self._convert_with_word(source, target)
                if target.exists():
                    return target
            except (OSError, subprocess.SubprocessError):
                pass
        office = shutil.which("soffice") or shutil.which("libreoffice")
        if not office:
            raise RuntimeError("Pratinjau memerlukan Microsoft Word atau LibreOffice.")
        subprocess.run(
            [office, "--headless", "--convert-to", "pdf", "--outdir", str(target_directory), str(source)],
            check=True,
            capture_output=True,
            timeout=120,
        )
        if not target.exists():
            raise RuntimeError("Konversi pratinjau tidak menghasilkan PDF.")
        return target

    @staticmethod
    def _convert_with_word(source: Path, target: Path) -> None:
        def quote(value: Path) -> str:
            return str(value).replace("'", "''")

        script = (
            "$ErrorActionPreference='Stop';"
            "$word=New-Object -ComObject Word.Application;"
            "$word.Visible=$false;"
            f"$doc=$word.Documents.Open('{quote(source)}');"
            f"$doc.SaveAs([ref]'{quote(target)}',[ref]17);"
            "$doc.Close();$word.Quit();"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            check=True,
            capture_output=True,
            timeout=120,
        )
