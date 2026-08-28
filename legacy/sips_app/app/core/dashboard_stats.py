"""
Agregasi statistik untuk halaman Dashboard.

Semua fungsi di sini murni membaca ``history_data`` (struktur yang sama
dipakai oleh Riwayat Surat -- lihat app/data/history_repository.py) dan
mengembalikan angka/list siap-pakai untuk kartu ringkasan & grafik di
app/ui/dashboard_window.py. Tidak ada state tersimpan di modul ini supaya
mudah dites dan dipanggil ulang kapan saja data berubah (surat baru
dibuat, dsb).

Struktur ringkas 1 entri "perjalanan_dinas" (lihat main_window.build_context):
    nomor_surat, nomor_spd_dprd, nomor_spd_asn,
    tujuan_bertugas_list: [str, ...]                  -> kab/kota tujuan
    dprd_terpilih: ["Nama||Kategori", ...]             -> anggota DPRD + kategori AKD
    asn_terpilih: ["Nama", ...]                        -> ASN pendamping (mode DPRD)
    pelaksana_terpilih / pendamping_terpilih: ["Nama"] -> ASN (mode Setwan)

Struktur ringkas 1 entri "undangan_rapat":
    tipe: "paripurna" | "biasa"
"""
from collections import Counter


def _clean(text):
    return (text or "").strip()


def compute_dashboard_stats(history_data):
    pd_data = (history_data or {}).get("perjalanan_dinas", {}) or {}
    ur_data = (history_data or {}).get("undangan_rapat", {}) or {}

    total_surat_tugas = len(pd_data)

    total_spd = 0
    kabkota_counter = Counter()
    kategori_counter = Counter()
    dprd_counter = Counter()
    asn_counter = Counter()

    for rec in pd_data.values():
        if _clean(rec.get("nomor_spd_dprd")) or _clean(rec.get("nomor_spd_asn")):
            total_spd += 1

        for kota in (rec.get("tujuan_bertugas_list") or []):
            kota = _clean(kota)
            if kota:
                kabkota_counter[kota] += 1

        for entry in (rec.get("dprd_terpilih") or []):
            entry = entry or ""
            if "||" in entry:
                nama, kategori = entry.split("||", 1)
            else:
                nama, kategori = entry, "Lainnya"
            nama = _clean(nama)
            kategori = _clean(kategori) or "Lainnya"
            if nama:
                dprd_counter[nama] += 1
                kategori_counter[kategori] += 1

        for nama in (rec.get("asn_terpilih") or []):
            nama = _clean(nama)
            if nama:
                asn_counter[nama] += 1
                kategori_counter["Pendamping ASN"] += 1

        for nama in (rec.get("pelaksana_terpilih") or []):
            nama = _clean(nama)
            if nama:
                asn_counter[nama] += 1
                kategori_counter["Pelaksana ASN (Setwan)"] += 1

        for nama in (rec.get("pendamping_terpilih") or []):
            nama = _clean(nama)
            if nama:
                asn_counter[nama] += 1
                kategori_counter["Pendamping ASN (Setwan)"] += 1

    total_paripurna = sum(1 for r in ur_data.values() if _clean(r.get("tipe")) == "paripurna")
    total_biasa = sum(1 for r in ur_data.values() if _clean(r.get("tipe")) == "biasa")

    return {
        "total_surat_tugas": total_surat_tugas,
        "total_spd": total_spd,
        "total_undangan_paripurna": total_paripurna,
        "total_undangan_biasa": total_biasa,
        "top_kabkota": kabkota_counter.most_common(8),
        "top_kategori": kategori_counter.most_common(8),
        "top_dprd": dprd_counter.most_common(10),
        "top_asn": asn_counter.most_common(10),
    }
