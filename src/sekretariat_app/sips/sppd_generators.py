"""
Generator dokumen SPPD (Surat Perintah Perjalanan Dinas / SPD) halaman
depan & belakang, satu dokumen per orang yang kemudian digabung jadi satu
file multi-halaman per kelompok (DPRD/ASN).
"""
import os
import shutil
import tempfile

from docxtpl import DocxTemplate

from sekretariat_app.sips.text_utils import extract_city_name, increment_nomor_spd, is_in_jabodetabek
from sekretariat_app.sips.docx_utils import _combine_word_pages


def _build_person_sppd_context(ctx, person, nomor_spd_str, destinations, transport):
    p_ctx = ctx.copy()
    p_ctx["pelaksana_dprd_sppd"] = person.get('nama', '-')
    p_ctx["jabatan_pelaksana_sppd"] = person.get('jabatan', '-')
    p_ctx["nomor_surat_sppd"] = nomor_spd_str
    p_ctx["jenis_perjalanan_sppd"] = ctx.get("jenis_perjalanan", "")
    p_ctx["transportasi_sppd"] = transport

    city_names = [extract_city_name(d) for d in destinations]
    p_ctx["tujuan_bertugas_sppd"] = ", ".join(city_names)

    if any(is_in_jabodetabek(c) for c in city_names):
        tujuan_awal = "Kota Jakarta"
    else:
        tujuan_awal = city_names[0] if city_names else "-"
    p_ctx["tujuan_awal_sppd_belakang"] = tujuan_awal
    p_ctx["tanggal_mulai_sppd"] = ctx.get("tanggal_mulai", "")
    p_ctx["tanggal_akhir_sppd"] = ctx.get("tanggal_akhir", "")
    p_ctx["tanggal_surat_sppd"] = ctx.get("tanggal_surat", "")
    p_ctx["materi_tugas_sppd"] = ctx.get("materi_tugas", "")
    p_ctx["tanggal_mulai_sppd_belakang"] = ctx.get("tanggal_mulai", "")
    p_ctx["tanggal_akhir_sppd_belakang"] = ctx.get("tanggal_akhir", "")
    return p_ctx

def buat_sppd_dprd(spd_depan_template, spd_belakang_template, ctx, sel_dprd, destinations, out_depan, out_belakang):
    import tempfile as tmpmod
    tmpdir = tmpmod.mkdtemp()
    depan_files = []
    belakang_files = []
    nomor_dprd = ctx.get('nomor_spd_dprd', ctx.get('nomor_spd', ''))
    transport = ctx.get("transportasi_otomatis", "Mobil")

    for idx, person in enumerate(sel_dprd):
        p_ctx = _build_person_sppd_context(ctx, person, nomor_dprd, destinations, transport)
        if os.path.exists(spd_depan_template):
            doc_d = DocxTemplate(spd_depan_template)
            doc_d.render(p_ctx)
            tmp = os.path.join(tmpdir, f"dprd_depan_{idx}.docx")
            doc_d.save(tmp)
            depan_files.append(tmp)
        if os.path.exists(spd_belakang_template):
            doc_b = DocxTemplate(spd_belakang_template)
            doc_b.render(p_ctx)
            tmp = os.path.join(tmpdir, f"dprd_belakang_{idx}.docx")
            doc_b.save(tmp)
            belakang_files.append(tmp)

    if depan_files: _combine_word_pages(depan_files, out_depan)
    if belakang_files: _combine_word_pages(belakang_files, out_belakang)
    shutil.rmtree(tmpdir, ignore_errors=True)

def buat_sppd_asn(spd_depan_template, spd_belakang_template, ctx, sel_asn, destinations, out_depan, out_belakang):
    import tempfile as tmpmod
    tmpdir = tmpmod.mkdtemp()
    depan_files = []
    belakang_files = []
    nomor_asn_base = ctx.get('nomor_spd_asn', ctx.get('nomor_spd', ''))
    transport = ctx.get("transportasi_otomatis", "Mobil")

    for idx, person in enumerate(sel_asn):
        nomor_asn = increment_nomor_spd(nomor_asn_base, idx)
        p_ctx = _build_person_sppd_context(ctx, person, nomor_asn, destinations, transport)
        if os.path.exists(spd_depan_template):
            doc_d = DocxTemplate(spd_depan_template)
            doc_d.render(p_ctx)
            tmp = os.path.join(tmpdir, f"asn_depan_{idx}.docx")
            doc_d.save(tmp)
            depan_files.append(tmp)
        if os.path.exists(spd_belakang_template):
            doc_b = DocxTemplate(spd_belakang_template)
            doc_b.render(p_ctx)
            tmp = os.path.join(tmpdir, f"asn_belakang_{idx}.docx")
            doc_b.save(tmp)
            belakang_files.append(tmp)

    if depan_files: _combine_word_pages(depan_files, out_depan)
    if belakang_files: _combine_word_pages(belakang_files, out_belakang)
    shutil.rmtree(tmpdir, ignore_errors=True)
