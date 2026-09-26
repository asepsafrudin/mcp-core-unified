"""
LangGraph Orchestrator Node for Serena Symbol Lookup & Routing (TASK-125 / TASK-120).

Provides centralized, token-optimized symbol cache queries with explicit routing:
- CURATED: direct to generator (golden snippets available)
- NOT_CURATED (with informative docstring): direct to generator with docstring context
- NOT_CURATED (thin docstring): route to full_source_fetch_node or docstring_full fallback
- NOT_FOUND: route to llm_knowledge_fallback_node (explicit flag)
- ERROR: route to lookup_error_node (no silent failures)
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Optional, TypedDict

from memory.symbol_indexer.tools import get_symbol_info

logger = logging.getLogger("symbol_lookup_node")


# ---------------------------------------------------------------------------
# State & Enums
# ---------------------------------------------------------------------------

class LookupOutcome(str, Enum):
    CURATED = "curated"          # usage_status == "curated", punya snippet nyata
    NOT_CURATED = "not_curated"  # symbol ada, tapi belum ada curated pattern
    NOT_FOUND = "not_found"      # symbol tidak ditemukan sama sekali
    ERROR = "error"              # gagal parse / exception


class AgentState(TypedDict, total=False):
    # Input
    symbol_path: str
    requested_detail: str  # "summary" | "usage" | "full"
    query_context: Optional[str]

    # Output dari symbol_lookup_node
    symbol_info: Optional[dict[str, Any]]
    lookup_outcome: str          # nilai dari LookupOutcome
    token_cost: int

    # Dipakai node berikutnya untuk keputusan routing & context
    needs_full_source: bool
    has_full_docstring: bool     # True kalau docstring_full tersedia sebagai cheap fallback
    needs_llm_fallback: bool     # True kalau not_found / error / thin doc
    routing_reason: str          # Penjelasan deterministik untuk observabilitas

    # Output dari full_source_fetch_node
    source_snippet: Optional[str]
    source_lines_range: Optional[str]

    # Prompt composer & generator output
    composed_prompt: Optional[str]
    generated_code: Optional[str]
    _error: Optional[str]


# ---------------------------------------------------------------------------
# Node 1: symbol_lookup_node
# ---------------------------------------------------------------------------

async def symbol_lookup_node(state: AgentState) -> AgentState:
    """
    Satu-satunya pintu masuk ke symbol cache (Redis / LTM).
    Menentukan outcome (curated / not_curated / not_found / error)
    dan menyiapkan flag routing deterministik untuk conditional edge.
    """
    symbol_path = state.get("symbol_path", "").strip()
    detail_level = state.get("requested_detail", "usage")

    if not symbol_path:
        return {
            **state,
            "symbol_info": None,
            "lookup_outcome": LookupOutcome.ERROR.value,
            "needs_full_source": False,
            "has_full_docstring": False,
            "needs_llm_fallback": True,
            "token_cost": 0,
            "routing_reason": "symbol_path is empty",
            "_error": "Empty symbol_path provided to symbol_lookup_node",
        }

    try:
        raw = await get_symbol_info(symbol_path, detail_level=detail_level)
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 — tangkap luas di boundary node
        logger.error(f"symbol_lookup_node failed for {symbol_path}: {exc}")
        return {
            **state,
            "symbol_info": None,
            "lookup_outcome": LookupOutcome.ERROR.value,
            "needs_full_source": False,
            "has_full_docstring": False,
            "needs_llm_fallback": True,
            "token_cost": 0,
            "routing_reason": f"Exception during lookup: {exc}",
            "_error": str(exc),
        }

    status = data.get("status")
    usage_status = data.get("usage_status")  # "curated" | "not_curated" | None

    if status != "success":
        outcome = LookupOutcome.NOT_FOUND
    elif usage_status == "curated":
        outcome = LookupOutcome.CURATED
    else:
        outcome = LookupOutcome.NOT_CURATED

    # Evaluasi ketebalan docstring
    docstring_short = data.get("docstring_short") or ""
    docstring_full = data.get("docstring_full") or ""
    has_full_docstring = bool(docstring_full and len(docstring_full.split()) >= 15)
    
    # Docstring pendek (< 15 kata) tanpa docstring_full dianggap "tipis"
    docstring_is_thin = (len(docstring_short.split()) < 15) and not has_full_docstring

    needs_full_source = (outcome == LookupOutcome.NOT_CURATED) and docstring_is_thin
    needs_llm_fallback = outcome in (LookupOutcome.NOT_FOUND, LookupOutcome.ERROR)

    reason = f"Outcome={outcome.value}, thin_doc={docstring_is_thin}, full_doc={has_full_docstring}"

    return {
        **state,
        "symbol_info": data,
        "lookup_outcome": outcome.value,
        "needs_full_source": needs_full_source,
        "has_full_docstring": has_full_docstring,
        "needs_llm_fallback": needs_llm_fallback,
        "token_cost": data.get("token_cost", 0),
        "routing_reason": reason,
    }


# ---------------------------------------------------------------------------
# Node 2: full_source_fetch_node (Bounded Token Budget Fallback)
# ---------------------------------------------------------------------------

async def full_source_fetch_node(state: AgentState) -> AgentState:
    """
    Mengambil potongan kode sumber langsung dari disk ketika docstring tipis,
    dengan pembatasan ketat (bounded 40 baris / max 2000 karakter) agar token tidak boros.
    """
    symbol_info = state.get("symbol_info") or {}
    file_loc = symbol_info.get("file_location")
    
    if not file_loc or ":L" not in file_loc:
        return {
            **state,
            "needs_full_source": False,
            "source_snippet": None,
            "routing_reason": f"{state.get('routing_reason', '')} -> full_source_fetch (no file_location)",
        }

    try:
        file_path, line_str = file_loc.split(":L")
        line_no = int(line_str)

        with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
            lines = fp.readlines()

        start = max(0, line_no - 1)
        end = min(len(lines), line_no + 39)
        excerpt = "".join(lines[start:end])

        # Token guard: batasi maksimal 2000 karakter
        if len(excerpt) > 2000:
            excerpt = excerpt[:2000] + "\n# ... [TRUNCATED FOR TOKEN BUDGET] ..."

        estimated_tokens = len(excerpt) // 4
        updated_token_cost = state.get("token_cost", 0) + estimated_tokens

        return {
            **state,
            "needs_full_source": False,
            "source_snippet": excerpt,
            "source_lines_range": f"L{start + 1}-L{end}",
            "token_cost": updated_token_cost,
            "routing_reason": f"{state.get('routing_reason', '')} -> full_source_fetched ({end - start} lines)",
        }
    except Exception as e:
        logger.warning(f"full_source_fetch_node failed to read {file_loc}: {e}")
        return {
            **state,
            "needs_full_source": False,
            "source_snippet": f"# Failed to read source file: {e}",
            "routing_reason": f"{state.get('routing_reason', '')} -> full_source_error ({e})",
        }


# ---------------------------------------------------------------------------
# Node 3: llm_knowledge_fallback_node
# ---------------------------------------------------------------------------

async def llm_knowledge_fallback_node(state: AgentState) -> AgentState:
    """
    Menandai bahwa ground-truth lokal tidak ditemukan, menyiapkan instruksi
    kehati-hatian untuk LLM generator.
    """
    symbol_path = state.get("symbol_path", "")
    disclaimer = (
        f"[DISCLAIMER: NO LOCAL GROUND TRUTH FOUND]\n"
        f"Simbol '{symbol_path}' tidak ditemukan pada cache lokal atau indeks simbol.\n"
        f"Gunakan pengetahuan umum dengan validasi ketat dan sertakan defensive type checking."
    )
    return {
        **state,
        "needs_llm_fallback": True,
        "routing_reason": f"{state.get('routing_reason', '')} -> llm_knowledge_fallback",
        "composed_prompt": disclaimer,
    }


# ---------------------------------------------------------------------------
# Node 4: lookup_error_node
# ---------------------------------------------------------------------------

async def lookup_error_node(state: AgentState) -> AgentState:
    """
    Menangani error runtime / infrastruktur tanpa silent failure.
    """
    err_msg = state.get("_error", "Unknown error during symbol lookup")
    logger.error(f"lookup_error_node activated: {err_msg}")
    return {
        **state,
        "routing_reason": f"Routing halted due to error: {err_msg}",
        "composed_prompt": f"[SYSTEM ERROR] Symbol lookup failed: {err_msg}",
    }


# ---------------------------------------------------------------------------
# Node 5: generator_node (Prompt Composition & Execution Bridge)
# ---------------------------------------------------------------------------

async def generator_node(state: AgentState) -> AgentState:
    """
    Menyusun prompt akhir berdasar konteks (curated / docstring / source)
    dan mengembalikan prompt yang siap dikirim ke LLM.
    """
    outcome = state.get("lookup_outcome")
    symbol_info = state.get("symbol_info") or {}
    query_ctx = state.get("query_context") or "Generate standard compliant Python code."
    
    symbol_path = symbol_info.get("symbol_path", state.get("symbol_path", ""))
    sig = symbol_info.get("signature", "")
    doc_short = symbol_info.get("docstring_short", "")
    doc_full = symbol_info.get("docstring_full", "")
    patterns = symbol_info.get("usage_patterns", [])

    prompt_parts = [f"# TASK / CONTEXT: {query_ctx}"]

    if state.get("needs_llm_fallback"):
        prompt_parts.append(
            f"\n[DISCLAIMER: NO LOCAL GROUND TRUTH FOUND]\n"
            f"Simbol '{symbol_path}' tidak ditemukan pada cache lokal atau indeks simbol.\n"
            f"Gunakan pengetahuan umum dengan validasi ketat dan sertakan defensive type checking."
        )
    elif outcome == LookupOutcome.CURATED.value and patterns:
        prompt_parts.append(f"\n[VERIFIED API USAGE PATTERNS]")
        prompt_parts.append(f"Target: {symbol_path}")
        prompt_parts.append(f"Signature: {sig}")
        for idx, p in enumerate(patterns, 1):
            prompt_parts.append(f"Example {idx} ({p.get('context', '')}):\n```python\n{p.get('code', '')}\n```")
    
    elif state.get("source_snippet"):
        prompt_parts.append(f"\n[TARGET SOURCE CODE EXCERPT ({state.get('source_lines_range', '')})]")
        prompt_parts.append(f"Target: {symbol_path}")
        prompt_parts.append(f"Signature: {sig}")
        prompt_parts.append(f"Source:\n```python\n{state.get('source_snippet')}\n```")
        
    elif doc_full or doc_short:
        prompt_parts.append(f"\n[OFFICIAL API SIGNATURE & DOCSTRING]")
        prompt_parts.append(f"Target: {symbol_path}")
        prompt_parts.append(f"Signature: {sig}")
        prompt_parts.append(f"Docstring:\n{doc_full if doc_full else doc_short}")

    composed = "\n".join(prompt_parts)

    
    return {
        **state,
        "composed_prompt": composed,
        "routing_reason": f"{state.get('routing_reason', '')} -> generator_composed",
    }


# ---------------------------------------------------------------------------
# Conditional Edge Routing Function
# ---------------------------------------------------------------------------

def route_after_lookup(state: AgentState) -> str:
    """
    Dipanggil LangGraph sebagai conditional edge setelah symbol_lookup_node.
    Return value = nama node tujuan berikutnya.
    """
    outcome = state.get("lookup_outcome")

    if outcome == LookupOutcome.CURATED.value:
        # Ada snippet terverifikasi → langsung ke generator
        return "generator_node"

    if outcome == LookupOutcome.NOT_CURATED.value:
        if state.get("needs_full_source"):
            # Docstring tipis & belum curated → fetch source code asli (bounded token budget)
            return "full_source_fetch_node"
        # Docstring cukup informatif (atau ada docstring_full) → langsung ke generator
        return "generator_node"

    if outcome == LookupOutcome.NOT_FOUND.value:
        # Simbol tidak ditemukan di cache → serahkan ke LLM dengan flag eksplisit no ground truth
        return "llm_knowledge_fallback_node"

    # ERROR — Redis/parse gagal → arahkan ke node alert/retry terisolasi
    return "lookup_error_node"


# ---------------------------------------------------------------------------
# LangGraph StateGraph Factory
# ---------------------------------------------------------------------------

def build_symbol_orchestrator_graph():
    """
    Membangun dan mengompilasi StateGraph LangGraph untuk orkestrasi simbol & generator.
    """
    from langgraph.graph import StateGraph, END

    workflow = StateGraph(AgentState)

    # Tambahkan semua node
    workflow.add_node("symbol_lookup_node", symbol_lookup_node)
    workflow.add_node("full_source_fetch_node", full_source_fetch_node)
    workflow.add_node("llm_knowledge_fallback_node", llm_knowledge_fallback_node)
    workflow.add_node("lookup_error_node", lookup_error_node)
    workflow.add_node("generator_node", generator_node)

    # Entry point
    workflow.set_entry_point("symbol_lookup_node")

    # Conditional edges setelah lookup
    workflow.add_conditional_edges(
        "symbol_lookup_node",
        route_after_lookup,
        {
            "generator_node": "generator_node",
            "full_source_fetch_node": "full_source_fetch_node",
            "llm_knowledge_fallback_node": "llm_knowledge_fallback_node",
            "lookup_error_node": "lookup_error_node",
        },
    )

    # Flow konvergen ke generator_node
    workflow.add_edge("full_source_fetch_node", "generator_node")
    workflow.add_edge("llm_knowledge_fallback_node", "generator_node")
    
    # Terminal ends
    workflow.add_edge("generator_node", END)
    workflow.add_edge("lookup_error_node", END)

    return workflow.compile()

