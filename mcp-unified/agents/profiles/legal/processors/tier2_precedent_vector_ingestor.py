"""
tier2_precedent_vector_ingestor.py — Dynamic Vector RAG Processor for Legal Agent (TASK-130).
Manages structured ingestion, vectorization, and on-demand semantic search for Judicial Precedents (MA & MK)
under namespace 'putusan_pengadilan'.
"""

import json
import logging
import math
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("tier2_vector_ingestor")


class PrecedentDocItem(BaseModel):
    """Skema Terstruktur Dokumen Putusan Yudisial Tier 2."""
    case_id: str
    nomor_perkara: str
    lembaga_peradilan: str  # 'Mahkamah Agung' | 'Mahkamah Konstitusi' | 'PTUN'
    tahun: int
    judul_kasus: str
    pemohon_penggugat: Optional[str] = None
    termohon_tergugat: Optional[str] = None
    norma_diuji: str
    duduk_perkara_ringkas: str
    ratio_decidendi: str
    amar_putusan: str
    status_norma: str  # 'Batal' | 'Inkonstitusional Bersyarat' | 'Ditolak' | 'Tidak Dapat Diterima' | 'Dikabulkan Sebagian'
    bidang_hukum: str  # 'Pajak Daerah' | 'BUMD' | 'Perizinan' | 'Tata Ruang' | 'Kepegawaian' | 'PBJ' | 'Pemerintahan Desa'
    kata_kunci: List[str] = Field(default_factory=list)


def format_precedent_for_embedding(item: PrecedentDocItem) -> str:
    """Membuat representasi teks padat semantik tinggi untuk model embedding."""
    return (
        f"Lembaga: {item.lembaga_peradilan}\n"
        f"Nomor Perkara: {item.nomor_perkara} ({item.tahun})\n"
        f"Judul: {item.judul_kasus}\n"
        f"Bidang: {item.bidang_hukum}\n"
        f"Norma Diuji: {item.norma_diuji}\n"
        f"Ratio Decidendi: {item.ratio_decidendi}\n"
        f"Amar Putusan: {item.amar_putusan}\n"
        f"Status Norma: {item.status_norma}\n"
        f"Keywords: {', '.join(item.kata_kunci)}"
    )


# In-memory structured repository for instant high-speed lookup and testing
_TIER2_IN_MEMORY_STORE: Dict[str, PrecedentDocItem] = {}


def _auto_seed_tier2_store():
    """Auto-seed store dari curated dataset jika file tersedia."""
    # Find MCP project root by traversing up to 'storage'
    cur = Path(__file__).resolve()
    mcp_root = None
    for p in cur.parents:
        if (p / "storage" / "raw_documents" / "data" / "curated_judicial_precedents.json").exists():
            mcp_root = p
            break
    if mcp_root:
        dataset_path = mcp_root / "storage" / "raw_documents" / "data" / "curated_judicial_precedents.json"
        try:
            with open(dataset_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for raw in data:
                    item = PrecedentDocItem(**raw)
                    _TIER2_IN_MEMORY_STORE[item.case_id] = item
        except Exception as e:
            logger.warning(f"Failed to auto-seed tier2 precedents: {e}")


_auto_seed_tier2_store()


def register_tier2_precedent(item: PrecedentDocItem) -> None:
    """Registrasi putusan ke store Tier 2."""
    _TIER2_IN_MEMORY_STORE[item.case_id] = item


def get_all_tier2_precedents() -> List[PrecedentDocItem]:
    """Mengambil seluruh putusan Tier 2 terdaftar."""
    return list(_TIER2_IN_MEMORY_STORE.values())


STOP_WORDS = {"bagaimana", "apakah", "apa", "dan", "yang", "di", "ke", "dari", "untuk", "pada", "oleh", "dengan", "ini", "itu", "terkait", "terhadap", "adalah", "saya", "kami", "mohon", "tolong"}


def _simple_keyword_overlap_score(query: str, text: str) -> float:
    """Menghitung skor relevansi berbasis leksikal/token overlap (fallback saat embedding offline)."""
    raw_q_words = [w for w in query.lower().replace("-", " ").replace("/", " ").replace("?", " ").split() if len(w) > 2]
    q_words = set([w for w in raw_q_words if w not in STOP_WORDS])
    if not q_words:
        q_words = set(raw_q_words)
    if not q_words:
        return 0.0
    t_words = set(text.lower().replace("-", " ").replace("/", " ").split())
    intersection = q_words.intersection(t_words)
    return len(intersection) / len(q_words)


def search_tier2_precedents(
    query: str,
    top_k: int = 5,
    bidang_filter: Optional[str] = None,
    min_score: float = 0.15
) -> List[Dict[str, Any]]:
    """
    Pencarian semantik/kombinasi terhadap Tier 2 Precedents di memory & vector store.
    """
    results = []
    
    for case_id, item in _TIER2_IN_MEMORY_STORE.items():
        if bidang_filter and bidang_filter.lower() not in item.bidang_hukum.lower():
            continue
            
        full_text = format_precedent_for_embedding(item)
        score = _simple_keyword_overlap_score(query, full_text)
        
        # Keyword boosts
        for kw in item.kata_kunci:
            if kw.lower() in query.lower():
                score += 0.25
        if item.nomor_perkara.lower() in query.lower():
            score += 0.5
        if item.bidang_hukum.lower() in query.lower():
            score += 0.2
            
        score = min(1.0, score)
        
        if score >= min_score:
            results.append({
                "case_id": item.case_id,
                "nomor_perkara": item.nomor_perkara,
                "lembaga": item.lembaga_peradilan,
                "tahun": item.tahun,
                "judul": item.judul_kasus,
                "norma_diuji": item.norma_diuji,
                "ratio_decidendi": item.ratio_decidendi,
                "amar": item.amar_putusan,
                "status_norma": item.status_norma,
                "bidang": item.bidang_hukum,
                "relevance_score": round(score, 3)
            })
            
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results[:top_k]
