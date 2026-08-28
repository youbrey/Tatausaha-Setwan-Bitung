"""
Generator "Lembar Pengajuan Naskah Dinas" (naskah_dinas_rapat.docx) untuk
Undangan Rapat Biasa & Undangan Paripurna.

Template Word-nya adalah file resmi kantor (NASKAH_DINAS_RAPAT.docx) yang
SUDAH berisi 3 placeholder docxtpl siap pakai -- generator ini murni
memetakan data yang SUDAH diisi di formulir Undangan (nomor surat,
tanggal, isi/perihal) ke 3 variabel itu, supaya pengguna tidak perlu
mengetik ulang apa pun.

Variabel docxtpl di template (JANGAN diubah namanya kecuali template Word
juga ikut diedit ulang):
    nomor_surat_rapat_naskah_dinas         -> nomor surat undangan
    tgl_surat_rapat_biasa_naskah_dinas     -> tanggal surat undangan
    isi_surat_rapat_biasa_naskah_dinas     -> ringkasan perihal rapat
"""
import os

from docxtpl import DocxTemplate

from sekretariat_app.sips.logging_util import safe_log


def build_context_naskah_dinas(nomor_surat, tanggal_surat, perihal_rapat):
    perihal_rapat = (perihal_rapat or "").strip().rstrip(".")
    if perihal_rapat:
        isi = f"Mohon diterbitkan Surat Undangan Rapat perihal {perihal_rapat}."
    else:
        isi = "Mohon diterbitkan Surat Undangan Rapat."
    return {
        "nomor_surat_rapat_naskah_dinas": nomor_surat or "",
        "tgl_surat_rapat_biasa_naskah_dinas": tanggal_surat or "",
        "isi_surat_rapat_biasa_naskah_dinas": isi,
    }


def generate_naskah_dinas(template_path, out_path, nomor_surat, tanggal_surat, perihal_rapat):
    """Render & simpan Lembar Pengajuan Naskah Dinas ke `out_path`."""
    ctx = build_context_naskah_dinas(nomor_surat, tanggal_surat, perihal_rapat)
    try:
        tpl = DocxTemplate(template_path)
        tpl.render(ctx)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        tpl.save(out_path)
        return out_path
    except Exception as e:
        safe_log(f"Gagal membuat Naskah Dinas: {e}")
        raise
