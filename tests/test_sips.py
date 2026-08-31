from __future__ import annotations

import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from sekretariat_app.sips.master_data import PersonnelMaster
from sekretariat_app.sips.models import InvitationFormData, TravelFormData
from sekretariat_app.sips.repository import SIPSRepository
from sekretariat_app.sips.service import SIPSService


def assert_valid_docx(test_case: unittest.TestCase, path: Path) -> None:
    test_case.assertTrue(path.exists(), path)
    test_case.assertGreater(path.stat().st_size, 1_000, path)
    with zipfile.ZipFile(path) as archive:
        test_case.assertIsNone(archive.testzip(), path)
        test_case.assertIn("word/document.xml", archive.namelist())


class SIPSMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.master = PersonnelMaster()
        cls.service = SIPSService(cls.master)

    def test_packaged_master_contains_dprd_asn_and_signers(self) -> None:
        self.assertEqual(len(self.master.dprd), 100)
        self.assertEqual(len(self.master.asn), 27)
        self.assertTrue(self.master.dprd_signers)
        self.assertTrue(self.master.asn_signers)
        self.assertTrue(all(row["nama"] for row in self.master.dprd))
        self.assertTrue(all(row["nama"] for row in self.master.asn))

    def test_dprd_travel_generates_complete_document_set(self) -> None:
        data = TravelFormData(
            mode="dprd",
            document_numbers={
                "surat_tugas_dprd": "001/ST-DPRD/VIII/2026",
                "pemberitahuan_dprd": "002/PB-DPRD/VIII/2026",
                "spd_dprd": "003/SPD-DPRD/VIII/2026",
            },
            letter_date=date(2026, 8, 28),
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            travel_type="Kunjungan Kerja",
            basis_dprd="Keputusan Pimpinan DPRD Kota Bitung",
            basis_asn="Surat Perintah Sekretaris DPRD Kota Bitung",
            subject="Koordinasi penyusunan program kerja",
            notice_subject="Melaksanakan koordinasi penyusunan program kerja",
            destinations=["DPRD Kota Manado"],
            signer_dprd=self.master.dprd_signers[0],
            signer_asn=self.master.asn_signers[0],
            dprd=[self.master.dprd[0]],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            files = self.service.generate_travel(data, temp_dir)
            self.assertEqual(len(files), 5)
            for path in files:
                assert_valid_docx(self, path)

    def test_secretariat_travel_generates_executor_and_companion_sets(self) -> None:
        data = TravelFormData(
            mode="setwan",
            document_numbers={
                "surat_tugas_asn": "010/ST-SETWAN/VIII/2026",
                "pemberitahuan_asn": "011/PB-SETWAN/VIII/2026",
                "spd_pelaksana": "012/SPD-PL/VIII/2026",
                "spd_pendamping": "013/SPD-PD/VIII/2026",
            },
            letter_date=date(2026, 8, 28),
            start_date=date(2026, 9, 3),
            end_date=date(2026, 9, 4),
            travel_type="Kunjungan Konsultasi",
            basis_dprd="Keputusan Pimpinan DPRD Kota Bitung",
            basis_asn="Surat Perintah Sekretaris DPRD Kota Bitung",
            subject="Konsultasi tata kelola administrasi",
            notice_subject="Melaksanakan konsultasi tata kelola administrasi",
            destinations=["Sekretariat DPRD Kota Tomohon"],
            signer_dprd=self.master.dprd_signers[0],
            signer_asn=self.master.asn_signers[0],
            executors=[self.master.asn[0]],
            companions=[self.master.asn[1]],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            files = self.service.generate_travel(data, temp_dir)
            self.assertEqual(len(files), 9)
            for path in files:
                assert_valid_docx(self, path)

    def test_plenary_invitation_generates_eight_page_template_and_support(self) -> None:
        data = InvitationFormData(
            invitation_type="paripurna",
            number="080/UND-PAR/VIII/2026",
            letter_date=date(2026, 8, 28),
            meeting_date=date(2026, 9, 7),
            time_text="10.00 WITA s.d. selesai",
            agenda="Rapat Paripurna DPRD Kota Bitung",
            signer=self.master.dprd_signers[0],
            clothing="PSL",
            scenarios=["Pembukaan", "Penyampaian laporan", "Penutupan"],
            include_official_note=True,
            include_attendance=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            files = self.service.generate_invitation(data, temp_dir)
            self.assertEqual(len(files), 3)
            for path in files:
                assert_valid_docx(self, path)

    def test_regular_invitation_generates_supporting_documents(self) -> None:
        data = InvitationFormData(
            invitation_type="biasa",
            number="100/UND-DPRD/VIII/2026",
            letter_date=date(2026, 8, 28),
            meeting_date=date(2026, 9, 1),
            time_text="09.00 WITA s.d. selesai",
            agenda="Rapat pembahasan program kerja",
            signer=self.master.dprd_signers[0],
            meeting_executor="Pimpinan dan Anggota Komisi I",
            meeting_type="Rapat Kerja",
            related_parties=["Kepala Bagian Umum", "Tenaga Ahli Fraksi Nusantara"],
            other_destination_pages=[
                ["Wali Kota Bitung", "Sekretaris Daerah Kota Bitung"],
                ["Kepala Bappeda Kota Bitung"],
            ],
            include_official_note=True,
            include_attendance=True,
            include_related_attendance=True,
            include_secretariat_attendance=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            files = self.service.generate_invitation(data, temp_dir)
            self.assertEqual(len(files), 3)
            for path in files:
                assert_valid_docx(self, path)

    def test_repository_supports_draft_recap_and_unique_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = SIPSRepository(Path(temp_dir) / "sekretariat.db")
            draft_id = repository.save(
                record_type="travel_dprd",
                title="Koordinasi",
                document_number="",
                document_date="2026-08-28",
                event_start="2026-09-01",
                event_end="2026-09-02",
                destination="Manado",
                status="draft",
                author="operator",
                payload={"mode": "dprd"},
            )
            generated_id = repository.save(
                record_type="invitation_regular",
                title="Rapat Kerja",
                document_number="100/UND/VIII/2026",
                document_date="2026-08-28",
                event_start="2026-09-01",
                event_end="2026-09-01",
                destination="Komisi I",
                status="generated",
                author="operator",
                payload={"invitation_type": "biasa"},
                numbers={"nomor_undangan": "100/UND/VIII/2026"},
            )

            self.assertEqual(repository.get(draft_id).status, "draft")
            self.assertEqual(repository.get(generated_id).status, "generated")
            self.assertEqual(len(repository.list(category="travel")), 1)
            self.assertEqual(len(repository.list(category="invitation", search="rapat")), 1)
            self.assertEqual(
                repository.dashboard_stats(),
                {"travel": 0, "plenary": 0, "regular": 1, "drafts": 1},
            )
            with self.assertRaisesRegex(ValueError, "sudah digunakan"):
                repository.validate_numbers({"nomor_undangan": "100/und/viii/2026"})
            repository.validate_numbers(
                {"nomor_undangan": "100/UND/VIII/2026"},
                generated_id,
            )
            with self.assertRaisesRegex(ValueError, "dua jenis dokumen"):
                repository.validate_numbers({"a": "NOMOR-1", "b": "nomor-1"})
            self.assertTrue(repository.delete_draft(draft_id))
            self.assertIsNone(repository.get(draft_id))

    def test_shell_uses_real_sips_pages_not_placeholders(self) -> None:
        shell_source = (
            Path(__file__).parents[1]
            / "src"
            / "sekretariat_app"
            / "ui"
            / "shell.py"
        ).read_text(encoding="utf-8")
        self.assertIn('TravelPage("dprd"', shell_source)
        self.assertIn('TravelPage("setwan"', shell_source)
        self.assertIn('InvitationPage("paripurna"', shell_source)
        self.assertIn('InvitationPage("biasa"', shell_source)
        self.assertNotIn("ModuleWorkspacePage(", shell_source)
        self.assertNotIn("= RecapPage(", shell_source)

    def test_travel_and_invitation_pages_use_automatic_live_preview(self) -> None:
        page_source = (
            Path(__file__).parents[1]
            / "src"
            / "sekretariat_app"
            / "ui"
            / "pages"
            / "sips.py"
        ).read_text(encoding="utf-8")
        preview_source = (
            Path(__file__).parents[1]
            / "src"
            / "sekretariat_app"
            / "ui"
            / "live_preview.py"
        ).read_text(encoding="utf-8")
        converter_source = (
            Path(__file__).parents[1]
            / "src"
            / "sekretariat_app"
            / "sips"
            / "preview.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(page_source.count("self.live_preview = LiveDocumentPreview()"), 2)
        self.assertEqual(page_source.count("def _schedule_live_preview"), 2)
        self.assertNotIn('QPushButton("Pratinjau")', page_source)
        self.assertIn("class _LivePreviewWorker(QThread)", preview_source)
        self.assertIn("self._timer.setInterval(900)", preview_source)
        self.assertIn("$word.Visible=$false;$word.DisplayAlerts=0", converter_source)
        self.assertIn('"}finally{"', converter_source)


if __name__ == "__main__":
    unittest.main()
