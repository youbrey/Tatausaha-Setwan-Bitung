"""
Generator "Daftar Hadir Rapat" untuk Undangan Rapat Biasa & Undangan
Paripurna.

Berbeda dari rencana awal (1 template generik + database roster JSON),
kantor sudah punya template Word RESMI per pelaksana rapat (Komisi I/II/
III, Banggar, Banmus, Bapemperda, Paripurna DPRD, Pihak Terkait,
Sekretariat, TAF) dengan SUSUNAN NAMA SUDAH TERTULIS TETAP di tabelnya
(bukan diisi otomatis dari database) -- jadi generator ini jauh lebih
sederhana: tinggal PILIH file template yang sesuai lalu isi 4 variabel
header (perihal/isi rapat, hari, tanggal, jam). Kalau susunan nama
berubah (mis. ada pergantian anggota Komisi), edit langsung tabel di
file .docx template-nya di resources/templates/ -- TIDAK perlu
mengubah kode ini.

Variabel docxtpl (SAMA di semua template "biasa", beda dikit di
template Paripurna -- lihat is_paripurna):
    Biasa     : isi_surat_rapat_biasa_daftar_hadir, hari,
                tanggal_rapat_biasa_daftar_hadir, jam_rapat_biasa_daftar_hadir
    Paripurna : isi_surat_rapat_paripurna_daftar_hadir, hari,
                tanggal_rapat_paripurna_daftar_hadir, jam_rapat_paripurna_daftar_hadir
"""
import os
import tempfile

from docxtpl import DocxTemplate

from sekretariat_app.sips.logging_util import safe_log
from sekretariat_app.sips.docx_utils import _combine_word_pages


def build_context_daftar_hadir(hari, tanggal, jam, isi_perihal, is_paripurna=False):
    suffix = "paripurna" if is_paripurna else "biasa"
    return {
        "hari": (hari or "").strip(),
        f"tanggal_rapat_{suffix}_daftar_hadir": (tanggal or "").strip(),
        f"jam_rapat_{suffix}_daftar_hadir": (jam or "").strip(),
        f"isi_surat_rapat_{suffix}_daftar_hadir": (isi_perihal or "").strip(),
    }


def _render_satu_lembar(template_path, ctx, tmp_dir):
    tpl = DocxTemplate(template_path)
    tpl.render(ctx)
    out = os.path.join(tmp_dir, f"_dh_{os.path.basename(template_path)}")
    tpl.save(out)
    return out


def generate_daftar_hadir_rapat(
    template_utama, out_path, hari, tanggal, jam, isi_perihal,
    is_paripurna=False, lembar_tambahan=None,
):
    """Render Daftar Hadir & simpan ke `out_path`.

    Args:
        template_utama: path template pelaksana rapat utama (mis. hasil
            lookup TEMPLATE_DAFTAR_HADIR_RAPAT_MAP[pelaksana_rapat]).
        lembar_tambahan: list path template TAMBAHAN yang mau digabung
            SETELAH lembar utama jadi satu file (mis. Pihak Terkait,
            Sekretariat, TAF) -- boleh kosong/None. Tiap lembar tambahan
            memakai konteks (hari/tanggal/jam/isi) YANG SAMA dengan lembar
            utama, karena satu Daftar Hadir mewakili SATU rapat yang sama.
    """
    ctx = build_context_daftar_hadir(hari, tanggal, jam, isi_perihal, is_paripurna)
    tmp_dir = tempfile.mkdtemp(prefix="sips_daftar_hadir_")
    try:
        files = [_render_satu_lembar(template_utama, ctx, tmp_dir)]
        for tpl_path in (lembar_tambahan or []):
            if tpl_path and os.path.exists(tpl_path):
                files.append(_render_satu_lembar(tpl_path, ctx, tmp_dir))

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        if len(files) > 1:
            _combine_word_pages(files, out_path)
        else:
            import shutil
            shutil.copy(files[0], out_path)
        return out_path
    except Exception as e:
        safe_log(f"Gagal membuat Daftar Hadir Rapat: {e}")
        raise
    finally:
        for f in os.listdir(tmp_dir):
            try:
                os.remove(os.path.join(tmp_dir, f))
            except OSError:
                pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass
