"""
BPHN 6-Dimension Regulatory Evaluator
Berdasarkan Pedoman Evaluasi Peraturan Perundang-undangan Nomor PHN-HN.01.03-07 (BPHN Kemkumham).

6 Dimensi Evaluasi:
1. Dimensi Pancasila (Bobot: 25%)
2. Dimensi Ketepatan Jenis PUU (Bobot: 15%)
3. Dimensi Disharmoni Pengaturan - Vertikal & Horizontal (Bobot: 20%)
4. Dimensi Kejelasan Rumusan & Bahasa Hukum (Bobot: 10%)
5. Dimensi Kesesuaian Asas Bidang Hukum (Bobot: 15%)
6. Dimensi Efektivitas Pelaksanaan (Bobot: 15%)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from ..connectors.llm_connector import LLMConnector
from ..connectors.kb_connector import KBConnector

logger = logging.getLogger("mcp-unified.legal.bphn_evaluator")

# Bobot Standar Resmi BPHN (Total: 100%)
DIMENSION_WEIGHTS = {
    "dimensi_pancasila": 0.25,
    "dimensi_ketepatan_jenis": 0.15,
    "dimensi_disharmoni": 0.20,
    "dimensi_kejelasan_rumusan": 0.10,
    "dimensi_kesesuaian_asas": 0.15,
    "dimensi_efektivitas": 0.15,
}


class BPHNEvaluator:
    """Evaluator Peraturan Perundang-undangan berbasis 6 Dimensi BPHN."""

    def __init__(self):
        self.llm = LLMConnector()
        self.kb = KBConnector()

    def _calculate_overall_score(self, dimension_scores: Dict[str, float]) -> float:
        """Menghitung total skor tertimbang (weighted score) 0 - 100."""
        total_score = 0.0
        for dim, weight in DIMENSION_WEIGHTS.items():
            score = dimension_scores.get(dim, 0.0)
            total_score += score * weight
        return round(total_score, 2)

    def _determine_recommendation(
        self,
        overall_score: float,
        critical_issues: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Menentukan rekomendasi tindak lanjut berdasarkan skor dan isu kritis:
        - DIPERTAHANKAN (Skor >= 85 dan tidak ada isu fatal)
        - DIUBAH / REVISI (Skor 60 - 84 atau ada disharmoni parsial)
        - DICABUT (Skor < 60 atau bertentangan dengan norma pokok Pancasila/UU di atasnya)
        """
        has_fatal_disharmony = any(
            issue.get("severity") == "FATAL" or issue.get("dimensi") == "dimensi_pancasila"
            for issue in critical_issues
        )

        if overall_score >= 85 and not has_fatal_disharmony:
            status = "DIPERTAHANKAN"
            rationale = "Regulasi memiliki kualitas tinggi, selaras dengan Pancasila, hierarki peraturan di atasnya, dan efektif dilaksanakan tanpa cacat substansial."
        elif overall_score >= 60 and not has_fatal_disharmony:
            status = "DIUBAH"
            rationale = "Regulasi masih relevan namun membutuhkan penyesuaian materi muatan, klarifikasi rumusan pasal ambigu, atau harmonisasi dengan regulasi sektoral terbaru."
        else:
            status = "DICABUT"
            rationale = "Regulasi memiliki benturan substansial dengan norma yang lebih tinggi, bertentangan dengan asas hukum pokok, atau menimbulkan beban implementasi yang tidak proporsional."

        return {
            "status": status,
            "overall_score": overall_score,
            "rationale": rationale,
            "has_fatal_issues": has_fatal_disharmony,
        }

    async def evaluate_regulation(
        self,
        regulation_text: str,
        regulation_title: str = "Peraturan Perundang-Undangan",
        regulation_type: str = "Peraturan Daerah / Peraturan Kepala Daerah",
        higher_regulations: Optional[List[str]] = None,
        sectoral_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Menjalankan Evaluasi 6 Dimensi Penuh terhadap Dokumen Regulasi.
        """
        system_prompt = """Anda adalah Tim Ahli Analisis dan Evaluasi Hukum BPHN (Badan Pembinaan Hukum Nasional) Kementerian Hukum dan HAM.
Tugas Anda adalah melakukan audit dan penilaian hukum komprehensif terhadap naskah peraturan berdasarkan Pedoman Evaluasi Peraturan Perundang-undangan Nomor PHN-HN.01.03-07.

Anda WAJIB mengevaluasi 6 Dimensi Penilaian:
1. Dimensi Pancasila (Nilai Ketuhanan, Kemanusiaan, Persatuan, Kerakyatan, Keadilan Sosial).
2. Dimensi Ketepatan Jenis PUU (Kesesuaian materi muatan dengan hierarki UU No. 12/2011 jo UU No. 15/2019).
3. Dimensi Disharmoni Pengaturan (Uji vertikal terhadap UU/PP di atasnya dan uji horizontal terhadap peraturan setingkat).
4. Dimensi Kejelasan Rumusan (Kebakuan bahasa, ketiadaan istilah multitafsir, kepastian subjek & objek norma).
5. Dimensi Kesesuaian Asas Bidang Hukum (Asas-asas spesifik dalam bidang urusan terkait, misal asas desentralisasi, kepastian hukum, keterbukaan).
6. Dimensi Efektivitas Pelaksanaan (Keberlakuan sosiologis, kesiapan aparatur pelaksana, beban kepatuhan masyarakat, sanksi/insentif).

Setiap dimensi dinilai dengan skor 0 - 100.
Berikan output HANYA dalam format JSON valid tanpa teks pengantar atau penutup."""

        higher_regs_str = ", ".join(higher_regulations) if higher_regulations else "UU No. 23 Tahun 2014, UU No. 12 Tahun 2011"
        sector_str = sectoral_domain or "Pemerintahan Daerah & Pelayanan Publik"

        prompt = f"""Lakukan Evaluasi 6 Dimensi BPHN terhadap regulasi berikut:

Judul: {regulation_title}
Jenis: {regulation_type}
Sektor/Bidang: {sector_str}
Regulasi Rujukan / Yang Lebih Tinggi: {higher_regs_str}

Naskah Regulasi:
\"\"\"
{regulation_text[:6000]}
\"\"\"

Format Response JSON yang WAJIB dipatuhi:
{{
    "identitas": {{
        "judul": "{regulation_title}",
        "jenis": "{regulation_type}",
        "sektor": "{sector_str}"
    }},
    "evaluasi_dimensi": {{
        "dimensi_pancasila": {{
            "skor": 85.0,
            "analisis": "Analisis keselarasan dengan 5 sila Pancasila...",
            "kesimpulan": "Selaras / Terdapat Catatan",
            "pasal_terkait": ["Pasal 1", "Pasal 3"]
        }},
        "dimensi_ketepatan_jenis": {{
            "skor": 90.0,
            "analisis": "Analisis apakah materi muatan tepat diatur dalam jenis regulasi ini...",
            "kesimpulan": "Tepat / Kurang Tepat",
            "pasal_terkait": []
        }},
        "dimensi_disharmoni": {{
            "skor": 75.0,
            "analisis": "Analisis benturan vertikal dengan {higher_regs_str} dan horizontal...",
            "potensi_disharmoni": [
                {{"pasal": "Pasal X", "berbenturan_dengan": "UU Y Pasal Z", "uraian": "..."}}
            ]
        }},
        "dimensi_kejelasan_rumusan": {{
            "skor": 80.0,
            "analisis": "Analisis kebakuan bahasa hukum dan potensi multitafsir...",
            "pasal_ambigu": ["Pasal A", "Pasal B"]
        }},
        "dimensi_kesesuaian_asas": {{
            "skor": 85.0,
            "analisis": "Analisis kesesuaian dengan asas hukum sektoral {sector_str}..."
        }},
        "dimensi_efektivitas": {{
            "skor": 70.0,
            "analisis": "Analisis daya laku sosiologis, kesiapan institusi pelaksana, dan beban masyarakat...",
            "kendala_implementasi": ["Kendala 1", "Kendala 2"]
        }}
    }},
    "isu_kritis": [
        {{"dimensi": "dimensi_disharmoni", "pasal": "Pasal X", "severity": "MEDIUM/FATAL", "deskripsi": "..."}}
    ],
    "rekomendasi_pasal_per_pasal": [
        {{"pasal": "Pasal 1", "status": "DIPERTAHANKAN/DIUBAH", "saran_perbaikan": "..."}}
    ]
}}
"""
        logger.info(f"Memulai Evaluasi 6 Dimensi BPHN untuk '{regulation_title}'...")
        res = await self.llm.generate(prompt=prompt, system_prompt=system_prompt)

        if not res.get("success"):
            return {
                "success": False,
                "error": f"LLM generation failed: {res.get('error')}",
            }

        try:
            content = res.get("content", "").strip()
            # Clean possible markdown block
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            parsed_data = json.loads(content.strip())
            
            # Extract scores and compute weighted total
            dim_eval = parsed_data.get("evaluasi_dimensi", {})
            dim_scores = {
                k: float(dim_eval.get(k, {}).get("skor", 70.0))
                for k in DIMENSION_WEIGHTS
            }
            
            overall_score = self._calculate_overall_score(dim_scores)
            issues = parsed_data.get("isu_kritis", [])
            recommendation = self._determine_recommendation(overall_score, issues)

            return {
                "success": True,
                "identitas": parsed_data.get("identitas", {}),
                "skor_akhir": overall_score,
                "bobot_dimensi": DIMENSION_WEIGHTS,
                "skor_per_dimensi": dim_scores,
                "evaluasi_dimensi": dim_eval,
                "rekomendasi": recommendation,
                "isu_kritis": issues,
                "rekomendasi_pasal_per_pasal": parsed_data.get("rekomendasi_pasal_per_pasal", []),
                "model_used": res.get("model_used"),
            }

        except json.JSONDecodeError as je:
            logger.error(f"Gagal mem-parse JSON hasil evaluasi: {je}")
            return {
                "success": False,
                "error": f"JSON parse error: {je}",
                "raw_response": res.get("content"),
            }
