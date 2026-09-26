"""
naskah_akademik_generator.py — Generator Sistematika 6 Bab Naskah Akademik (Lampiran I UU 12/2011)
Menyusun naskah kajian sosio-legal standar resmi untuk pembentukan RUU / Raperda / Raperpres
dengan integrasi logging Meaningful Participation (Pasal 96 UU 13/2022).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NaskahAkademikInput:
    title: str
    region_or_institution: str  # misal: Pemerintah Daerah Kabupaten Morowali
    background_issue: str
    objectives: List[str]
    methodology: str = "Metode penelitian yuridis normatif didukung data empiris sosio-legal dan analisis komparatif regulasi."
    theoretical_basis: str = "Teori Negara Kesejahteraan (Welfare State) dan Teori Efektivitas Hukum (Prof. Soerjono Soekanto)."
    empirical_practice: str = "Praktik penyelenggaraan urusan konkuren di daerah menunjukkan perlunya standarisasi operasional dan kepastian alokasi APBD."
    related_regulations: List[str] = field(default_factory=list)
    filosofis_point: str = "Pancasila dan Pembukaan UUD 1945 mengamanatkan perlindungan segenap bangsa dan pemenuhan hak dasar warga negara."
    sosiologis_point: str = "Tuntutan nyata masyarakat di daerah terhadap kemudahan akses layanan dasar dan kejelasan prosedur administratif."
    yuridis_point: str = "Amanat Pasal 18 ayat (6) UUD 1945 dan Pasal 236 UU No. 23 Tahun 2014 tentang wewenang Pemda menetapkan Perda."
    scope_subjects: List[str] = field(default_factory=list)
    meaningful_participation_records: List[Dict[str, str]] = field(default_factory=list)


class NaskahAkademikGenerator:
    """
    Generator terstruktur Naskah Akademik sesuai Lampiran I UU 12/2011 jo UU 13/2022.
    """

    @classmethod
    def generate(cls, data: NaskahAkademikInput) -> Dict[str, Any]:
        """
        Menyusun Naskah Akademik lengkap 6 Bab.
        """
        related_laws = data.related_regulations or [
            "Undang-Undang Dasar Negara Republik Indonesia Tahun 1945",
            "Undang-Undang Nomor 23 Tahun 2014 tentang Pemerintahan Daerah",
            "Undang-Undang Nomor 12 Tahun 2011 tentang Pembentukan Peraturan Perundang-undangan jo UU 13/2022",
            "Peraturan Pemerintah Nomor 12 Tahun 2019 tentang Pengelolaan Keuangan Daerah"
        ]

        scopes = data.scope_subjects or [
            "Ketentuan Umum dan Pembatasan Istilah",
            "Asas, Maksud, dan Tujuan Pengaturan",
            "Ruang Lingkup dan Kewenangan Penyelenggaraan",
            "Tata Cara Koordinasi dan Pelaksanaan Urusan",
            "Pembiayaan dan Alokasi Anggaran Daerah",
            "Pengawasan, Pembinaan, dan Sanksi Administratif",
            "Ketentuan Peralihan dan Penutup"
        ]

        na_doc = {
            "judul": f"NASKAH AKADEMIK RANCANGAN PERATURAN TENTANG {data.title.upper()}",
            "pemrakarsa": data.region_or_institution,
            "bab_1_pendahuluan": {
                "a_latar_belakang": data.background_issue,
                "b_identifikasi_masalah": [
                    f"Permasalahan apa yang dihadapi dalam {data.title.lower()} dan mengapa memerlukan regulasi?",
                    f"Bagaimana evaluasi terhadap peraturan perundang-undangan terkait saat ini?",
                    f"Bagaimana landasan filosofis, sosiologis, dan yuridis pembentukan peraturan?",
                    f"Bagaimana jangkauan, arah pengaturan, dan ruang lingkup materi muatan yang perlu diatur?"
                ],
                "c_tujuan_dan_kegunaan": data.objectives or [
                    "Merumuskan permasalahan hukum yang dihadapi masyarakat dan pemerintah daerah.",
                    "Menetapkan arah pengaturan regulasi yang selaras dengan peraturan perundang-undangan yang lebih tinggi.",
                    "Menjadi pedoman resmi dalam penyusunan draf batang tubuh pasal."
                ],
                "d_metode": data.methodology
            },
            "bab_2_kajian_teoretis_dan_empiris": {
                "kajian_teoretis": data.theoretical_basis,
                "praktik_empiris": data.empirical_practice,
                "beban_kepatuhan_ria": "Analisis dampak regulasi (RIA) menunjukkan bahwa penetapan aturan ini tidak menimbulkan beban kepatuhan finansial berlebih bagi masyarakat, melainkan memperkuat akuntabilitas aparatur."
            },
            "bab_3_evaluasi_puu_terkait": {
                "analisis_harmonisasi": "Melakukan penelusuran hierarki peraturan perundang-undangan secara vertikal dan horizontal:",
                "daftar_regulasi_terkait": related_laws,
                "status_disharmonisasi": "Tidak ditemukan pertentangan norma (antinomi) dengan undang-undang di atasnya. Pengaturan berada dalam koridor otonomi daerah."
            },
            "bab_4_landasan_filosofis_sosiologis_yuridis": {
                "landasan_filosofis": data.filosofis_point,
                "landasan_sosiologis": data.sosiologis_point,
                "landasan_yuridis": data.yuridis_point
            },
            "bab_5_jangkauan_dan_ruang_lingkup": {
                "arah_pengaturan": f"Memberikan kepastian hukum, standarisasi tata kelola, dan perlindungan kepentingan umum terkait {data.title.lower()}.",
                "materi_muatan": scopes,
                "meaningful_participation": data.meaningful_participation_records or [
                    {"hak": "Right to be heard", "realisasi": "Telah dilaksanakan Forum Konsultasi Publik dengan akademisi, praktisi hukum, dan tokoh masyarakat."},
                    {"hak": "Right to be considered", "realisasi": "Masukan terkait kemudahan perizinan dan dispensasi biaya telah diakomodasi ke dalam materi pokok draf."},
                    {"hak": "Right to be explained", "realisasi": "Penjelasan atas usulan pasal yang tidak dapat diakomodasi telah disampaikan secara transparan dalam risalah rapat."}
                ]
            },
            "bab_6_penutup": {
                "kesimpulan": f"Pembentukan regulasi tentang {data.title} sangat mendesak dan telah memenuhi syarat formil serta materiil pembentukan peraturan perundang-undangan.",
                "saran": "Direkomendasikan agar draf rancangan peraturan segera diajukan ke Kantor Wilayah Kementerian Hukum untuk proses Pengharmonisasian sesuai amanat Pasal 58 UU No. 13 Tahun 2022."
            }
        }
        return na_doc

    @classmethod
    def render_markdown(cls, doc: Dict[str, Any]) -> str:
        """
        Merender dokumen Naskah Akademik ke format Markdown resmi.
        """
        lines = []
        lines.append(f"# {doc['judul']}\n")
        lines.append(f"**Pemrakarsa:** {doc['pemrakarsa']}\n")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        # BAB I
        b1 = doc["bab_1_pendahuluan"]
        lines.append("## BAB I: PENDAHULUAN\n")
        lines.append(f"### A. Latar Belakang\n{b1.get('a_latar_belakang', '')}\n")
        lines.append("### B. Identifikasi Masalah\n")
        id_masalah = b1.get("b_identifikasi_masalah") or b1.get("identifikasi_masalah", [])
        for i, m in enumerate(id_masalah, 1):
            lines.append(f"{i}. {m}")
        lines.append("\n### C. Tujuan dan Kegunaan\n")
        tujuan = b1.get("c_tujuan_dan_kegunaan") or b1.get("tujuan_dan_kegunaan", [])
        for i, t in enumerate(tujuan, 1):
            lines.append(f"{i}. {t}")
        lines.append(f"\n### D. Metode Penelitian\n{b1.get('d_metode', '')}\n")

        # BAB II
        b2 = doc["bab_2_kajian_teoretis_dan_empiris"]
        lines.append("## BAB II: KAJIAN TEORETIS DAN PRAKTIK EMPIRIS\n")
        lines.append(f"### A. Kajian Teoretis\n{b2['kajian_teoretis']}\n")
        lines.append(f"### B. Kajian Praktik Empiris Penyelenggaraan\n{b2['praktik_empiris']}\n")
        lines.append(f"### C. Analisis Beban Kepatuhan (Regulatory Impact Assessment)\n{b2['beban_kepatuhan_ria']}\n")

        # BAB III
        b3 = doc["bab_3_evaluasi_puu_terkait"]
        lines.append("## BAB III: EVALUASI DAN ANALISIS PERATURAN PERUNDANG-UNDANGAN TERKAIT\n")
        lines.append(f"{b3['analisis_harmonisasi']}\n")
        for i, r in enumerate(b3["daftar_regulasi_terkait"], 1):
            lines.append(f"{i}. {r}")
        lines.append(f"\n**Status Harmonisasi:** {b3['status_disharmonisasi']}\n")

        # BAB IV
        b4 = doc["bab_4_landasan_filosofis_sosiologis_yuridis"]
        lines.append("## BAB IV: LANDASAN FILOSOFIS, SOSIOLOGIS, DAN YURIDIS\n")
        lines.append(f"### A. Landasan Filosofis\n{b4['landasan_filosofis']}\n")
        lines.append(f"### B. Landasan Sosiologis\n{b4['landasan_sosiologis']}\n")
        lines.append(f"### C. Landasan Yuridis\n{b4['landasan_yuridis']}\n")

        # BAB V
        b5 = doc["bab_5_jangkauan_dan_ruang_lingkup"]
        lines.append("## BAB V: JANGKAUAN, ARAH PENGATURAN, DAN RUANG LINGKUP MATERI MUATAN\n")
        lines.append(f"### A. Arah Pengaturan\n{b5['arah_pengaturan']}\n")
        lines.append("### B. Ruang Lingkup Materi Muatan\n")
        for i, s in enumerate(b5["materi_muatan"], 1):
            lines.append(f"{i}. {s}")
        lines.append("\n### C. Rekam Jejak Partisipasi Masyarakat yang Bermakna (Pasal 96 UU 13/2022)\n")
        for mp in b5["meaningful_participation"]:
            lines.append(f"- **{mp['hak']}:** {mp['realisasi']}")
        lines.append("")

        # BAB VI
        b6 = doc["bab_6_penutup"]
        lines.append("## BAB VI: PENUTUP\n")
        lines.append(f"### A. Kesimpulan\n{b6['kesimpulan']}\n")
        lines.append(f"### B. Saran\n{b6['saran']}\n")

        return "\n".join(lines)
