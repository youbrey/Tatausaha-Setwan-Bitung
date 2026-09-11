from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PIL import Image
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from sekretariat_app.pdf_tools.engine import execute
from sekretariat_app.ui.pdf_jobs import PDFJobs


def _progress(*_args) -> None:
    pass


class PdfToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source.pdf"
        with fitz.open() as document:
            first = document.new_page(width=300, height=300)
            first.insert_text((35, 55), "Teks halaman pertama")
            second = document.new_page(width=300, height=300)
            second.insert_text((35, 55), "Teks halaman kedua")
            document.save(self.source)
        self.image = self.root / "photo.png"
        Image.new("RGB", (80, 60), "#2563eb").save(self.image)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _run(self, action: str, output: str, **values):
        target = self.root / output
        result = execute({
            "action": action,
            "source": str(self.source),
            "output": str(target),
            **values,
        }, _progress)
        return target, result

    def test_page_and_content_edit_actions(self) -> None:
        organized, result = self._run("organize", "organized.pdf", pages="2,1,2")
        self.assertEqual(result["count"], 3)
        deleted, result = self._run("delete", "deleted.pdf", pages="2")
        self.assertEqual(result["count"], 1)
        rotated, _ = self._run("rotate", "rotated.pdf", pages="1", angle=90)
        blank, result = self._run("blank", "blank.pdf", page=0)
        self.assertEqual(result["count"], 3)
        text, _ = self._run(
            "text", "text.pdf", page=0, rect=[0.1, 0.25, 0.9, 0.5],
            text="Tambahan", size=12, family="sans-serif", color="#000000",
        )
        image, _ = self._run(
            "image", "image.pdf", page=0, rect=[0.1, 0.2, 0.5, 0.6],
            image=str(self.image),
        )
        for path in (organized, deleted, rotated, blank, text, image):
            with fitz.open(path) as document:
                self.assertGreaterEqual(len(document), 1)

    def test_merge_split_render_convert_and_security_actions(self) -> None:
        copied, _ = self._run("copy", "copy.pdf")
        rendered, result = self._run("render", "preview.png", page=0, width=700)
        self.assertEqual(result["count"], 2)
        self.assertTrue(rendered.is_file())

        merged = self.root / "merged.pdf"
        execute({
            "action": "merge",
            "sources": [str(self.source), str(copied)],
            "output": str(merged),
        }, _progress)
        with fitz.open(merged) as document:
            self.assertEqual(len(document), 4)

        split_dir, result = self._run("split", "split", groups="1;2")
        self.assertEqual(result["files"], 2)
        self.assertEqual(len(list(split_dir.glob("*.pdf"))), 2)
        png_dir, result = self._run("pdf_to_images", "png", pages="1-2", dpi=72)
        self.assertEqual(result["files"], 2)
        self.assertEqual(len(list(png_dir.glob("*.png"))), 2)
        docx, _ = self._run("pdf_to_word", "editable.docx", mode="text")
        self.assertGreater(docx.stat().st_size, 1000)

        from_images = self.root / "images.pdf"
        execute({
            "action": "images_to_pdf",
            "sources": [str(self.image)],
            "output": str(from_images),
        }, _progress)
        protected, _ = self._run(
            "protect", "protected.pdf", user_password="buka",
            owner_password="pemilik", allow_print=True, allow_copy=False,
        )
        unprotected = self.root / "unprotected.pdf"
        execute({
            "action": "unprotect", "source": str(protected),
            "output": str(unprotected), "password": "pemilik",
        }, _progress)
        with fitz.open(unprotected) as document:
            self.assertFalse(document.needs_pass)

    def test_worker_uses_process_pipes_and_returns_result(self) -> None:
        app = QCoreApplication.instance() or QCoreApplication([])
        output = self.root / "worker-copy.pdf"
        received: list[dict] = []
        loop = QEventLoop()
        jobs = PDFJobs()
        jobs.finished.connect(lambda result: (received.append(result), loop.quit()))
        jobs.start({
            "action": "copy",
            "source": str(self.source),
            "output": str(output),
        })
        QTimer.singleShot(15_000, loop.quit)
        loop.exec()
        app.processEvents()
        self.assertTrue(received, "worker PDF tidak selesai dalam 15 detik")
        self.assertTrue(received[0].get("ok"), received[0])
        self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
