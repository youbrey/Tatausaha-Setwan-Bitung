"""One disposable process per PDF job; never run MuPDF on Qt worker threads."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _write(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".writing")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    # Also works from a windowed PyInstaller executable without stdin/stdout.
    request_file = Path(sys.argv[-1])
    directory = request_file.parent
    try:
        request = json.loads(request_file.read_text(encoding="utf-8"))
        request_file.unlink(missing_ok=True)
        if os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
        from .engine import execute

        def progress(done: int, total: int, message: str) -> None:
            if (directory / "cancel").exists():
                raise InterruptedError("Pekerjaan dibatalkan. Dokumen sumber tetap utuh.")
            _write(directory / "progress.json", {"done": done, "total": total, "message": message})

        progress(0, 0, "Memproses dokumen…")
        result = execute(request, progress)
        progress(1, 1, "Selesai")
        _write(directory / "result.json", {"ok": True, "result": result})
    except Exception as error:
        _write(directory / "result.json", {
            "ok": False, "error": str(error), "cancelled": isinstance(error, InterruptedError),
            "password_path": getattr(error, "path", None),
        })
        return 1
    finally:
        request_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
