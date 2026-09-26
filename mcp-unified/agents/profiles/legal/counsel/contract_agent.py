"""
contract_agent.py - Modul Contract Vetting & Risk Assessment (JF Analis Hukum)
================================================================================
Melakukan audit dan pengujian yuridis atas draf Kontrak Pengadaan Barang/Jasa (PBJ)
Pemerintah (Perpres No. 16/2018 jo Perpres No. 12/2021) serta Perjanjian Kerja Sama (PKS)
Pemerintah Daerah (Permendagri No. 22/2020).

Fokus pada mitigasi temuan audit BPK/APIP, validitas klausul ganti rugi/denda keterlambatan,
penyampingan Pasal 1266/1267 KUHPerdata, serta kepastian forum penyelesaian sengketa.
"""

from typing import List, Dict, Any, Optional
import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ContractRiskItem:
    kategori_klausul: str  # 'denda_keterlambatan', 'force_majeure', 'pengakhiran_kontrak', 'sengketa', 'jaminan'
    nomor_pasal: str
    teks_klausul: str
    tingkat_risiko: str  # 'TINGGI', 'SEDANG', 'RENDAH'
    dasar_regulasi: str
    analisis_risiko: str
    rekomendasi_revisi: str


@dataclass
class ContractVettingResult:
    judul_kontrak: str
    nomor_draf: str
    para_pihak: List[str]
    nilai_kontrak: float
    jenis_kontrak: str  # 'PBJ_PEMERINTAH', 'PKS_DAERAH', 'MOU'
    skor_kesehatan_kontrak: int  # 0 - 100
    status_kelayakan: str  # 'LAYAK_TANDATANGAN', 'LAYAK_DENGAN_REVISI', 'TIDAK_LAYAK'
    temuan_risiko: List[ContractRiskItem]
    checklist_klausul_wajib: Dict[str, bool]
    celah_audit_bpk_apip: List[str]
    executive_summary: str


class ContractVettingAgent:
    """
    Engine Vetting Kontrak Pemerintah untuk JF Analis Hukum.
    """

    KLAUSUL_WAJIB_PBJ = {
        "identitas_para_pihak": "Identitas lengkap PPK dan Penyedia yang sah",
        "lingkup_pekerjaan": "Spesifikasi teknis, KAK, dan volume pekerjaan yang terukur",
        "nilai_dan_pembayaran": "Nilai kontrak termasuk PPN dan tata cara termin/prestasi",
        "hak_dan_kewajiban": "Rincian hak dan kewajiban masing-masing pihak",
        "jangka_waktu_pelaksanaan": "Masa berlaku kontrak dan jadwal penyelesaian pekerjaan",
        "jaminan_pengadaan": "Jaminan Pelaksanaan / Jaminan Uang Muka / Jaminan Pemeliharaan",
        "sanksi_dan_denda": "Ketentuan denda keterlambatan 1/1000 per hari (Perpres PBJ)",
        "keadaan_kahar": "Definisi, prosedur pemberitahuan, dan penanganan force majeure",
        "pengakhiran_kontrak": "Penyampingan Pasal 1266 & 1267 KUHPerdata untuk pemutusan sepihak",
        "penyelesaian_sengketa": "Pilihan forum arbitrase / mediasi / pengadilan negeri yang tegas"
    }

    def __init__(self, jenjang: str = "Ahli Madya"):
        self.jenjang = jenjang

    def audit_draf_kontrak(
        self,
        judul_kontrak: str,
        nomor_draf: str,
        para_pihak: List[str],
        nilai_kontrak: float,
        jenis_kontrak: str,
        draf_pasal: Dict[str, str]  # e.g., {'Pasal 10': 'Dalam hal terjadi keterlambatan...'}
    ) -> ContractVettingResult:
        """
        Melakukan audit komprehensif terhadap draf klausul kontrak.
        """
        temuan: List[ContractRiskItem] = []
        checklist = {k: False for k in self.KLAUSUL_WAJIB_PBJ.keys()}
        celah_bpk: List[str] = []

        total_text = " ".join(draf_pasal.values()).lower()

        # 1. Audit Checklist Klausul Wajib
        if any(w in total_text for w in ["pihak pertama", "pejabat pembuat komitmen", "ppk"]):
            checklist["identitas_para_pihak"] = True
        if any(w in total_text for w in ["ruang lingkup", "lingkup pekerjaan", "spesifikasi"]):
            checklist["lingkup_pekerjaan"] = True
        if any(w in total_text for w in ["nilai kontrak", "harga kontrak", "tata cara pembayaran", "termin"]):
            checklist["nilai_dan_pembayaran"] = True
        if any(w in total_text for w in ["hak", "kewajiban"]):
            checklist["hak_dan_kewajiban"] = True
        if any(w in total_text for w in ["jangka waktu", "hari kalender"]):
            checklist["jangka_waktu_pelaksanaan"] = True
        if any(w in total_text for w in ["jaminan pelaksanaan", "jaminan uang muka", "jaminan pemeliharaan"]):
            checklist["jaminan_pengadaan"] = True
        if any(w in total_text for w in ["denda", "1/1000", "seperseribu"]):
            checklist["sanksi_dan_denda"] = True
        if any(w in total_text for w in ["keadaan kahar", "force majeure"]):
            checklist["keadaan_kahar"] = True
        if "1266" in total_text or "1267" in total_text or "mengesampingkan" in total_text:
            checklist["pengakhiran_kontrak"] = True
        if any(w in total_text for w in ["penyelesaian sengketa", "arbitrase", "pengadilan negeri", "layanan penyelesaian sengketa"]):
            checklist["penyelesaian_sengketa"] = True

        # 2. Audit Spesifik Per Pasal
        for pasal_nomor, isi in draf_pasal.items():
            isi_lower = isi.lower()

            # Audit Denda Keterlambatan
            if "denda" in isi_lower or "keterlambatan" in isi_lower:
                if "1/1000" not in isi_lower and "seperseribu" not in isi_lower:
                    temuan.append(ContractRiskItem(
                        kategori_klausul="denda_keterlambatan",
                        nomor_pasal=pasal_nomor,
                        teks_klausul=isi,
                        tingkat_risiko="TINGGI",
                        dasar_regulasi="Pasal 79 ayat (4) Perpres No. 16/2018 jo Perpres No. 12/2021",
                        analisis_risiko="Besaran denda tidak mengacu standar baku 1/1000 per hari keterlambatan, berpotensi memicu temuan kerugian negara oleh BPK.",
                        rekomendasi_revisi="Rumuskan: 'Besarnya denda keterlambatan adalah 1/1000 (satu permil) per hari keterlambatan dari nilai kontrak atau bagian kontrak sebelum PPN.'"
                    ))
                if "maksimal" in isi_lower and "50" not in isi_lower and "9%" not in isi_lower:
                    temuan.append(ContractRiskItem(
                        kategori_klausul="denda_keterlambatan",
                        nomor_pasal=pasal_nomor,
                        teks_klausul=isi,
                        tingkat_risiko="SEDANG",
                        dasar_regulasi="Perlem LKPP No. 12/2021",
                        analisis_risiko="Tidak ada batasan pemberian kesempatan maksimal 50 hari kalender dengan denda.",
                        rekomendasi_revisi="Tambahkan klausul batas waktu pemberian kesempatan penyelesaian pekerjaan maksimal 50 hari kalender."
                    ))

            # Audit Pengakhiran Kontrak (Pasal 1266 KUHPerdata)
            if "pemutusan" in isi_lower or "pengakhiran" in isi_lower:
                if "1266" not in isi_lower:
                    temuan.append(ContractRiskItem(
                        kategori_klausul="pengakhiran_kontrak",
                        nomor_pasal=pasal_nomor,
                        teks_klausul=isi,
                        tingkat_risiko="TINGGI",
                        dasar_regulasi="Pasal 1266 & 1267 KUHPerdata",
                        analisis_risiko="Tidak mencantumkan klausul penyampingan Pasal 1266 & 1267 KUHPerdata. Hal ini mewajibkan PPK meminta putusan pengadilan terlebih dahulu untuk memutuskan kontrak sepihak jika rekanan cidera janji.",
                        rekomendasi_revisi="Wajib ditambahkan: 'Para Pihak sepakat untuk mengesampingkan berlakunya ketentuan Pasal 1266 dan Pasal 1267 Kitab Undang-Undang Hukum Perdata dalam hal pemutusan perjanjian ini.'"
                    ))

            # Audit Penyelesaian Sengketa
            if "sengketa" in isi_lower or "perselisihan" in isi_lower:
                if "musyawarah" in isi_lower and not any(w in isi_lower for w in ["pengadilan negeri", "arbitrase", "bani", "lkpp"]):
                    temuan.append(ContractRiskItem(
                        kategori_klausul="sengketa",
                        nomor_pasal=pasal_nomor,
                        teks_klausul=isi,
                        tingkat_risiko="TINGGI",
                        dasar_regulasi="Pasal 85 Perpres No. 16/2018 jo Perpres No. 12/2021",
                        analisis_risiko="Pilihan forum penyelesaian kebuntuan hukum tidak tegas jika musyawarah mufakat gagal.",
                        rekomendasi_revisi="Tegaskan forum lanjutan: 'Apabila musyawarah tidak tercapai dalam 30 hari, para pihak sepakat memilih domisili hukum di Pengadilan Negeri [Wilayah] atau melalui Layanan Penyelesaian Sengketa Kontrak LKPP / BANI.'"
                    ))

            # Audit Force Majeure
            if "kahar" in isi_lower or "force majeure" in isi_lower:
                if "14" not in isi_lower and "hari" not in isi_lower:
                    temuan.append(ContractRiskItem(
                        kategori_klausul="force_majeure",
                        nomor_pasal=pasal_nomor,
                        teks_klausul=isi,
                        tingkat_risiko="SEDANG",
                        dasar_regulasi="Standar Dokumen Pemilihan LKPP",
                        analisis_risiko="Tidak ada batas waktu pelaporan keadaan kahar, membuka ruang klaim fiktif di kemudian hari.",
                        rekomendasi_revisi="Tambahkan batas waktu: 'Penyedia wajib memberitahukan keadaan kahar secara tertulis paling lambat 14 (empat belas) hari kalender sejak terjadinya peristiwa.'"
                    ))

        # 3. Analisis Potensi Temuan BPK/APIP
        if not checklist["jaminan_pengadaan"] and nilai_kontrak > 200_000_000:
            celah_bpk.append("Nilai kontrak di atas Rp 200 Juta wajib melampirkan Jaminan Pelaksanaan sebesar 5% dari nilai kontrak (Pasal 30 Perpres 16/2018).")
        if not checklist["pengakhiran_kontrak"]:
            celah_bpk.append("Ketiadaan penyampingan Pasal 1266 KUHPerdata menghambat eksekusi jaminan pelaksanaan dan pencairan sisa anggaran jika terjadi wanprestasi.")
        if any(t.tingkat_risiko == "TINGGI" and t.kategori_klausul == "denda_keterlambatan" for t in temuan):
            celah_bpk.append("Klausul denda yang tidak presisi merupakan objek pemeriksaan rutin BPK yang berujung pada penetapan Tuntutan Ganti Rugi (TGR).")

        # 4. Scoring Kesehatan Kontrak
        base_score = 100
        for t in temuan:
            if t.tingkat_risiko == "TINGGI":
                base_score -= 25
            elif t.tingkat_risiko == "SEDANG":
                base_score -= 10
            else:
                base_score -= 5

        # Pinalti jika klausul wajib belum lengkap
        missing_count = sum(1 for v in checklist.values() if not v)
        base_score -= (missing_count * 5)
        score = max(0, min(100, base_score))

        if score >= 80 and not any(t.tingkat_risiko == "TINGGI" for t in temuan):
            status = "LAYAK_TANDATANGAN"
        elif score >= 50:
            status = "LAYAK_DENGAN_REVISI"
        else:
            status = "TIDAK_LAYAK"

        # 5. Executive Summary
        exec_summary = (
            f"RINGKASAN EKSEKUTIF TELAAHAN KONTRAK / PKS (VETTING)\n"
            f"Nomor Draf: {nomor_draf} | Judul: {judul_kontrak}\n"
            f"Nilai Kontrak: Rp {nilai_kontrak:,.2f} | Jenis: {jenis_kontrak}\n"
            f"----------------------------------------------------------------------\n"
            f"1. SKOR KELAYAKAN YURIDIS: {score}/100 ({status})\n"
            f"2. TEMUAN RISIKO KRITIS (HIGH RISK):\n"
            + "\n".join([f"   - [{t.nomor_pasal}] {t.analisis_risiko}" for t in temuan if t.tingkat_risiko == 'TINGGI']) + (
                "\n   (Tidak ditemukan risiko tingkat tinggi)" if not any(t.tingkat_risiko == 'TINGGI' for t in temuan) else ""
            ) + "\n"
            f"3. STATUS KLAUSUL WAJIB:\n"
            f"   - Terpenuhi: {sum(1 for v in checklist.values() if v)} / {len(checklist)} Klausul Standar\n"
            f"4. POTENSI TEMUAN AUDIT APIP / BPK:\n"
            + "\n".join([f"   * {c}" for c in celah_bpk]) + (
                "\n   * Minim potensi temuan jika revisi klausul dipenuhi." if not celah_bpk else ""
            ) + "\n"
            f"5. REKOMENDASI TINDAKAN:\n"
            f"   {'Lakukan perbaikan redaksional pasal berisiko tinggi sebelum penandatanganan kontrak definitif.' if status != 'LAYAK_TANDATANGAN' else 'Draf kontrak dapat dilanjutkan ke tahap penandatanganan.'}"
        )

        return ContractVettingResult(
            judul_kontrak=judul_kontrak,
            nomor_draf=nomor_draf,
            para_pihak=para_pihak,
            nilai_kontrak=nilai_kontrak,
            jenis_kontrak=jenis_kontrak,
            skor_kesehatan_kontrak=score,
            status_kelayakan=status,
            temuan_risiko=temuan,
            checklist_klausul_wajib=checklist,
            celah_audit_bpk_apip=celah_bpk,
            executive_summary=exec_summary
        )

    def render_markdown(self, result: ContractVettingResult) -> str:
        """
        Merender laporan telaahan yuridis kontrak berstandar ASN.
        """
        lines = []
        lines.append(f"# NOTA TELAAHAN YURIDIS DRAF KONTRAK / KERJASAMA (VETTING)")
        lines.append(f"**Nomor Dokumen:** {result.nomor_draf}")
        lines.append(f"**Judul Kontrak:** {result.judul_kontrak}")
        lines.append(f"**Para Pihak:** {', '.join(result.para_pihak)}")
        lines.append(f"**Nilai Kontrak:** Rp {result.nilai_kontrak:,.2f}")
        lines.append(f"**Jenis Perjanjian:** `{result.jenis_kontrak}`")
        lines.append(f"**Jenjang Pemeriksa:** JF Analis Hukum ({self.jenjang})")
        lines.append(f"**Skor Kelayakan Yuridis:** **{result.skor_kesehatan_kontrak} / 100** (`{result.status_kelayakan}`)")
        lines.append(f"\n---\n")

        lines.append(f"## I. HASIL AUDIT KLAUSUL WAJIB STANDAR PEMERINTAH")
        lines.append("| No | Klausul Standar PBJ / PKS | Status Keberadaan | Keterangan Standar |")
        lines.append("|---|---|---|---|")
        for idx, (klausul, status) in enumerate(result.checklist_klausul_wajib.items(), start=1):
            badge = "✅ TERSEDIA" if status else "❌ TIDAK ADA / KURANG"
            ket = self.KLAUSUL_WAJIB_PBJ.get(klausul, "-")
            lines.append(f"| {idx} | {klausul.replace('_', ' ').title()} | {badge} | {ket} |")

        lines.append(f"\n## II. MATRIKS IDENTIFIKASI RISIKO & REKOMENDASI REVISI PASAL")
        if not result.temuan_risiko:
            lines.append("*Seluruh pasal yang dianalisis tidak menunjukkan red flag klausul berisiko tinggi.*")
        else:
            lines.append("| Pasal | Kategori | Tingkat Risiko | Dasar Regulasi | Analisis Risiko & Rekomendasi Revisi |")
            lines.append("|---|---|---|---|---|")
            for t in result.temuan_risiko:
                lines.append(
                    f"| **{t.nomor_pasal}** | `{t.kategori_klausul}` | **{t.tingkat_risiko}** | {t.dasar_regulasi} | "
                    f"**Risiko:** {t.analisis_risiko}<br>**Rekomendasi:** *{t.rekomendasi_revisi}* |"
                )

        lines.append(f"\n## III. MITIGASI POTENSI TEMUAN PEMERIKSAAN BPK / APIP")
        if result.celah_audit_bpk_apip:
            for c in result.celah_audit_bpk_apip:
                lines.append(f"- ⚠️ **Peringatan Audit:** {c}")
        else:
            lines.append("- ✅ Draf kontrak telah mengakomodasi ketentuan perlindungan keuangan daerah/negara secara memadai.")

        lines.append(f"\n## IV. KESIMPULAN & REKOMENDASI AKHIR")
        if result.status_kelayakan == "LAYAK_TANDATANGAN":
            lines.append("Draf kontrak dinyatakan **LAYAK DITANDATANGANI** oleh Pejabat Pembuat Komitmen (PPK) / Kepala Daerah.")
        elif result.status_kelayakan == "LAYAK_DENGAN_REVISI":
            lines.append("Draf kontrak dinyatakan **LAYAK DENGAN CATATAN REVISI WAJIB**. Draf wajib dikembalikan kepada penyedia/mitra kerja sama untuk menyelaraskan klausul berisiko tinggi sebelum penandatanganan definitif.")
        else:
            lines.append("Draf kontrak dinyatakan **TIDAK LAYAK**. Terdapat cacat klausul esensial yang dapat merugikan kepentingan hukum dan keuangan pemerintah.")

        lines.append(f"\n---\n")
        lines.append(f"### LAMPIRAN: 1-PAGE EXECUTIVE BRIEFING")
        lines.append(f"```text\n{result.executive_summary}\n```")

        return "\n".join(lines)
