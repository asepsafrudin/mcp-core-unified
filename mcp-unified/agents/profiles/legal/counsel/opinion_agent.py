"""
opinion_agent.py - Modul Legal Opinion Generator & AUPB Shield (JF Analis Hukum)
==================================================================================
Mengimplementasikan penalaran hukum deduktif berbasis metode IRAC (Issue, Rule,
Application, Conclusion), audit kepatuhan Asas-Asas Umum Pemerintahan yang Baik
(AUPB - UU No. 30/2014), pengujian batas diskresi pejabat administrasi, serta
deteksi dini risiko tindak pidana korupsi/kerugian negara (UU No. 31/1999 jo UU No. 20/2001).

Standar BPHN & PermenPAN-RB No. 51/2020.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LegalIssue:
    issue_id: str
    pertanyaan_hukum: str
    kategori: str  # 'kewenangan', 'prosedur', 'substansi', 'kontrak', 'keuangan'
    pihak_terkait: List[str]


@dataclass
class RuleReference:
    peraturan: str
    pasal: str
    bunyi_norma: str
    tingkat_hierarki: str  # 'UUD 1945', 'UU/Perppu', 'PP', 'Perpres', 'Permen', 'Perda'
    status_keberlakuan: str = "BERLAKU"


@dataclass
class AUPBComplianceCheck:
    asas: str
    dasar_hukum: str  # e.g., 'Pasal 10 ayat (1) huruf a UU 30/2014'
    status: str  # 'PATUH', 'POTENSI_PELANGGARAN', 'TIDAK_TERAPLIKASI'
    catatan_analisis: str
    skor_kepatuhan: int  # 0 - 100


@dataclass
class DiskresiAssessment:
    apakah_ada_dasar_diskresi: bool
    alasan_diskresi: str  # 'peraturan_belum_mengatur', 'peraturan_tidak_lengkap', 'stagnasi_pemerintahan'
    persyaratan_terpenuhi: List[str]
    potensi_melampaui_wewenang: bool
    potensi_mencampuradukkan_wewenang: bool
    potensi_sewenang_wenang: bool


@dataclass
class LegalOpinionResult:
    judul_kasus: str
    pemohon_pendapat: str
    nomor_memo: str
    tanggal: str
    issues: List[LegalIssue]
    rules: List[RuleReference]
    irac_analysis: Dict[str, Any]
    aupb_shield_audit: List[AUPBComplianceCheck]
    diskresi_assessment: Optional[DiskresiAssessment]
    risiko_kerugian_negara: Dict[str, Any]
    kesimpulan_dan_rekomendasi: Dict[str, Any]
    executive_summary: str


class LegalOpinionAgent:
    """
    Engine Analisis Hukum Opini Legal berbasis IRAC dan AUPB Shield.
    Representasi keahlian JF Analis Hukum (BPHN / Kemenkumham / KemenPAN-RB).
    """

    # 8 AUPB Baku sesuai Pasal 10 ayat (1) UU No. 30 Tahun 2014
    AUPB_LIST = [
        ("Kepastian Hukum", "Pasal 10 ayat (1) huruf a UU 30/2014", "Mengutamakan landasan peraturan perundang-undangan, kepatutan, keajegan, dan keadilan."),
        ("Kemanfaatan", "Pasal 10 ayat (1) huruf b UU 30/2014", "Manfaat yang harus diperhatikan secara seimbang antara kepentingan individu dan masyarakat."),
        ("Ketidakberpihakan", "Pasal 10 ayat (1) huruf c UU 30/2014", "Kewajiban mempertimbangkan kepentingan para pihak secara objektif dan tidak diskriminatif."),
        ("Kecermatan", "Pasal 10 ayat (1) huruf d UU 30/2014", "Kewajiban meneliti semua fakta yang relevan dan mendasarkan keputusan pada dokumen yang sah."),
        ("Tidak Menyalahgunakan Kewenangan", "Pasal 10 ayat (1) huruf e UU 30/2014", "Kewajiban tidak melampaui, mencampuradukkan, dan/atau bertindak sewenang-wenang (Pasal 17-18)."),
        ("Keterbukaan", "Pasal 10 ayat (1) huruf f UU 30/2014", "Memberikan akses informasi yang benar, jujur, dan tidak diskriminatif kepada masyarakat."),
        ("Kepentingan Umum", "Pasal 10 ayat (1) huruf g UU 30/2014", "Mendahulukan kesejahteraan umum dengan cara yang aspiratif, akomodatif, dan selektif."),
        ("Pelayanan yang Baik", "Pasal 10 ayat (1) huruf h UU 30/2014", "Memberikan pelayanan yang tepat waktu, prosedur sederhana, dan biaya yang transparan."),
    ]

    def __init__(self, jenjang: str = "Ahli Madya"):
        self.jenjang = jenjang

    def evaluate_aupb_compliance(
        self,
        tindakan_pemerintah: str,
        fakta_kasus: Dict[str, Any]
    ) -> List[AUPBComplianceCheck]:
        """
        Menguji tindakan / keputusan pejabat terhadap 8 Asas Umum Pemerintahan yang Baik.
        """
        results = []
        doc_count = len(fakta_kasus.get("dokumen_pendukung", []))
        has_prosedur = fakta_kasus.get("ada_sop_baku", True)
        ada_konflik = fakta_kasus.get("ada_konflik_kepentingan", False)
        ada_kajian = fakta_kasus.get("ada_kajian_teknis", True)

        for asas_nama, dasar_hukum, deskripsi in self.AUPB_LIST:
            status = "PATUH"
            skor = 100
            catatan = f"Tindakan selaras dengan prinsip {asas_nama}."

            if asas_nama == "Kecermatan":
                if doc_count < 2 or not ada_kajian:
                    status = "POTENSI_PELANGGARAN"
                    skor = 40
                    catatan = "Minim dokumen pendukung atau belum ada kajian teknis komprehensif sebelum penetapan."
            elif asas_nama == "Ketidakberpihakan":
                if ada_konflik:
                    status = "POTENSI_PELANGGARAN"
                    skor = 20
                    catatan = "Terindikasi adanya benturan kepentingan (conflict of interest) dalam pengambilan keputusan."
            elif asas_nama == "Kepastian Hukum":
                if not has_prosedur:
                    status = "POTENSI_PELANGGARAN"
                    skor = 50
                    catatan = "Keputusan diambil tanpa merujuk SOP baku atau landasan delegasi wewenang yang tegas."
            elif asas_nama == "Tidak Menyalahgunakan Kewenangan":
                if fakta_kasus.get("indikasi_melampaui_tenggang_waktu", False):
                    status = "POTENSI_PELANGGARAN"
                    skor = 45
                    catatan = "Terdapat indikasi pengambilan keputusan melampaui masa jabatan atau wewenang delegasi."

            results.append(AUPBComplianceCheck(
                asas=asas_nama,
                dasar_hukum=dasar_hukum,
                status=status,
                catatan_analisis=catatan,
                skor_kepatuhan=skor
            ))

        return results

    def assess_diskresi(
        self,
        latar_belakang: str,
        alasan: str,
        ada_persetujuan_atasan: bool = False
    ) -> DiskresiAssessment:
        """
        Menguji keabsahan penggunaan hak Diskresi Pejabat Pemerintahan (Pasal 22-30 UU 30/2014).
        """
        syarat = []
        if "tujuan" in latar_belakang.lower() or "kelancaran" in latar_belakang.lower():
            syarat.append("Sesuai dengan tujuan diskresi (kelancaran penyelenggaraan pemerintahan)")
        if "darurat" in latar_belakang.lower() or "mendesak" in latar_belakang.lower():
            syarat.append("Menangani keadaan mendesak untuk kepentingan umum")
        if ada_persetujuan_atasan:
            syarat.append("Telah memperoleh persetujuan tertulis dari atasan pejabat (Pasal 25 ayat (1))")

        potensi_lampau = not ada_persetujuan_atasan and ("anggaran" in latar_belakang.lower() or "keuangan" in latar_belakang.lower())
        potensi_campur = "tupoksi_lain" in latar_belakang.lower()
        potensi_wenang2 = len(syarat) == 0

        return DiskresiAssessment(
            apakah_ada_dasar_diskresi=alasan in ["peraturan_belum_mengatur", "peraturan_tidak_lengkap", "stagnasi_pemerintahan"],
            alasan_diskresi=alasan,
            persyaratan_terpenuhi=syarat,
            potensi_melampaui_wewenang=potensi_lampau,
            potensi_mencampuradukkan_wewenang=potensi_campur,
            potensi_sewenang_wenang=potensi_wenang2
        )

    def check_risiko_kerugian_negara(
        self,
        aspek_keuangan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deteksi dini elemen Pasal 2 ayat (1) dan Pasal 3 UU Tipikor (UU 31/1999 jo UU 20/2001).
        Unsur:
        1. Melawan hukum / menyalahgunakan kewenangan/kesempatan/sarana
        2. Memperkaya diri sendiri, orang lain, atau suatu korporasi
        3. Dapat merugikan keuangan negara atau perekonomian negara (Putusan MK No. 25/PUU-XIV/2016 -> delik materiil/kerugian nyata).
        """
        nominal_transaksi = aspek_keuangan.get("nilai_transaksi", 0)
        apakah_ada_audit_bpk = aspek_keuangan.get("ada_lhp_bpk_apip", False)
        apakah_ada_kelebihan_bayar = aspek_keuangan.get("kelebihan_bayar", False)
        apakah_prosedur_dilanggar = aspek_keuangan.get("pelanggaran_prosedur", False)

        level_risiko = "RENDAH"
        unsur_terpenuhi = []

        if apakah_prosedur_dilanggar:
            unsur_terpenuhi.append("Unsur Melawan Hukum / Penyalahgunaan Wewenang (Pasal 2/3 UU Tipikor)")
        if apakah_ada_kelebihan_bayar:
            unsur_terpenuhi.append("Unsur Memperkaya Pihak Lain / Rekanan")
            unsur_terpenuhi.append("Unsur Potensi Nyata Kerugian Keuangan Negara (Putusan MK 25/PUU-XIV/2016)")
            level_risiko = "TINGGI"
        elif apakah_prosedur_dilanggar:
            level_risiko = "SEDANG"

        mitigasi = []
        if level_risiko == "TINGGI":
            mitigasi.append("Segera lakukan Tuntutan Ganti Kerugian (TGR) atau pemulihan kas daerah/negara dalam tenggang 60 hari sesuai LHP APIP/BPK.")
            mitigasi.append("Bekukan sementara pencairan termin berikutnya sebelum audit fisik selesai.")
        elif level_risiko == "SEDANG":
            mitigasi.append("Lakukan adendum kontrak atau penyesuaian administratif sebelum penerbitan SPM/SP2D.")
        else:
            mitigasi.append("Pertahankan kepatuhan bukti fisik SPJ dan dokumentasi lapangan.")

        return {
            "level_risiko": level_risiko,
            "nominal_terdampak": nominal_transaksi,
            "unsur_tipikor_teridentifikasi": unsur_terpenuhi,
            "rekomendasi_mitigasi": mitigasi,
            "catatan_hukum": "Berdasarkan Putusan MK No. 25/PUU-XIV/2016, kerugian keuangan negara harus bersifat nyata dan pasti (actual loss), bukan sekadar potensi (potential loss)."
        }

    def generate_opinion(
        self,
        judul_kasus: str,
        pemohon: str,
        nomor_memo: str,
        fakta_peristiwa: str,
        issues: List[LegalIssue],
        rules: List[RuleReference],
        fakta_kasus_detail: Optional[Dict[str, Any]] = None,
        aspek_keuangan: Optional[Dict[str, Any]] = None
    ) -> LegalOpinionResult:
        """
        Menyusun Pendapat Hukum (Legal Opinion) komprehensif berstandar JF Analis Hukum.
        """
        fakta_detail = fakta_kasus_detail or {}
        aspek_uang = aspek_keuangan or {}

        # 1. Audit AUPB
        aupb_audit = self.evaluate_aupb_compliance(judul_kasus, fakta_detail)

        # 2. Diskresi (jika ada indikasi)
        diskresi = None
        if fakta_detail.get("menggunakan_diskresi", False):
            diskresi = self.assess_diskresi(
                latar_belakang=fakta_peristiwa,
                alasan=fakta_detail.get("alasan_diskresi", "peraturan_tidak_lengkap"),
                ada_persetujuan_atasan=fakta_detail.get("persetujuan_atasan", False)
            )

        # 3. Risiko Keuangan
        risiko_uang = self.check_risiko_kerugian_negara(aspek_uang)

        # 4. Konstruksi IRAC Analysis
        irac_map = {}
        for issue in issues:
            irac_map[issue.issue_id] = {
                "issue": issue.pertanyaan_hukum,
                "applicable_rules": [r.peraturan + " " + r.pasal for r in rules],
                "application": (
                    f"Menganalisis keterkaitan antara fakta bahwa '{fakta_peristiwa[:120]}...' "
                    f"terhadap ketentuan norma hukum yang berlaku. "
                    f"Berdasarkan asas lex specialis derogat legi generali dan ketentuan wewenang pejabat, "
                    f"tindakan tersebut harus diuji kesesuaian prosedurnya."
                ),
                "conclusion": (
                    f"Tindakan hukum terkait {issue.pertanyaan_hukum} "
                    f"{'DAPAT DIBENARKAN secara yuridis dengan catatan pemenuhan syarat administratif.' if risiko_uang['level_risiko'] != 'TINGGI' else 'BERISIKO TINGGI dan perlu ditinjau ulang sebelum dieksekusi.'}"
                )
            }

        # 5. Rekomendasi
        rekomendasi_utama = []
        if risiko_uang["level_risiko"] == "TINGGI":
            rekomendasi_utama.append("Tunda pelaksanaan keputusan hingga klarifikasi audit independen/APIP selesai.")
        else:
            rekomendasi_utama.append("Keputusan dapat diteruskan dengan melengkapi dokumen telaahan staf dan SOP.")

        pelanggaran_aupb = [a.asas for a in aupb_audit if a.status == "POTENSI_PELANGGARAN"]
        if pelanggaran_aupb:
            rekomendasi_utama.append(f"Perbaiki mitigasi risiko pelanggaran asas: {', '.join(pelanggaran_aupb)}.")

        kesimpulan_rekomendasi = {
            "kesimpulan_umum": "Yuridis Terpenuhi dengan Catatan Mitigasi" if risiko_uang["level_risiko"] != "TINGGI" else "Yuridis Rawan Pembatalan/Gugatan",
            "langkah_tindakan": rekomendasi_utama,
            "tingkat_urgensi": "SEGERA" if risiko_uang["level_risiko"] == "TINGGI" else "NORMAL"
        }

        # 6. Executive Summary (1-Page Briefing)
        exec_summary = (
            f"RINGKASAN EKSEKUTIF PENDAPAT HUKUM (LEGAL OPINION)\n"
            f"Nomor: {nomor_memo} | Perihal: {judul_kasus}\n"
            f"Pemohon: {pemohon} | Jenjang Analis: {self.jenjang}\n"
            f"----------------------------------------------------------------------\n"
            f"1. POKOK MASALAH HUKUM:\n"
            + "\n".join([f"   - {i.pertanyaan_hukum}" for i in issues]) + "\n"
            f"2. KESIMPULAN YURIDIS:\n"
            f"   {kesimpulan_rekomendasi['kesimpulan_umum']}\n"
            f"3. STATUS KEPATUHAN AUPB (UU 30/2014):\n"
            f"   - Catatan Perhatian: {', '.join(pelanggaran_aupb) if pelanggaran_aupb else 'Seluruh 8 Asas Terpenuhi Baik'}\n"
            f"4. RISIKO KEUANGAN NEGARA & TIPIKOR:\n"
            f"   - Level Risiko: {risiko_uang['level_risiko']}\n"
            f"   - Rekomendasi Utama: {risiko_uang['rekomendasi_mitigasi'][0] if risiko_uang['rekomendasi_mitigasi'] else 'Tertib SPJ'}\n"
            f"5. REKOMENDASI TINDAKAN EKSEKUTIF:\n"
            + "\n".join([f"   * {r}" for r in rekomendasi_utama])
        )

        return LegalOpinionResult(
            judul_kasus=judul_kasus,
            pemohon_pendapat=pemohon,
            nomor_memo=nomor_memo,
            tanggal=datetime.now().strftime("%Y-%m-%d"),
            issues=issues,
            rules=rules,
            irac_analysis=irac_map,
            aupb_shield_audit=aupb_audit,
            diskresi_assessment=diskresi,
            risiko_kerugian_negara=risiko_uang,
            kesimpulan_dan_rekomendasi=kesimpulan_rekomendasi,
            executive_summary=exec_summary
        )

    def render_markdown(self, result: LegalOpinionResult) -> str:
        """
        Merender dokumen resmi Pendapat Hukum (Legal Opinion) ke format Markdown ASN.
        """
        lines = []
        lines.append(f"# NOTA PENDAPAT HUKUM (LEGAL OPINION)")
        lines.append(f"**Nomor:** {result.nomor_memo}")
        lines.append(f"**Kepada Yth:** {result.pemohon_pendapat}")
        lines.append(f"**Dari:** Tim Analis Hukum ({self.jenjang})")
        lines.append(f"**Tanggal:** {result.tanggal}")
        lines.append(f"**Perihal:** {result.judul_kasus}")
        lines.append(f"\n---\n")

        lines.append(f"## I. DUDUK PERKARA (STATEMENT OF FACTS)")
        lines.append(f"Bahwa berdasarkan permohonan yang diajukan, duduk perkara dan permasalahan hukum dirumuskan sebagai berikut:")
        for idx, iss in enumerate(result.issues, start=1):
            lines.append(f"{idx}. {iss.pertanyaan_hukum} (Kategori: {iss.kategori.upper()})")

        lines.append(f"\n## II. DASAR HUKUM & REGULASI TERKAIT (RULES)")
        for r in result.rules:
            lines.append(f"- **{r.peraturan} {r.pasal}** ({r.tingkat_hierarki}): \"{r.bunyi_norma}\" [{r.status_keberlakuan}]")

        lines.append(f"\n## III. ANALISIS YURIDIS BERBASIS IRAC (APPLICATION)")
        for key, item in result.irac_analysis.items():
            lines.append(f"### Isu Hukum: {item['issue']}")
            lines.append(f"**Analisis Penerapan Norma:**\n{item['application']}")
            lines.append(f"**Sub-Kesimpulan:**\n{item['conclusion']}\n")

        lines.append(f"## IV. UJI KEPATUHAN ASAS UMUM PEMERINTAHAN YANG BAIK (AUPB SHIELD)")
        lines.append("| No | Asas AUPB | Dasar Hukum | Status Kepatuhan | Catatan Analisis |")
        lines.append("|---|---|---|---|---|")
        for i, a in enumerate(result.aupb_shield_audit, start=1):
            status_badge = "✅ PATUH" if a.status == "PATUH" else "⚠️ PERHATIAN"
            lines.append(f"| {i} | {a.asas} | {a.dasar_hukum} | {status_badge} | {a.catatan_analisis} |")

        if result.diskresi_assessment:
            d = result.diskresi_assessment
            lines.append(f"\n## V. PENGUJIAN KEABSAHAN DISKRESI (PASAL 22-30 UU 30/2014)")
            lines.append(f"- Dasar Diskresi: {'Memenuhi Syarat' if d.apakah_ada_dasar_diskresi else 'Tidak Memenuhi Syarat'}")
            lines.append(f"- Alasan: {d.alasan_diskresi}")
            lines.append(f"- Potensi Melampaui Wewenang: {'YA (Rawan Batal Demi Hukum)' if d.potensi_melampaui_wewenang else 'TIDAK'}")
            lines.append(f"- Potensi Sewenang-wenang: {'YA' if d.potensi_sewenang_wenang else 'TIDAK'}")

        lines.append(f"\n## VI. PENILAIAN RISIKO KEUANGAN NEGARA & TIPIKOR")
        lines.append(f"- **Tingkat Risiko:** `{result.risiko_kerugian_negara['level_risiko']}`")
        lines.append(f"- **Catatan:** {result.risiko_kerugian_negara['catatan_hukum']}")
        if result.risiko_kerugian_negara["unsur_tipikor_teridentifikasi"]:
            lines.append("- **Unsur Terindikasi:**")
            for u in result.risiko_kerugian_negara["unsur_tipikor_teridentifikasi"]:
                lines.append(f"  * {u}")

        lines.append(f"\n## VII. KESIMPULAN DAN REKOMENDASI TINDAKAN")
        lines.append(f"**Kesimpulan Utama:** {result.kesimpulan_dan_rekomendasi['kesimpulan_umum']}")
        lines.append(f"\n**Rekomendasi Tindakan (Action Plan):**")
        for r in result.kesimpulan_dan_rekomendasi["langkah_tindakan"]:
            lines.append(f"1. {r}")

        lines.append(f"\n---\n")
        lines.append(f"### LAMPIRAN: 1-PAGE EXECUTIVE BRIEFING")
        lines.append(f"```text\n{result.executive_summary}\n```")

        return "\n".join(lines)
