"""
Research Tools - MCP Tools untuk AI-powered Web Research
=========================================================
Menggunakan VaneConnector (SearxNG + Groq) untuk riset cepat dan akurat.

Tools yang tersedia:
    - vane_search:        Pencarian cepat dengan sintesis AI
    - vane_deep_research: Riset mendalam multi-query + simpan ke KB
    - vane_legal_search:  Riset khusus hukum Indonesia (domain filter)

Digunakan oleh: ResearchAgent, LegalAgent
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

# Add parent path untuk imports MCP
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# Import VaneConnector
try:
    from integrations.vane_connector import VaneConnector
    _vane_available = True
except ImportError:
    try:
        from mcp_unified.integrations.vane_connector import VaneConnector
        _vane_available = True
    except ImportError:
        _vane_available = False
        logger.warning("VaneConnector tidak tersedia, research tools akan terbatas")


# ============================================================
# SINGLETON CONNECTOR
# ============================================================
_connector: Optional["VaneConnector"] = None

def _get_connector() -> "VaneConnector":
    """Dapatkan singleton VaneConnector."""
    global _connector
    if _connector is None and _vane_available:
        _connector = VaneConnector()
    if _connector is None:
        raise RuntimeError("VaneConnector tidak tersedia. Pastikan Vane Docker berjalan.")
    return _connector


# ============================================================
# TOOL: vane_search
# ============================================================
async def vane_search(
    query: str,
    num_results: int = 8,
    mode: str = "balanced",
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    MCP Tool: Pencarian web dengan sintesis AI via Vane/Groq.

    Melakukan pencarian menggunakan SearxNG dan mensintesis jawaban
    dengan model qwen/qwen3-32b. Sumber otomatis difilter untuk
    konten relevan Indonesia.

    Args:
        query:         Pertanyaan atau topik yang ingin diriset
        num_results:   Jumlah sumber web yang diambil (default: 8)
        mode:          Mode pencarian: "speed" | "balanced" | "quality"
        system_prompt: Prompt sistem kustom untuk memengaruhi gaya jawaban

    Returns:
        {
            "success":    bool,
            "answer":     str,    # Jawaban tersintesis dengan sitasi
            "sources":    list,   # Daftar sumber [{title, url, snippet}]
            "model_used": str,    # Model AI yang digunakan
            "timestamp":  str
        }

    Example:
        result = await vane_search("dasar hukum SPM bidang kesehatan")
        print(result["answer"])
    """
    logger.info(f"[vane_search] Query: {query!r}, mode={mode}")
    try:
        conn = _get_connector()
        # Sesuaikan jumlah hasil dengan mode
        if mode == "speed":
            num_results = min(num_results, 5)
        elif mode == "quality":
            num_results = max(num_results, 10)

        # Run sync connector di thread pool agar tidak block asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: conn.research(
                query=query,
                num_results=num_results,
                system_prompt=system_prompt,
            )
        )
        result["query"] = query
        result["mode"]  = mode
        return result
    except Exception as e:
        logger.error(f"[vane_search] Error: {e}")
        return {
            "success": False,
            "error":   str(e),
            "query":   query,
        }


# ============================================================
# TOOL: vane_legal_search
# ============================================================
async def vane_legal_search(
    query: str,
    regulation: str = "UU 23/2014",
    num_results: int = 10,
) -> Dict[str, Any]:
    """
    MCP Tool: Riset hukum Indonesia dengan konteks regulasi spesifik.

    Sama seperti vane_search tapi dengan system prompt yang dioptimalkan
    untuk analisis hukum dan referensi ke regulasi tertentu.

    Args:
        query:       Pertanyaan hukum
        regulation:  Regulasi referensi (default: "UU 23/2014")
        num_results: Jumlah sumber (default: 10, lebih banyak = lebih akurat)

    Returns:
        Sama dengan vane_search, ditambah field "regulation"

    Example:
        result = await vane_legal_search(
            "kewenangan pemerintah daerah bidang kesehatan",
            regulation="UU 23/2014 dan PP 2/2018"
        )
    """
    legal_system_prompt = (
        f"Anda adalah ahli hukum tata negara Indonesia yang spesialis dalam {regulation}. "
        f"Analisis pertanyaan berikut dengan mengacu pada ketentuan hukum dari sumber yang diberikan. "
        f"Sertakan: (1) Dasar hukum/pasal yang relevan, (2) Penjelasan substantif, "
        f"(3) Implikasi praktis, (4) Sitasi sumber [nomor]. "
        f"Gunakan terminologi hukum yang tepat dalam Bahasa Indonesia formal."
    )

    result = await vane_search(
        query=f"{query} {regulation}",
        num_results=num_results,
        mode="quality",
        system_prompt=legal_system_prompt,
    )
    result["regulation"] = regulation
    return result


# ============================================================
# TOOL: vane_deep_research
# ============================================================
async def vane_deep_research(
    main_query: str,
    sub_queries: Optional[List[str]] = None,
    namespace: str = "legal_research_deep",
    save_to_kb: bool = False,
) -> Dict[str, Any]:
    """
    MCP Tool: Riset mendalam dengan multiple queries.

    Melakukan serangkaian pencarian untuk topik yang kompleks,
    menggabungkan hasilnya menjadi satu laporan komprehensif,
    dan secara opsional menyimpan ke Knowledge Base.

    Args:
        main_query:  Query utama / topik riset
        sub_queries: Daftar sub-query tambahan (auto-generated jika kosong)
        namespace:   Namespace KB untuk penyimpanan (default: "legal_research_deep")
        save_to_kb:  Simpan hasil ke Knowledge Base (default: False)

    Returns:
        {
            "success":    bool,
            "summary":    str,   # Ringkasan gabungan semua riset
            "sections":   list,  # Hasil tiap sub-query
            "all_sources": list, # Semua sumber unik
            "namespace":  str,
            "saved_to_kb": bool
        }
    """
    logger.info(f"[vane_deep_research] Main query: {main_query!r}")

    # Generate sub-queries jika tidak disediakan
    if not sub_queries:
        sub_queries = _generate_sub_queries(main_query)

    all_queries = [main_query] + sub_queries
    sections    = []
    all_sources = {}  # Dedup by URL

    # Jalankan semua query secara berurutan
    for i, q in enumerate(all_queries):
        logger.info(f"[vane_deep_research] ({i+1}/{len(all_queries)}) {q!r}")
        result = await vane_legal_search(q, num_results=8)

        if result.get("success"):
            sections.append({
                "query":  q,
                "answer": result["answer"],
                "model":  result.get("model_used", ""),
            })
            # Kumpulkan sumber unik
            for s in result.get("sources", []):
                url = s.get("url", "")
                if url and url not in all_sources:
                    all_sources[url] = s

    if not sections:
        return {
            "success": False,
            "error":   "Semua sub-query gagal",
            "main_query": main_query,
        }

    # Gabungkan semua jawaban menjadi summary
    combined = "\n\n".join(
        f"### {s['query']}\n{s['answer']}" for s in sections
    )

    result_data = {
        "success":     True,
        "main_query":  main_query,
        "summary":     combined,
        "sections":    sections,
        "all_sources": list(all_sources.values()),
        "source_count": len(all_sources),
        "namespace":   namespace,
        "saved_to_kb": False,
    }

    # Simpan ke KB jika diminta
    if save_to_kb:
        try:
            saved = await _save_to_knowledge_base(main_query, combined, all_sources, namespace)
            result_data["saved_to_kb"] = saved
        except Exception as e:
            logger.warning(f"[vane_deep_research] KB save failed: {e}")

    return result_data


# ============================================================
# TOOL: vane_gap_fill (untuk UU 23/2014 gap analysis)
# ============================================================
async def vane_gap_fill(
    sub_urusan: str,
    bidang: str,
    context: str = "UU 23/2014 lampiran pemerintahan daerah",
) -> Dict[str, Any]:
    """
    MCP Tool: Isi gap data sub-urusan yang kosong di laporan UU 23/2014.

    Khusus dirancang untuk mengisi data yang hilang dalam inventory
    sub-urusan berdasarkan UU 23/2014.

    Args:
        sub_urusan: Nama sub-urusan yang datanya kosong
        bidang:     Bidang urusan (misal: Kesehatan, Pendidikan)
        context:    Konteks tambahan untuk pencarian

    Returns:
        {
            "success":     bool,
            "sub_urusan":  str,
            "bidang":      str,
            "data_filled": dict,  # Data yang berhasil diisi
            "sources":     list
        }
    """
    query = (
        f"pembagian kewenangan sub urusan {sub_urusan} bidang {bidang} "
        f"pemerintah pusat provinsi kabupaten kota {context}"
    )

    gap_prompt = (
        f"Anda mengisi data kosong untuk sub-urusan '{sub_urusan}' dalam bidang '{bidang}' "
        f"berdasarkan UU 23/2014 tentang Pemerintahan Daerah. "
        f"Berikan: (1) Deskripsi sub-urusan, (2) Kewenangan Pemerintah Pusat, "
        f"(3) Kewenangan Pemerintah Provinsi, (4) Kewenangan Pemerintah Kab/Kota, "
        f"(5) Standar Pelayanan Minimal jika ada, (6) Dasar hukum spesifik. "
        f"Format jawaban dalam poin-poin yang terstruktur."
    )

    result = await vane_search(
        query=query,
        num_results=10,
        mode="quality",
        system_prompt=gap_prompt,
    )

    if result.get("success"):
        return {
            "success":     True,
            "sub_urusan":  sub_urusan,
            "bidang":      bidang,
            "data_filled": {
                "deskripsi":           result["answer"],
                "sumber_data":         [s["url"] for s in result.get("sources", [])[:5]],
                "model_used":          result.get("model_used", ""),
                "confidence":          "medium",  # berdasarkan snippet saja
            },
            "sources":     result.get("sources", []),
        }
    return {
        "success":    False,
        "sub_urusan": sub_urusan,
        "bidang":     bidang,
        "error":      result.get("error", "Unknown error"),
    }


# ============================================================
# HELPERS
# ============================================================
def _generate_sub_queries(main_query: str) -> List[str]:
    """Generate sub-queries dari main_query untuk deep research."""
    # Untuk sekarang: sub-query sederhana dari kata kunci utama
    # TODO: gunakan Groq untuk generate sub-queries secara dinamis
    return [
        f"{main_query} dasar hukum pasal",
        f"{main_query} penjelasan implementasi daerah",
        f"{main_query} standar pelayanan minimal SPM",
    ]


async def _save_to_knowledge_base(
    query: str,
    content: str,
    sources: dict,
    namespace: str,
) -> bool:
    """Simpan hasil riset ke Knowledge Base (PostgreSQL + pgvector)."""
    try:
        from knowledge.store import KnowledgeStore
        kb = KnowledgeStore()
        await kb.store(
            content=content,
            namespace=namespace,
            metadata={
                "query":    query,
                "sources":  list(sources.keys())[:10],
                "type":     "vane_research",
            }
        )
        return True
    except Exception as e:
        logger.warning(f"KB store failed: {e}")
        return False


# ============================================================
# QUICK TEST
# ============================================================
if __name__ == "__main__":
    async def main():
        print("\n" + "="*60)
        print("RESEARCH TOOLS TEST")
        print("="*60)

        # Test 1: vane_search
        print("\n[Test 1] vane_search")
        r = await vane_search(
            "standar pelayanan minimal bidang kesehatan UU 23 2014",
            num_results=6,
            mode="balanced"
        )
        if r["success"]:
            print(f"✅ {r['model_used']} — {len(r['answer'])} karakter")
            print(r["answer"][:400])
        else:
            print(f"❌ {r['error']}")

        # Test 2: vane_legal_search
        print("\n[Test 2] vane_legal_search")
        r2 = await vane_legal_search(
            "pembagian kewenangan urusan ketentraman dan ketertiban umum",
            regulation="UU 23/2014"
        )
        if r2["success"]:
            print(f"✅ {r2['model_used']} — {len(r2['answer'])} karakter")
            print(r2["answer"][:400])
        else:
            print(f"❌ {r2['error']}")

    asyncio.run(main())
