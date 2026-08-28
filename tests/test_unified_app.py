from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from sekretariat_app.auth import UserRepository
from sekretariat_app.documentation.models import DocumentProject, PAPER_SIZES
from sekretariat_app.documentation.templates import TEMPLATES, layout_rectangles
from tpp_finger_scan.domain.models import Employee
from tpp_finger_scan.infrastructure.employee_master import EmployeeMaster, normalize_employee_name


class UnifiedApplicationTests(unittest.TestCase):
    def test_packaged_employee_master_resolves_position(self):
        master = EmployeeMaster()
        self.assertEqual(len(master.records), 29)
        self.assertEqual(
            master.find("YUNIKY RAINTUNG").position,
            "Petugas Protokol Komisi III",
        )
        self.assertEqual(
            master.find("ZUSANA J.D. KAUNANG").position,
            "Analis Kebijakan Ahli Muda",
        )
        positions = master.resolve_positions([Employee("120", "YUNIKY RAINTUNG")])
        self.assertEqual(positions["120"], "Petugas Protokol Komisi III")

    def test_employee_name_normalization_removes_titles_and_degrees(self):
        self.assertEqual(
            normalize_employee_name("Drs. ALBERT M. SARESE, M.Si."),
            "ALBERT M SARESE",
        )

    def test_default_project_roundtrip_and_f4_size(self):
        project = DocumentProject(title="Dokumentasi Rapat")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rapat.dokufoto.json"
            project.save(path)
            loaded = DocumentProject.load(path)
        self.assertEqual(loaded.title, "Dokumentasi Rapat")
        self.assertEqual(loaded.page_size_mm, PAPER_SIZES["F4"])
        self.assertEqual(len(loaded.pages), 1)

    def test_all_templates_stay_inside_page_margins(self):
        width, height = PAPER_SIZES["F4"]
        margins = (15.0, 15.0, 15.0, 15.0)
        self.assertEqual(len(TEMPLATES), 11)
        for template in TEMPLATES:
            rectangles = layout_rectangles(template, width, height, margins)
            self.assertEqual(len(rectangles), len(template.cells))
            for x, y, cell_width, cell_height in rectangles:
                self.assertGreaterEqual(x, margins[3])
                self.assertGreaterEqual(y, margins[0])
                self.assertLessEqual(x + cell_width, width - margins[1] + 0.001)
                self.assertLessEqual(y + cell_height, height - margins[2] + 0.001)

    def test_user_password_is_hashed_and_authentication_works(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = UserRepository(Path(temp_dir) / "users.db")
            self.assertIsNotNone(repository.authenticate("admin", "admin123"))
            self.assertIsNone(repository.authenticate("admin", "wrong-password"))
            created = repository.add_user("operator1", "Operator Satu", "operator", "rahasia123")
            self.assertEqual(repository.authenticate("operator1", "rahasia123"), created)

    def test_documentation_menu_is_after_tpp(self):
        shell_source = (
            Path(__file__).parents[1]
            / "src"
            / "sekretariat_app"
            / "ui"
            / "shell.py"
        ).read_text(encoding="utf-8")
        tpp_position = shell_source.index('self._nav("Rekapitulasi TPP", "tpp")')
        documentation_position = shell_source.index('self._nav("Dokumentasi Foto", "documentation")')
        self.assertLess(tpp_position, documentation_position)

    def test_react_workspace_can_be_migrated(self):
        pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        photo = {"id": "photo-1", "name": "foto.png", "dataUrl": f"data:image/png;base64,{pixel}"}
        workspace = {
            "kind": "dokufoto-workspace",
            "schemaVersion": 1,
            "project": {
                "id": "react-project",
                "title": "Proyek React Lama",
                "paperSize": "F4",
                "orientation": "portrait",
                "margins": {"top": 2, "right": 2, "bottom": 2, "left": 2.5},
                "fontFamily": "Arial",
                "author": "Operator",
                "institution": "Sekretariat DPRD",
                "createdAt": "2026-08-01T00:00:00",
                "updatedAt": "2026-08-01T00:00:00",
                "kopSurat": {
                    "enabled": False,
                    "governmentName": "PEMERINTAH KOTA BITUNG",
                    "agencyName": "DPRD",
                    "address": "Bitung",
                    "contactInfo": "",
                    "borderStyle": "double",
                },
                "pages": [{
                    "id": "page-1",
                    "pageNumber": 1,
                    "title": "Dokumentasi",
                    "layoutTemplateId": "grid-1",
                    "cells": [{"id": "cell-1", "row": 0, "col": 0, "photo": photo}],
                    "grids": [{
                        "id": "grid-1", "x": 50, "y": 52, "widthPercent": 80,
                        "heightPx": 300, "rows": 1, "cols": 1, "cells": [
                            {"id": "cell-1", "row": 0, "col": 0, "photo": photo}
                        ],
                    }],
                    "floatingTexts": [{
                        "id": "text-1", "text": "RAPAT", "x": 50, "y": 10,
                        "width": 300, "fontSize": 24, "fontFamily": "Arial",
                    }],
                }],
            },
            "photos": [photo],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "lama.dokufoto.json"
            path.write_text(json.dumps(workspace), encoding="utf-8")
            project = DocumentProject.load(path)
            self.assertEqual(project.title, "Proyek React Lama")
            self.assertEqual(project.margins.left, 25.0)
            self.assertEqual(len(project.pages[0].elements), 2)
            self.assertTrue(project.media)
            self.assertTrue(Path(project.media[0]).exists())


if __name__ == "__main__":
    unittest.main()
