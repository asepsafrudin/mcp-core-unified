"""
statutory_rag_verifier.py — Deep Verification & Authentic Statutory Cross-Referencing.
Mencocokkan klausul delegasi pada regulasi turunan dengan teks otentik UU induk via Knowledge RAG.
"""

import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Fallback Statutory Corpus untuk pasal-pasal kunci jika KB RAG sedang cold-start
FALLBACK_STATUTORY_CORPUS = {
    "pp_47_2015_pasal_96": (
        "Pasal 96 Peraturan Pemerintah Nomor 47 Tahun 2015:\n"
        "(1) Pemerintah Daerah Kabupaten/Kota mengalokasikan Alokasi Dana Desa (ADD) dalam APBD setiap tahun anggaran.\n"
        "(4) Pengalokasian ADD sebagaimana dimaksud pada ayat (1) ditetapkan dengan Peraturan Bupati/Walikota.\n"
        "(7) Ketentuan lebih lanjut mengenai tata cara pengalokasian dan penyaluran ADD diatur dengan Peraturan Bupati/Walikota."
    ),
    "uu_6_2014_pasal_72": (
        "Pasal 72 Undang-Undang Nomor 6 Tahun 2014 tentang Desa:\n"
        "(1) Pendapatan Desa sebagaimana dimaksud dalam Pasal 71 ayat (2) bersumber dari:\n"
        "    c. bagian dari hasil pajak daerah dan retribusi daerah Kabupaten/Kota;\n"
        "    d. alokasi dana Desa yang merupakan bagian dari dana perimbangan yang diterima Kabupaten/Kota;\n"
        "(3) Bagian hasil pajak daerah dan retribusi daerah sebagaimana dimaksud pada ayat (1) huruf c paling sedikit 10% dari pajak dan retribusi daerah."
    ),
    "uu_1_2022_pasal_139": (
        "Pasal 139 Undang-Undang Nomor 1 Tahun 2022 tentang HKPD:\n"
        "Hasil penerimaan Pajak Daerah dan Retribusi Daerah sebagian dialokasikan kepada Desa paling sedikit 10% (sepuluh persen) dari realisasi penerimaan Pajak Daerah dan Retribusi Daerah Kabupaten/Kota."
    ),
    "uu_7_2014_pasal_38": (
        "Pasal 38 Undang-Undang Nomor 7 Tahun 2014 tentang Perdagangan:\n"
        "(1) Pemerintah mengatur kegiatan Perdagangan Luar Negeri melalui kebijakan dan pengendalian di bidang Ekspor dan Impor.\n"
        "(2) Pengendalian di bidang Ekspor dan Impor sebagaimana dimaksud pada ayat (1) dilakukan melalui perizinan, standardisasi, pelarangan, dan/atau pembatasan."
    ),
}


def search_authentic_statute(query: str, namespace: str = "legal_regulations") -> Dict[str, Any]:
    """
    Menarik kutipan otentik UU Induk dari Knowledge Bridge RAG atau Statutory Corpus.
    """
    cleaned_query = query.lower()
    
    # 1. Cek Fallback Corpus Lokal Cepat
    for key, text in FALLBACK_STATUTORY_CORPUS.items():
        terms = key.split("_")
        if all(t in cleaned_query for t in terms if len(t) > 2):
            return {
                "source": "statutory_corpus",
                "matched_key": key,
                "authentic_text": text,
                "confidence": 0.98,
            }

    # 2. Coba Query RAG via KnowledgeBridge jika tersedia
    try:
        from ..connectors.kb_connector import get_knowledge_bridge
        bridge = get_knowledge_bridge()
        if bridge:
            res = bridge.query(query, namespace=namespace)
            if res.success and res.context:
                return {
                    "source": "knowledge_bridge_rag",
                    "matched_key": query,
                    "authentic_text": res.context,
                    "confidence": 0.85,
                }
    except Exception as e:
        logger.warning(f"RAG query skipped: {e}")

    return {
        "source": "general_legal_knowledge",
        "matched_key": query,
        "authentic_text": f"Kutipan teks otentik untuk query '{query}' dirujuk berdasar asas-asas umum PUU.",
        "confidence": 0.70,
    }


def verify_delegation_scope(
    parent_law_query: str,
    derived_regulation_clause: str,
) -> Dict[str, Any]:
    """
    Membandingkan lingkup delegasi UU Induk dengan klausul regulasi turunan.
    """
    statute_info = search_authentic_statute(parent_law_query)
    auth_text = statute_info.get("authentic_text", "")

    # Deteksi apakah regulasi turunan menciptakan monopoli/larangan baru tanpa mandat eksplisit
    is_ultra_vires = False
    indicators = []

    if "monopoli" in derived_regulation_clause.lower() or "kanal tunggal" in derived_regulation_clause.lower() or "hanya dapat dilakukan oleh bumn" in derived_regulation_clause.lower():
        if "bumn" not in auth_text.lower() and "monopoli" not in auth_text.lower():
            is_ultra_vires = True
            indicators.append("regulasi_turunan_menciptakan_mekanisme_baru_di_luar_bunyi_delegasi")

    return {
        "is_ultra_vires": is_ultra_vires,
        "indicators": indicators,
        "authentic_statute_used": auth_text,
        "statute_source": statute_info.get("source"),
    }
