"""
deontic_logic_verifier.py — Kaidah Formulasi Norma Deontik (Lampiran II UU 12/2011)
Memverifikasi kepatuhan modalitas norma (Suruhan, Larangan, Kebolehan, Wewenang)
serta menolak frasa ambigu non-normatif dalam perancangan perundang-undangan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DeonticModality(str, Enum):
    COMMAND_PERSON = "SURUHAN_ORANG"       # Kata 'wajib' (subjek orang/pejabat)
    COMMAND_CONDITION = "SURUHAN_KONDISI"  # Kata 'harus' (persyaratan/objek barang)
    PROHIBITION = "LARANGAN"               # Kata 'dilarang' / 'tidak boleh'
    PERMISSION = "KEBOLEHAN"               # Kata 'dapat' (fakultatif/opsional)
    AUTHORIZATION = "WEWENANG"             # Kata 'berwenang' / 'diberi wewenang'
    AMBIGUOUS = "AMBIGU_NON_NORMATIF"      # Diksi terlarang: 'diupayakan', 'seyogianya', dll.
    UNDEFINED = "TIDAK_TERDEFINISI"


@dataclass
class DeonticAnalysisResult:
    article_ref: str
    clause_text: str
    primary_modality: DeonticModality
    detected_modalities: List[DeonticModality]
    ambiguous_terms: List[str]
    is_valid: bool
    findings: List[str]
    recommendation: Optional[str] = None


class DeonticLogicVerifier:
    """
    Engine verifikasi logika deontik sesuai 236 kaidah Lampiran II UU 12/2011.
    Menjamin pasal-pasal regulasi memiliki daya ikat hukum pasti tanpa multitafsir.
    """

    AMBIGUOUS_PATTERNS = [
        (r"\bdiupayakan\b", "diupayakan", "Ganti dengan 'wajib' jika mengikat, atau rumuskan mekanisme teknisnya."),
        (r"\bdiharapkan\b", "diharapkan", "Frasa 'diharapkan' tidak memiliki daya ikat hukum. Gunakan 'wajib' atau 'dapat'."),
        (r"\bseyogianya\b", "seyogianya", "Kata moralistis non-hukum. Ganti dengan modalitas imperatif 'wajib' atau 'dilarang'."),
        (r"\bsebaiknya\b", "sebaiknya", "Bukan norma hukum positif. Rumuskan hak atau kewajiban secara tegas."),
        (r"\bsemestinya\b", "semestinya", "Hindari ketidakpastian norma. Tentukan subjek dan sanksinya."),
        (r"\bdiusahakan\b", "diusahakan", "Lemah secara yuridis. Ganti dengan prosedur standar yang terukur."),
    ]

    MODALITY_PATTERNS = [
        (r"\bwajib\b", DeonticModality.COMMAND_PERSON),
        (r"\bharus\b", DeonticModality.COMMAND_CONDITION),
        (r"\bdilarang\b", DeonticModality.PROHIBITION),
        (r"\btidak boleh\b", DeonticModality.PROHIBITION),
        (r"\bdapat\b", DeonticModality.PERMISSION),
        (r"\bberwenang\b", DeonticModality.AUTHORIZATION),
        (r"\bdiberi wewenang\b", DeonticModality.AUTHORIZATION),
    ]

    @classmethod
    def verify_clause(cls, clause_text: str, article_ref: str = "Pasal -") -> DeonticAnalysisResult:
        """
        Memverifikasi satu ayat atau satu pasal norma.
        """
        text_lower = clause_text.lower()
        findings: List[str] = []
        ambiguous_found: List[str] = []
        recommendations: List[str] = []

        # 1. Deteksi frasa ambigu terlarang
        for pattern, word, rec in cls.AMBIGUOUS_PATTERNS:
            if re.search(pattern, text_lower):
                ambiguous_found.append(word)
                findings.append(f"Ditemukan frasa non-normatif '{word}' yang dilarang Lampiran II UU 12/2011.")
                recommendations.append(rec)

        # 2. Deteksi modalitas sah
        detected_mods: List[DeonticModality] = []
        for pattern, mod in cls.MODALITY_PATTERNS:
            if re.search(pattern, text_lower):
                if mod not in detected_mods:
                    detected_mods.append(mod)

        # 3. Evaluasi ketepatan penggunaan
        if ambiguous_found:
            primary_mod = DeonticModality.AMBIGUOUS
            is_valid = False
        elif detected_mods:
            primary_mod = detected_mods[0]
            is_valid = True

            # Uji spesifik subjek vs modalitas
            if primary_mod == DeonticModality.COMMAND_CONDITION and "setiap orang" in text_lower:
                findings.append("Catatan Kaidah: Subjek hukum 'Setiap Orang' lebih tepat menggunakan 'wajib', bukan 'harus'.")
        else:
            primary_mod = DeonticModality.UNDEFINED
            # Beberapa pasal seperti definisi atau ketentuan peralihan mungkin deklaratif
            if "adalah" in text_lower or "yang dimaksud dengan" in text_lower:
                primary_mod = DeonticModality.AUTHORIZATION  # Definisi status
                is_valid = True
            else:
                is_valid = False
                findings.append("Pasal tidak memuat modalitas norma deontik yang jelas (tidak ada wajib/dilarang/dapat/berwenang).")
                recommendations.append("Tambahkan modalitas hukum agar pasal memiliki konsekuensi suruhan, larangan, atau wewenang.")

        rec_str = " ".join(recommendations) if recommendations else "Norma telah memenuhi kaidah modalitas Lampiran II UU 12/2011."

        return DeonticAnalysisResult(
            article_ref=article_ref,
            clause_text=clause_text.strip(),
            primary_modality=primary_mod,
            detected_modalities=detected_mods,
            ambiguous_terms=ambiguous_found,
            is_valid=is_valid,
            findings=findings,
            recommendation=rec_str
        )

    @classmethod
    def verify_regulation_batch(cls, articles: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Memverifikasi kumpulan pasal/ayat dalam satu naskah rancangan peraturan.
        """
        results: List[Dict[str, Any]] = []
        total = len(articles)
        valid_count = 0
        ambiguous_count = 0

        for item in articles:
            ref = item.get("ref", "Pasal -")
            text = item.get("text", "")
            res = cls.verify_clause(text, article_ref=ref)
            if res.is_valid:
                valid_count += 1
            if res.ambiguous_terms:
                ambiguous_count += 1

            results.append({
                "article_ref": res.article_ref,
                "clause_text": res.clause_text,
                "primary_modality": res.primary_modality.value,
                "is_valid": res.is_valid,
                "ambiguous_terms": res.ambiguous_terms,
                "findings": res.findings,
                "recommendation": res.recommendation
            })

        compliance_rate = (valid_count / total * 100) if total > 0 else 100.0

        return {
            "total_clauses_analyzed": total,
            "valid_deontic_clauses": valid_count,
            "clauses_with_ambiguity": ambiguous_count,
            "deontic_compliance_rate_pct": round(compliance_rate, 2),
            "is_cleared": (ambiguous_count == 0 and compliance_rate >= 90.0),
            "details": results
        }
