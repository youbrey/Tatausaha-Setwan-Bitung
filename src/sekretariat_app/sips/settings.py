from __future__ import annotations

from importlib.resources import files


def template_path(name: str) -> str:
    return str(files("sekretariat_app.sips.resources.templates").joinpath(name))


def data_path(name: str) -> str:
    return str(files("sekretariat_app.sips.resources.data").joinpath(name))


TEMPLATE_ST_DPRD_BIASA = template_path("surat_tugas_dprd_biasa.docx")
TEMPLATE_ST_DPRD_TABEL = template_path("surat_tugas_dprd_tabel.docx")
TEMPLATE_ST_ASN_BIASA = template_path("surat_tugas_asn_biasa.docx")
TEMPLATE_ST_ASN_TABEL = template_path("surat_tugas_asn_tabel.docx")
TEMPLATE_PEMBERITAHUAN = template_path("pemberitahuan_dprd.docx")
TEMPLATE_PARIPURNA = template_path("rapat_paripurna.docx")
TEMPLATE_RAPAT_BIASA = template_path("rapat_biasa.docx")
TEMPLATE_SPD_DEPAN = template_path("SPD_DPRD.docx")
TEMPLATE_SPD_BELAKANG = template_path("SPD_BELAKANG.docx")
TEMPLATE_DAFTAR_HADIR = template_path("DAFTAR_HADIR_DPRD.docx")
TEMPLATE_NASKAH_DINAS_RAPAT = template_path("naskah_dinas_rapat.docx")
TEMPLATE_DAFTAR_HADIR_PARIPURNA = template_path("daftar_hadir_rapat_paripurna_dprd.docx")
TEMPLATE_DAFTAR_HADIR_PIHAK_TERKAIT = template_path("daftar_hadir_rapat_pihak_terkait.docx")
TEMPLATE_DAFTAR_HADIR_SEKRETARIAT = template_path("daftar_hadir_rapat_sekretariat.docx")
TEMPLATE_DAFTAR_HADIR_TAF = template_path("daftar_hadir_rapat_taf.docx")
MASTER_PERSONNEL_XLSX = data_path("database_dprd_asn.xlsx")

TEMPLATE_DAFTAR_HADIR_RAPAT_MAP = {
    "Pimpinan dan Anggota DPRD Kota Bitung": template_path("daftar_hadir_rapat_paripurna_dprd.docx"),
    "Pimpinan dan Anggota Komisi I": template_path("daftar_hadir_rapat_komisi_1.docx"),
    "Pimpinan dan Anggota Komisi II": template_path("daftar_hadir_rapat_komisi_2.docx"),
    "Pimpinan dan Anggota Komisi III": template_path("daftar_hadir_rapat_komisi_3.docx"),
    "Pimpinan dan Anggota Badan Anggaran": template_path("daftar_hadir_rapat_banggar.docx"),
    "Pimpinan dan Anggota Badan Pembentukan Perda": template_path("daftar_hadir_rapat_bapemperda.docx"),
    "Pimpinan dan Anggota Badan Musyawarah": template_path("daftar_hadir_rapat_banmus.docx"),
}
