"""
litigation_agent.py - Modul Advokasi Litigasi & Judicial Review (JF Analis Hukum & Perancang)
=============================================================================================
Menangani rekonstruksi kronologi fakta sengketa, penyusunan matriks 5 alat bukti
peradilan tata usaha negara (PTUN - Pasal 100 UU 5/1986 jo UU 9/2004), perumusan eksepsi
formal Tergugat (Kompetensi, Daluwarsa 90 Hari Pasal 55, Upaya Administratif UU 30/2014),
serta penyusunan Keterangan Pemerintah dalam Judicial Review di MKRI (Uji UU thd UUD 1945)
dan Mahkamah Agung (Hak Uji Materiil Peraturan di bawah UU).

Sesuai standar advokasi hukum BPHN, Ditjen PP, dan Biro Hukum Kementerian/Lembaga/Pemda.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class KronologiEvent:
    tanggal: str
    uraian_peristiwa: str
    aktor_terlibat: str
    dokumen_bukti: str
    relevansi_hukum: str


@dataclass
class AlatBuktiPTUN:
    jenis_alat_bukti: str  # 'SURAT_TULISAN', 'KETERANGAN_AHLI', 'SAKSI', 'PENGAKUAN', 'PENGETAHUAN_HAKIM'
    kode_bukti: str  # e.g., 'T-1', 'T-2'
    nama_dokumen_sumber: str
    relevansi_bantahan: str
    lokasi_fisik: str = "Arsip Biro Hukum"


@dataclass
class EksepsiItem:
    jenis_eksepsi: str  # 'KOMPETENSI_ABSOLUT', 'TENGGANG_WAKTU_90_HARI', 'UPAYA_ADMINISTRATIF', 'BUKAN_KTUN_FINAL', 'OBSCUUR_LIBEL'
    dasar_hukum: str
    dalil_bantahan: str
    kekuatan_argumen: str  # 'KUAT', 'SEDANG', 'LEMAH'


@dataclass
class JudicialReviewDefense:
    forum_peradilan: str  # 'MKRI' (Uji UU thd UUD 1945) atau 'MA' (Uji Peraturan thd UU)
    norma_diuji: str
    batu_uji: str
    bantahan_legal_standing: str
    dalil_open_legal_policy: bool
    keterangan_pemerintah: str


@dataclass
class LitigationCaseFile:
    nomor_perkara: str
    judul_sengketa: str
    instansi_tergugat: str
    penggugat: str
    forum_pengadilan: str
    kronologi: List[KronologiEvent]
    matriks_alat_bukti: List[AlatBuktiPTUN]
    daftar_eksepsi: List[EksepsiItem]
    judicial_review: Optional[JudicialReviewDefense]
    prospek_kemenangan: str  # 'TINGGI', 'MODERAT', 'BERISIKO'
    executive_summary: str


class LitigationAdvocacyAgent:
    """
    Engine Advokasi Hukum Pemerintah untuk Litigasi dan Judicial Review.
    """

    def __init__(self, jenjang: str = "Ahli Madya"):
        self.jenjang = jenjang

    def build_eksepsi_ptun(
        self,
        tanggal_ktun: str,
        tanggal_gugatan: str,
        apakah_lewat_90_hari: bool,
        apakah_sudah_upaya_administratif: bool,
        sifat_ktun_final: bool,
        ranah_sengketa: str = "TUN"
    ) -> List[EksepsiItem]:
        """
        Menyusun bantahan formal (Eksepsi) Tergugat dalam sengketa TUN.
        """
        eksepsi_list = []

        # 1. Eksepsi Tenggang Waktu 90 Hari (Pasal 55 UU PTUN)
        if apakah_lewat_90_hari:
            eksepsi_list.append(EksepsiItem(
                jenis_eksepsi="TENGGANG_WAKTU_90_HARI",
                dasar_hukum="Pasal 55 UU No. 5 Tahun 1986 tentang PTUN",
                dalil_bantahan=(
                    f"Gugatan Penggugat telah daluwarsa (lewat waktu) karena diajukan melampaui tenggang waktu "
                    f"90 (sembilan puluh) hari kalender sejak Keputusan Tata Usaha Negara diterima atau diumumkan. "
                    f"Maka gugatan Penggugat secara hukum harus dinyatakan tidak dapat diterima (Niet Ontvankelijke Verklaard / NO)."
                ),
                kekuatan_argumen="KUAT"
            ))

        # 2. Eksepsi Upaya Administratif (Pasal 75-78 UU 30/2014 jo PERMA No. 6 Tahun 2018)
        if not apakah_sudah_upaya_administratif:
            eksepsi_list.append(EksepsiItem(
                jenis_eksepsi="UPAYA_ADMINISTRATIF",
                dasar_hukum="Pasal 75 s.d. Pasal 78 UU No. 30/2014 jo Perma No. 6 Tahun 2018",
                dalil_bantahan=(
                    "Penggugat belum menempuh upaya administratif (keberatan dan/atau banding administratif) "
                    "pada instansi Tergugat sebelum mendaftarkan gugatan ke Pengadilan TUN. Berdasarkan Perma No. 6/2018, "
                    "Pengadilan TUN tidak berwenang memeriksa dan memutus perkara a quo sebelum upaya administratif selesai ditempuh."
                ),
                kekuatan_argumen="KUAT"
            ))

        # 3. Eksepsi Objek Sengketa Bukan KTUN Final (Pasal 1 angka 9 UU 51/2009)
        if not sifat_ktun_final:
            eksepsi_list.append(EksepsiItem(
                jenis_eksepsi="BUKAN_KTUN_FINAL",
                dasar_hukum="Pasal 1 angka 9 UU No. 51 Tahun 2009",
                dalil_bantahan=(
                    "Objek sengketa yang digugat masih merupakan surat pemberitahuan, telaahan staf, atau memo internal "
                    "yang belum menimbulkan akibat hukum definitif (belum bersifat konkret, individual, dan final). "
                    "Sehingga objek a quo bukan merupakan KTUN yang dapat disengketakan di PTUN."
                ),
                kekuatan_argumen="KUAT"
            ))

        # 4. Eksepsi Kompetensi Absolut (Jika ranah perdata / perdata khusus)
        if ranah_sengketa != "TUN":
            eksepsi_list.append(EksepsiItem(
                jenis_eksepsi="KOMPETENSI_ABSOLUT",
                dasar_hukum="Pasal 2 UU No. 5 Tahun 1986",
                dalil_bantahan=(
                    f"Substansi yang dipermasalahkan menyangkut sengketa keperdataan / perjanjian kerja sama, "
                    f"sehingga kewenangan mengadili perkara ini secara absolut berada pada lingkup Pengadilan Negeri, "
                    f"bukan Pengadilan Tata Usaha Negara."
                ),
                kekuatan_argumen="KUAT"
            ))

        return eksepsi_list

    def construct_case_defense(
        self,
        nomor_perkara: str,
        judul_sengketa: str,
        instansi_tergugat: str,
        penggugat: str,
        forum: str,
        kronologi_data: List[Dict[str, str]],
        bukti_data: List[Dict[str, str]],
        fakta_formal: Dict[str, Any],
        jr_data: Optional[Dict[str, Any]] = None
    ) -> LitigationCaseFile:
        """
        Menyusun berkas advokasi hukum dan strategi pembelaan perkara.
        """
        # 1. Parsing Kronologi
        kronologi_list = [
            KronologiEvent(
                tanggal=k.get("tanggal", "-"),
                uraian_peristiwa=k.get("peristiwa", "-"),
                aktor_terlibat=k.get("aktor", "-"),
                dokumen_bukti=k.get("bukti", "-"),
                relevansi_hukum=k.get("relevansi", "-")
            )
            for k in kronologi_data
        ]

        # 2. Parsing Bukti PTUN (Pasal 100 UU PTUN)
        bukti_list = [
            AlatBuktiPTUN(
                jenis_alat_bukti=b.get("jenis", "SURAT_TULISAN"),
                kode_bukti=b.get("kode", f"T-{idx}"),
                nama_dokumen_sumber=b.get("nama", "-"),
                relevansi_bantahan=b.get("relevansi", "-"),
                lokasi_fisik=b.get("lokasi", "Arsip Biro Hukum")
            )
            for idx, b in enumerate(bukti_data, start=1)
        ]

        # 3. Eksepsi
        eksepsi = self.build_eksepsi_ptun(
            tanggal_ktun=fakta_formal.get("tanggal_ktun", ""),
            tanggal_gugatan=fakta_formal.get("tanggal_gugatan", ""),
            apakah_lewat_90_hari=fakta_formal.get("lewat_90_hari", False),
            apakah_sudah_upaya_administratif=fakta_formal.get("upaya_administratif_selesai", True),
            sifat_ktun_final=fakta_formal.get("ktun_final", True),
            ranah_sengketa=fakta_formal.get("ranah", "TUN")
        )

        # 4. Judicial Review (jika forum MK / MA)
        jr_defense = None
        if jr_data:
            jr_defense = JudicialReviewDefense(
                forum_peradilan=jr_data.get("forum", "MKRI"),
                norma_diuji=jr_data.get("norma_diuji", "-"),
                batu_uji=jr_data.get("batu_uji", "-"),
                bantahan_legal_standing=jr_data.get("bantahan_standing", "Pemohon tidak mengalami kerugian konstitusional langsung."),
                dalil_open_legal_policy=jr_data.get("open_legal_policy", True),
                keterangan_pemerintah=jr_data.get("dalil_pemerintah", "Norma a quo merupakan pilihan kebijakan pembentuk UU yang proporsional.")
            )

        # 5. Penilaian Prospek Kemenangan
        strong_eksepsi = sum(1 for e in eksepsi if e.kekuatan_argumen == "KUAT")
        has_surat_bukti = any(b.jenis_alat_bukti == "SURAT_TULISAN" for b in bukti_list)

        if strong_eksepsi >= 1 and has_surat_bukti:
            prospek = "TINGGI"
        elif has_surat_bukti:
            prospek = "MODERAT"
        else:
            prospek = "BERISIKO"

        # 6. Ringkasan Eksekutif
        exec_summary = (
            f"RINGKASAN STRATEGI ADVOKASI HUKUM PERKARA\n"
            f"Perkara: {nomor_perkara} | Judul: {judul_sengketa}\n"
            f"Tergugat: {instansi_tergugat} | Penggugat: {penggugat}\n"
            f"Forum: {forum} | Prospek Kemenangan: {prospek}\n"
            f"----------------------------------------------------------------------\n"
            f"1. EKSEPSI FORMAL UTAMA:\n"
            + "\n".join([f"   - [{e.jenis_eksepsi}] {e.dalil_bantahan[:100]}..." for e in eksepsi]) + (
                "\n   (Tidak ada eksepsi formal mutlak, fokus pada pembuktian pokok perkara)" if not eksepsi else ""
            ) + "\n"
            f"2. KESIAPAN ALAT BUKTI (PASAL 100 UU PTUN):\n"
            f"   - Total Bukti Terverifikasi: {len(bukti_list)} Bukti Dokumen/Saksi\n"
            f"3. CATATAN STRATEGIS SIDANG:\n"
            f"   - Ajukan Putusan Sela atas Eksepsi Kompetensi/Daluwarsa untuk menghentikan perkara lebih dini.\n"
            f"   - Pastikan pejabat penandatangan KTUN siap memberikan keterangan saksi fakta jika diperlukan."
        )

        return LitigationCaseFile(
            nomor_perkara=nomor_perkara,
            judul_sengketa=judul_sengketa,
            instansi_tergugat=instansi_tergugat,
            penggugat=penggugat,
            forum_pengadilan=forum,
            kronologi=kronologi_list,
            matriks_alat_bukti=bukti_list,
            daftar_eksepsi=eksepsi,
            judicial_review=jr_defense,
            prospek_kemenangan=prospek,
            executive_summary=exec_summary
        )

    def render_markdown(self, case: LitigationCaseFile) -> str:
        """
        Merender berkas advokasi sengketa dan jawaban Tergugat ke format Markdown resmi.
        """
        lines = []
        lines.append(f"# BERKAS ADVOKASI HUKUM & JAWABAN PERKARA")
        lines.append(f"**Nomor Perkara:** {case.nomor_perkara}")
        lines.append(f"**Judul Sengketa:** {case.judul_sengketa}")
        lines.append(f"**Instansi Tergugat:** {case.instansi_tergugat}")
        lines.append(f"**Pihak Penggugat / Pemohon:** {case.penggugat}")
        lines.append(f"**Forum Peradilan:** `{case.forum_pengadilan}`")
        lines.append(f"**Jenjang Advokat/Analis:** {self.jenjang}")
        lines.append(f"**Estimasi Prospek Kemenangan:** **{case.prospek_kemenangan}**")
        lines.append(f"\n---\n")

        lines.append(f"## I. REKONSTRUKSI KRONOLOGI FAKTA PERSIDANGAN")
        lines.append("| Tanggal | Peristiwa Hukum | Pihak Terlibat | Alat Bukti Relevan | Signifikansi Yuridis |")
        lines.append("|---|---|---|---|---|")
        for k in case.kronologi:
            lines.append(f"| {k.tanggal} | {k.uraian_peristiwa} | {k.aktor_terlibat} | `{k.dokumen_bukti}` | {k.relevansi_hukum} |")

        lines.append(f"\n## II. BANTARAN FORMAL (EKSEPSI TERGUGAT)")
        if not case.daftar_eksepsi:
            lines.append("*Tidak diajukan eksepsi formal mutlak. Tergugat langsung menjawab materi pokok perkara.*")
        else:
            for idx, e in enumerate(case.daftar_eksepsi, start=1):
                lines.append(f"### {idx}. Eksepsi {e.jenis_eksepsi.replace('_', ' ').title()}")
                lines.append(f"- **Dasar Hukum:** {e.dasar_hukum}")
                lines.append(f"- **Kekuatan Argumen:** `{e.kekuatan_argumen}`")
                lines.append(f"- **Dalil Bantahan:**\n  \"{e.dalil_bantahan}\"\n")

        lines.append(f"## III. MATRIKS 5 ALAT BUKTI (PASAL 100 UU PTUN)")
        lines.append("| Kode Bukti | Jenis Alat Bukti | Nama Dokumen / Sumber | Pokok Relevansi Bantahan | Lokasi Fisik |")
        lines.append("|---|---|---|---|---|")
        for b in case.matriks_alat_bukti:
            lines.append(f"| **{b.kode_bukti}** | `{b.jenis_alat_bukti}` | {b.nama_dokumen_sumber} | {b.relevansi_bantahan} | {b.lokasi_fisik} |")

        if case.judicial_review:
            jr = case.judicial_review
            lines.append(f"\n## IV. STRATEGI KETERANGAN PEMERINTAH (JUDICIAL REVIEW - {jr.forum_peradilan})")
            lines.append(f"- **Norma yang Diuji:** {jr.norma_diuji}")
            lines.append(f"- **Batu Uji Konstitusional / UU:** {jr.batu_uji}")
            lines.append(f"- **Bantahan Legal Standing Pemohon:** {jr.bantahan_legal_standing}")
            lines.append(f"- **Kebijakan Hukum Terbuka (Open Legal Policy):** {'Diterapkan' if jr.dalil_open_legal_policy else 'Tidak Diterapkan'}")
            lines.append(f"- **Substansi Keterangan Pemerintah:**\n  {jr.keterangan_pemerintah}")

        lines.append(f"\n## V. KESIMPULAN PETITUM / LANGKAH ADVOKASI")
        lines.append("Berdasarkan seluruh uraian fakta, dasar hukum, dan alat bukti yang diajukan, Tergugat memohon kepada Majelis Hakim:")
        lines.append("1. **DALAM EKSEPSI:** Mengabulkan eksepsi Tergugat seluruhnya dan menyatakan gugatan Penggugat tidak dapat diterima (*Niet Ontvankelijke Verklaard*).")
        lines.append("2. **DALAM POKOK PERKARA:** Menolak gugatan Penggugat untuk seluruhnya serta menyatakan KTUN Tergugat sah demi hukum.")

        lines.append(f"\n---\n")
        lines.append(f"### LAMPIRAN: 1-PAGE EXECUTIVE BRIEFING")
        lines.append(f"```text\n{case.executive_summary}\n```")

        return "\n".join(lines)
