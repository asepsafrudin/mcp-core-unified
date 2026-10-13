"""
Research Tools - MCP Tools untuk AI-powered Web Research
=========================================================
Menggunakan VaneConnector (SearxNG + Groq) untuk riset cepat dan akurat.

Tools yang tersedia:
    - vane_search:           Pencarian cepat dengan sintesis AI
    - vane_deep_research:    Riset mendalam multi-query + simpan ke KB
    - vane_legal_search:     Riset khusus hukum Indonesia (domain filter)
    - vane_gap_fill:         Pengisian data gap urusan/sub-urusan UU 23/2014
    - vane_7pillars_analyze: Analisis Naskah/Regulasi Taksonomi 7 Pilar DIM v2.0 (Track A Ditjen PP)

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

# Import VaneConnector & MemForge normalizer
try:
    from integrations.vane_connector import VaneConnector, normalize_research_namespace
    _vane_available = True
except ImportError:
    try:
        from mcp_unified.integrations.vane_connector import VaneConnector, normalize_research_namespace
        _vane_available = True
    except ImportError:
        _vane_available = False
        def normalize_research_namespace(ns):
            return ns or "puu:regulasi:pencari"
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

        # Eksekusi riset asinkron langsung (non-blocking)
        result = await conn.research_async(
            query=query,
            num_results=num_results,
            system_prompt=system_prompt,
            mode=mode,
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
    namespace: str = "puu:regulasi:pencari",
    save_to_kb: bool = False,
) -> Dict[str, Any]:
    """
    MCP Tool: Riset mendalam dengan multiple queries.

    Melakukan serangkaian pencarian untuk topik yang kompleks,
    menggabungkan hasilnya menjadi satu laporan komprehensif,
    dan secara opsional menyimpan ke MemForge Native / Knowledge Base.

    Args:
        main_query:  Query utama / topik riset
        sub_queries: Daftar sub-query tambahan (auto-generated jika kosong)
        namespace:   Namespace MemForge (default: "puu:regulasi:pencari")
        save_to_kb:  Simpan hasil ke MemForge/KB (default: False)

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
# TOOL: vane_7pillars_analyze (Track A Ditjen PP & Bangda)
# ============================================================
async def vane_7pillars_analyze(
    title: str,
    draft_content: str,
    context: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    cross_references: Optional[List[Dict[str, str]]] = None,
    save_to_kb: bool = False,
    namespace: str = "puu:regulasi:pencari",
) -> Dict[str, Any]:
    """
    MCP Tool: Analisis Naskah/Regulasi Berbasis Taksonomi 7 Pilar DIM v2.0 (Track A Ditjen PP).

    Mengevaluasi draf regulasi daerah terhadap 7 Pilar Legislatif:
      1. Kewenangan & Yurisdiksi (Urusan Konkuren UU 23/2014 & Ultra Vires Check)
      2. Kelembagaan & Tata Kelola (OPD & Struktur Pelaksana)
      3. Hierarki Peraturan & Landasan Hukum (UU 12/2011 jo UU 13/2022)
      4. Personil & SDM Aparatur (PPNS & Pejabat Fungsional Perancang/Pengawas)
      5. Finansial, Beban Fiskal & APBD (Kepatuhan UU HKPD 1/2022 & Standar Biaya)
      6. Sarana Prasarana & Fasilitas Standar (SPBE & Infrastruktur Layanan Publik)
      7. Prosedur, Standar SPM & Penegakan (SOP & Sanksi Bertahap)
    Serta menyusun Matriks Disposisi DIM (APPROVED, PARKING_LOT, ENCLAVE,
    ALTERNATIVE_VEHICLE, OUT_OF_SCOPE, FUTURE_AGENDA).

    Args:
        title:            Judul rancangan peraturan / regulasi yang dievaluasi
        draft_content:    Teks draf pasal/materi muatan yang dianalisis
        context:          Konteks/catatan latar belakang analisis
        metadata:         Metadata tambahan (misal: jenis regulasi, pemda pemrakarsa)
        cross_references: Referensi silang peraturan terkait
        save_to_kb:       Simpan hasil evaluasi ke MemForge Native (default: False)
        namespace:        Namespace MemForge (default: "puu:regulasi:pencari")

    Returns:
        {
            "success":           bool,
            "title":             str,
            "analysis_7pillars": str,
            "model_used":        str,
            "timestamp":         str,
            "analysis_version":  str,
            "pillars_evaluated": int,
            "namespace":         str,
            "saved_to_kb":       bool
        }
    """
    logger.info(f"[vane_7pillars_analyze] Title: {title!r}")
    try:
        conn = _get_connector()
        result = await conn.synthesize_7_pillars_async(
            title=title,
            draft_text=draft_content,
            metadata=metadata,
            context_notes=context,
            cross_references=cross_references,
        )

        result["namespace"] = namespace
        result["saved_to_kb"] = False

        if result.get("success") and save_to_kb:
            analysis_text = result.get("analysis_7pillars", "")
            if analysis_text:
                saved = await _save_to_knowledge_base(
                    query=f"Analisis 7 Pilar DIM: {title}",
                    content=analysis_text,
                    sources={"self": {"title": title, "url": f"internal://ranperda/{title}"}},
                    namespace=namespace,
                )
                result["saved_to_kb"] = bool(saved)

        return result
    except Exception as e:
        logger.error(f"[vane_7pillars_analyze] Error: {e}")
        return {
            "success":           False,
            "error":             str(e),
            "title":             title,
            "analysis_version":  "7Pillars-v2.0-DitjenPP-Bangda",
            "pillars_evaluated": 7,
            "namespace":         namespace,
            "saved_to_kb":       False,
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
    """
    Simpan hasil riset ke MemForge Native (PostgreSQL pgvector / SQLite-vec).
    Mengikuti Zero-Leakage Policy dan taksonomi resmi PUU.
    """
    target_ns = normalize_research_namespace(namespace)
    try:
        conn = _get_connector()
        memforge_res = await conn.save_to_memforge_async(
            result={
                "query": query,
                "answer": content,
                "sources": [{"url": u} for u in list(sources.keys())[:10]],
            },
            namespace=target_ns,
            importance=0.85,
            agent_id="puu:regulasi:pencari",
        )
        if memforge_res.get("success"):
            logger.info(f"Riset tersimpan ke MemForge namespace '{target_ns}': {memforge_res.get('memory_id')}")
            return True

        # Fallback ke KnowledgeStore jika MemForge belum aktif
        from knowledge.store import KnowledgeStore
        kb = KnowledgeStore()
        await kb.store(
            content=content,
            namespace=target_ns,
            metadata={
                "query":   query,
                "sources": list(sources.keys())[:10],
                "type":    "vane_research",
            }
        )
        return True
    except Exception as e:
        logger.warning(f"Simpan hasil riset gagal: {e}")
        return False


def register_research_tools(registry) -> int:
    """Register Vane AI Research tools into execution.registry."""
    tools_list = [vane_search, vane_deep_research, vane_legal_search, vane_gap_fill, vane_7pillars_analyze]
    registered = 0
    for fn in tools_list:
        try:
            name = getattr(fn, "__name__", None)
            if name and registry.get_tool(name) is None:
                registry.register(fn, name=name, category="research")
                registered += 1
        except Exception as e:
            logger.warning(f"Failed to register research tool: {e}")
    return registered


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
