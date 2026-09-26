"""
legislative_drafter.py — Engine Perancangan Peraturan Berbasis 236 Kaidah Lampiran II UU 12/2011
Menghasilkan draf regulasi daerah (Perda/Perkada) dengan struktur anatomi baku:
Judul, Konsiderans Menimbang, Dasar Hukum Mengingat, Diktum, Batang Tubuh, Ketentuan Peralihan & Penutup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .deontic_logic_verifier import DeonticLogicVerifier


@dataclass
class RegulationMetadata:
    reg_type: str  # PERATURAN DAERAH / PERATURAN GUBERNUR / PERATURAN BUPATI
    region_name: str  # misal: KABUPATEN MOROWALI
    title_subject: str  # misal: PENYELENGGARAAN STANDAR PELAYANAN MINIMAL
    year: int = 2026
    official_title: str = "BUPATI MOROWALI"
    menimbang_points: List[str] = field(default_factory=list)
    mengingat_bases: List[str] = field(default_factory=list)


class LegislativeDrafter:
    """
    Generator dan validator perancangan perundang-undangan standar Ditjen PP (UU 12/2011 jo UU 13/2022).
    """

    DEFAULT_MENIMBANG = [
        "bahwa untuk melaksanakan ketentuan Pasal ... Undang-Undang Nomor ... tentang ...;",
        "bahwa untuk meningkatkan kualitas pelayanan publik dan kepastian hukum di daerah, perlu mengatur ...;",
        "bahwa berdasarkan pertimbangan sebagaimana dimaksud dalam huruf a dan huruf b, perlu menetapkan Peraturan Daerah tentang ...;"
    ]

    DEFAULT_MENGINGAT = [
        "Pasal 18 ayat (6) Undang-Undang Dasar Negara Republik Indonesia Tahun 1945;",
        "Undang-Undang Nomor 23 Tahun 2014 tentang Pemerintahan Daerah sebagaimana telah beberapa kali diubah terakhir dengan Undang-Undang Nomor 6 Tahun 2023;",
        "Peraturan Pemerintah Nomor 12 Tahun 2019 tentang Pengelolaan Keuangan Daerah;",
        "Peraturan Menteri Dalam Negeri Nomor 80 Tahun 2015 tentang Pembentukan Produk Hukum Daerah sebagaimana telah diubah dengan Peraturan Menteri Dalam Negeri Nomor 120 Tahun 2018."
    ]

    @classmethod
    def assemble_regulation_draft(
        cls,
        meta: RegulationMetadata,
        chapters: List[Dict[str, Any]]
    ) -> str:
        """
        Merakit naskah regulasi lengkap sesuai format resmi Lampiran II UU 12/2011.
        """
        lines: List[str] = []

        # 1. JUDUL REGULASI
        lines.append(f"{meta.reg_type.upper()} {meta.region_name.upper()}")
        lines.append(f"NOMOR ... TAHUN {meta.year}")
        lines.append("TENTANG")
        lines.append(f"{meta.title_subject.upper()}\n")

        # 2. PEMBUKAAN
        lines.append("DENGAN RAHMAT TUHAN YANG MAHA ESA\n")
        lines.append(f"{meta.official_title.upper()},\n")

        # 3. KONSIDERANS MENIMBANG
        lines.append("Menimbang:")
        menimbang = meta.menimbang_points or cls.DEFAULT_MENIMBANG
        for i, pt in enumerate(menimbang):
            char_label = chr(ord('a') + i)
            # Kaidah UU 12/2011: Setiap butir diawali huruf kecil 'bahwa' dan diakhiri titik koma (kecuali butir terakhir diakhiri titik)
            clean_pt = pt.strip()
            if not clean_pt.lower().startswith("bahwa"):
                clean_pt = f"bahwa {clean_pt}"
            is_last = (i == len(menimbang) - 1)
            clean_pt = clean_pt.rstrip(";.") + ("." if is_last else ";")
            lines.append(f"  {char_label}. {clean_pt}")

        lines.append("")

        # 4. DASAR HUKUM MENGINGAT
        lines.append("Mengingat:")
        mengingat = meta.mengingat_bases or cls.DEFAULT_MENGINGAT
        for i, law in enumerate(mengingat):
            num_label = i + 1
            clean_law = law.strip().rstrip(";.")
            is_last = (i == len(mengingat) - 1)
            clean_law = clean_law + ("." if is_last else ";")
            lines.append(f"  {num_label}. {clean_law}")

        lines.append("\nMEMUTUSKAN:\n")
        lines.append(f"Menetapkan: {meta.reg_type.upper()} TENTANG {meta.title_subject.upper()}.\n")

        # 5. BATANG TUBUH (BAB & PASAL)
        global_pasal = 1
        all_clauses_for_verification = []

        for ch_idx, chapter in enumerate(chapters):
            ch_num_roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"][min(ch_idx, 9)]
            ch_title = chapter.get("title", f"BAB {ch_num_roman}").upper()
            lines.append(f"BAB {ch_num_roman}")
            lines.append(f"{ch_title}\n")

            articles = chapter.get("articles", [])
            for art in articles:
                lines.append(f"Pasal {global_pasal}")
                paragraphs = art.get("paragraphs", [])
                if len(paragraphs) == 1:
                    # Tanpa ayat (1) jika hanya 1 ayat
                    p_text = paragraphs[0].strip()
                    lines.append(f"{p_text}\n")
                    all_clauses_for_verification.append({"ref": f"Pasal {global_pasal}", "text": p_text})
                else:
                    for p_idx, p in enumerate(paragraphs):
                        p_num = p_idx + 1
                        p_text = p.strip()
                        lines.append(f"({p_num}) {p_text}")
                        all_clauses_for_verification.append({"ref": f"Pasal {global_pasal} ayat ({p_num})", "text": p_text})
                    lines.append("")
                global_pasal += 1

        # 6. KETENTUAN PENUTUP
        lines.append(f"BAB {['I','II','III','IV','V','VI','VII','VIII','IX','X'][min(len(chapters), 9)]}")
        lines.append("KETENTUAN PENUTUP\n")
        lines.append(f"Pasal {global_pasal}")
        lines.append(f"Peraturan Daerah ini mulai berlaku pada tanggal diundangkan.\n")
        lines.append("Agar setiap orang mengetahuinya, memerintahkan pengundangan Peraturan Daerah ini ")
        lines.append("dengan penempatannya dalam Lembaran Daerah.\n")

        lines.append(f"Ditetapkan di ...")
        lines.append(f"pada tanggal ... {meta.year}\n")
        lines.append(f"{meta.official_title.upper()},\n\n\n\n")
        lines.append("[NAMA LENGKAP KEPALA DAERAH]")

        draft_output = "\n".join(lines)
        return draft_output

    @classmethod
    def validate_anatomy(cls, text: str) -> Dict[str, Any]:
        """
        Memvalidasi naskah regulasi terhadap kaidah anatomi Lampiran II UU 12/2011.
        """
        findings = []
        score = 100

        # Check Judul
        if not re.search(r"NOMOR\s+.*\s+TAHUN", text, re.IGNORECASE):
            findings.append("Anatomi Error: Format Nomor dan Tahun Regulasi tidak ditemukan.")
            score -= 15

        # Check Pembukaan
        if "DENGAN RAHMAT TUHAN YANG MAHA ESA" not in text.upper():
            findings.append("Kaidah 236: Frasa 'DENGAN RAHMAT TUHAN YANG MAHA ESA' wajib ada di bagian pembukaan.")
            score -= 15

        # Check Konsiderans Menimbang
        if not re.search(r"Menimbang:\s*\n\s*a\.\s*bahwa", text, re.IGNORECASE):
            findings.append("Kaidah 236: Konsiderans Menimbang wajib diawali butir 'a. bahwa'.")
            score -= 15

        # Check Dasar Hukum Mengingat
        if not re.search(r"Mengingat:\s*\n\s*1\.", text, re.IGNORECASE):
            findings.append("Kaidah 236: Dasar Hukum Mengingat wajib menggunakan penomoran arab '1.', '2.', dst.")
            score -= 15

        # Check Diktum
        if "MEMUTUSKAN:" not in text.upper() or "Menetapkan:" not in text:
            findings.append("Kaidah 236: Diktum wajib memuat kata 'MEMUTUSKAN:' dan 'Menetapkan:'.")
            score -= 15

        # Check Ketentuan Penutup
        if not re.search(r"mulai berlaku pada tanggal diundangkan", text, re.IGNORECASE):
            findings.append("Kaidah 236: Ketentuan penutup wajib memuat klausul keberlakuan pengundangan.")
            score -= 10

        # Extract articles for deontic verification
        article_matches = re.findall(r"Pasal\s+(\d+)[\s\S]*?(?=Pasal\s+\d+|BAB\s+[IVXLCDM]+|$)", text)
        articles_data = []
        for i, art_body in enumerate(re.split(r"Pasal\s+\d+", text)[1:]):
            articles_data.append({"ref": f"Pasal {i+1}", "text": art_body.strip()[:300]})

        deontic_check = DeonticLogicVerifier.verify_regulation_batch(articles_data)

        anatomy_status = "LULUS ANATOMI" if score >= 85 and deontic_check["is_cleared"] else "PERLU REVISI KONSEPSI"

        return {
            "anatomy_score": max(0, score),
            "status": anatomy_status,
            "findings": findings,
            "deontic_compliance": deontic_check,
            "is_ready_for_harmonisasi": (score >= 85 and deontic_check["is_cleared"])
        }
