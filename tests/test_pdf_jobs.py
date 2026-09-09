from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import fitz
from PIL import Image
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from sekretariat_app.pdf_tools.engine import execute
from sekretariat_app.ui.pdf_jobs import PDFJobs


class PdfJobsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_worker_starts_and_returns_result_without_file_redirection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            output = root / "working-copy.pdf"
            with fitz.open() as document:
                page = document.new_page()
                page.insert_text((72, 72), "Uji Edit PDF")
                document.save(source)

            job = PDFJobs()
            loop = QEventLoop()
            messages: list[dict] = []

            def complete(message: dict) -> None:
                messages.append(message)
                loop.quit()

            job.finished.connect(complete)
            job.start({"action": "open", "source": str(source), "output": str(output)})
            QTimer.singleShot(20_000, loop.quit)
            loop.exec()

            self.assertTrue(messages, "Worker PDF tidak selesai dalam 20 detik")
            self.assertTrue(messages[0].get("ok"), json.dumps(messages[0], ensure_ascii=False))
            self.assertTrue(output.is_file())
            with fitz.open(output) as result:
                self.assertEqual(len(result), 1)

    def test_core_pdf_menu_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            with fitz.open() as document:
                for index in range(3):
                    page = document.new_page()
                    page.insert_text((72, 72), f"Halaman {index + 1}")
                document.save(source)
            image = root / "photo.png"
            Image.new("RGB", (80, 60), "navy").save(image)

            operations = [
                {"action": "open", "source": str(source), "output": str(root / "open.pdf")},
                {"action": "organize", "source": str(source), "output": str(root / "organize.pdf"), "pages": "3,1-2,2"},
                {"action": "delete", "source": str(source), "output": str(root / "delete.pdf"), "pages": "2"},
                {"action": "rotate", "source": str(source), "output": str(root / "rotate.pdf"), "pages": "1", "angle": 90},
                {"action": "blank", "source": str(source), "output": str(root / "blank.pdf"), "page": 0},
                {"action": "text", "source": str(source), "output": str(root / "text.pdf"), "page": 0,
                 "rect": [0.1, 0.1, 0.65, 0.3], "text": "Teks baru", "size": 12},
                {"action": "image", "source": str(source), "output": str(root / "image.pdf"), "page": 0,
                 "rect": [0.1, 0.1, 0.5, 0.5], "image": str(image)},
                {"action": "merge", "sources": [str(source), str(source)], "output": str(root / "merge.pdf")},
                {"action": "split", "source": str(source), "output": str(root / "split"), "groups": "1-2;3"},
                {"action": "images_to_pdf", "sources": [str(image)], "output": str(root / "images.pdf")},
                {"action": "pdf_to_images", "source": str(source), "output": str(root / "pages"), "pages": "", "dpi": 72},
                {"action": "pdf_to_word", "source": str(source), "output": str(root / "editable.docx"), "mode": "text"},
                {"action": "pdf_to_word", "source": str(source), "output": str(root / "appearance.docx"), "mode": "appearance"},
                {"action": "protect", "source": str(source), "output": str(root / "protected.pdf"),
                 "user_password": "user-pass", "owner_password": "owner-pass"},
            ]

            for request in operations:
                with self.subTest(action=request["action"], output=request["output"]):
                    result = execute(request)
                    self.assertTrue(Path(result["path"]).exists())

            result = execute({
                "action": "unprotect",
                "source": str(root / "protected.pdf"),
                "output": str(root / "unprotected.pdf"),
                "password": "owner-pass",
            })
            self.assertTrue(Path(result["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
