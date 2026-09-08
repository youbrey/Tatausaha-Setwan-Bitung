from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


class PDFJobs(QObject):
    finished = Signal(dict)
    progress = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.finished.connect(self._finish)
        self.process.errorOccurred.connect(self._error)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.readyReadStandardOutput.connect(self._drain_stdout)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.timer = QTimer(self)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self._poll)
        self.directory = None
        self._stderr = bytearray()
        self.busy = False

    def start(self, request: dict) -> None:
        if self.busy:
            raise RuntimeError("Tunggu pekerjaan PDF selesai.")
        self.directory = tempfile.TemporaryDirectory(prefix="setwan-pdf-job-")
        path = Path(self.directory.name) / "request.json"
        with path.open("w", encoding="utf-8") as stream:
            os.chmod(path, 0o600)
            json.dump(request, stream, ensure_ascii=False)
        # Do not redirect to ``os.devnull`` here.  In a windowed PyInstaller
        # build on Windows, Qt can interpret ``nul`` as a relative output file
        # and abort before the worker starts with "Could not open output
        # redirection for writing".  Draining both channels is portable and
        # also gives us the real worker error when startup fails.
        self._stderr.clear()
        environment = QProcessEnvironment.systemEnvironment()
        if getattr(sys, "frozen", False):
            # PyInstaller harus memperlakukan executable kedua sebagai proses
            # baru. Tanpa ini bootloader dapat berhenti sebelum dispatcher
            # ``--pdf-worker`` dijalankan pada build Windows.
            environment.insert("PYINSTALLER_RESET_ENVIRONMENT", "1")
        self.process.setProcessEnvironment(environment)
        self.busy = True
        self.busy_changed.emit(True)
        arguments = (["--pdf-worker"] if getattr(sys, "frozen", False)
                     else ["-m", "sekretariat_app.pdf_tools.worker"])
        self.process.start(sys.executable, arguments + [str(path)])
        self.timer.start()

    def _read_stderr(self) -> None:
        self._stderr.extend(bytes(self.process.readAllStandardError()))
        if len(self._stderr) > 16_384:
            del self._stderr[:-16_384]

    def _drain_stdout(self) -> None:
        self.process.readAllStandardOutput()

    def cancel(self) -> None:
        if self.directory and self.busy:
            (Path(self.directory.name) / "cancel").touch()
            self.progress.emit("Membatalkan setelah operasi aktif selesai…")

    def _poll(self) -> None:
        if not self.directory:
            return
        try:
            data = json.loads((Path(self.directory.name) / "progress.json").read_text(encoding="utf-8"))
            suffix = f' ({data["done"]}/{data["total"]})' if data["total"] else ""
            self.progress.emit(data["message"] + suffix)
        except (OSError, ValueError, KeyError):
            pass

    def _error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._finish()

    def _finish(self, *_args) -> None:
        if not self.busy:
            return
        self.timer.stop()
        self._read_stderr()
        self._drain_stdout()
        try:
            data = json.loads((Path(self.directory.name) / "result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            detail = ""
            detail = self._stderr.decode("utf-8", errors="replace").strip()
            if detail:
                detail = detail[-2000:]
            else:
                detail = self.process.errorString().strip()
            if not detail or detail == "Unknown error":
                detail = f"Kode keluar proses: {self.process.exitCode()}"
            message = "Proses PDF berhenti sebelum menghasilkan hasil."
            if detail:
                message += f"\n\nRincian teknis:\n{detail}"
            data = {"ok": False, "error": message}
        self.directory.cleanup()
        self.directory = None
        self._stderr.clear()
        self.busy = False
        self.busy_changed.emit(False)
        self.finished.emit(data)
