"""
MCP Tools for Code Symbol Knowledge Graph & AST Intelligence (TASK-123).
Exposes symbol_search, symbol_get_definition, and symbol_index_library to OpenHands & IDE Agents.
"""

import json
import logging
from typing import Dict, Any, Optional, List

from memory.graph.store_sqlite import SQLiteGraphStore
from memory.graph.traverser import GraphTraverser
from memory.graph.hybrid_search import HybridGraphSearcher
from memory.symbol_indexer.indexer import LibrarySymbolIndexer
from memory.symbol_indexer.schema import (
    SymbolIndexItem,
    UsagePatternItem,
    SnippetItem,
    LibraryMetaIndex,
)


logger = logging.getLogger(__name__)

# Shared instances
_graph_store = SQLiteGraphStore()
_traverser = GraphTraverser(_graph_store)
_searcher = HybridGraphSearcher(_graph_store)
_indexer = LibrarySymbolIndexer(_graph_store)


async def symbol_search(query: str, library: str = "pydantic", limit: int = 5) -> str:
    """
    Search for Python library code symbols (classes, methods, decorators, configs).
    Returns accurate signatures, docstrings, and connected components without LLM hallucinations.
    """
    try:
        namespace = "code_symbols"
        results = _searcher.search(query, namespace=namespace, top_k=limit, expand_depth=1)
        
        matches = []
        for r in results:
            neighbors_info = [
                {"id": n.id, "name": n.name, "type": n.entity_type}
                for n in r.neighbors
            ]
            matches.append({
                "symbol_id": r.node.id,
                "name": r.node.name,
                "type": r.node.entity_type,
                "metadata": r.node.metadata,
                "connected_symbols": neighbors_info
            })

        return json.dumps({
            "status": "success",
            "query": query,
            "library": library,
            "total_matches": len(matches),
            "matches": matches
        }, indent=2)
    except Exception as e:
        logger.error(f"symbol_search failed: {e}")
        return json.dumps({"status": "error", "error": str(e)})


async def symbol_get_definition(symbol_name: str, library: str = "pydantic") -> str:
    """
    Get full deterministic definition and related symbol graph for a specific class or method.
    Provides exact signature, parameter requirements, return types, and decorators.
    """
    try:
        namespace = "code_symbols"
        # Search for exact node by symbol_name or prefix
        target_id = None
        for prefix in (f"class:{library}.{symbol_name}", f"method:{library}.{symbol_name}", f"function:{library}.{symbol_name}", f"decorator:{library}.{symbol_name}"):
            node = _graph_store.get_node(prefix, namespace=namespace)
            if node:
                target_id = node.id
                break

        if not target_id:
            # Fallback: search by name
            search_res = _searcher.search(symbol_name, namespace=namespace, top_k=1, expand_depth=2)
            if search_res:
                target_id = search_res[0].node.id

        if not target_id:
            return json.dumps({
                "status": "not_found",
                "message": f"Symbol '{symbol_name}' not found in library '{library}'. Try running symbol_index_library('{library}') first."
            })

        subgraph = _traverser.get_subgraph_context(target_id, depth=2, namespace=namespace)
        
        root_node = next((n for n in subgraph.nodes if n.id == target_id), None)
        relations = [
            {"source": e.source_id, "relation": e.relation, "target": e.target_id}
            for e in subgraph.edges
        ]

        return json.dumps({
            "status": "success",
            "symbol": root_node.model_dump() if root_node else {},
            "related_nodes": [n.model_dump() for n in subgraph.nodes if n.id != target_id],
            "relations": relations
        }, indent=2, default=str)
    except Exception as e:
        logger.error(f"symbol_get_definition failed: {e}")
        return json.dumps({"status": "error", "error": str(e)})


async def symbol_index_library(library_name: str = "pydantic") -> str:
    """
    Index or re-index a Python library into the Code Knowledge Graph (e.g. pydantic, fastmcp, langgraph, httpx, psycopg).
    """
    try:
        res = _indexer.index_library(library_name)
        return json.dumps(res, indent=2)
    except Exception as e:
        logger.error(f"symbol_index_library failed: {e}")
        return json.dumps({"status": "error", "error": str(e)})


async def get_symbol_info(
    symbol_path: str,
    detail_level: str = "summary",
    library_version: Optional[str] = None
) -> str:
    """
    Ambil informasi symbol kode Python (signature, brief docstring, usage pattern, source)
    dari 3-Layer Redis Cache secara sangat hemat token (TASK-125).

    Args:
        symbol_path: Path symbol lengkap (misal: 'pydantic.BaseModel.model_validate' atau 'fastapi.FastAPI')
        detail_level: Tingkat detail: 'summary' (~40 token) | 'usage' (~120 token) | 'full' (source code)
        library_version: Versi spesifik (opsional, otomatis deteksi jika kosong)
    """
    import importlib.metadata
    from memory.symbol_indexer.redis_cache import symbol_redis_cache
    from memory.working import working_memory

    try:
        parts = symbol_path.strip().split(".")
        lib_name = parts[0]

        # 1. Resolve version
        ver = library_version
        if not ver:
            try:
                ver = importlib.metadata.version(lib_name)
            except Exception:
                ver = "1.0.0"

        # 2. Fetch Layer 1 Symbol
        symbol_item = await symbol_redis_cache.get_symbol(lib_name, ver, symbol_path)
        
        # Fallback if not found: try dynamic runtime inspection and cache it immediately
        if not symbol_item:
            try:
                import importlib
                import inspect
                # Try finding target object by splitting module and attribute
                obj = None
                curr_mod = None
                for i in range(len(parts), 0, -1):
                    mod_attempt = ".".join(parts[:i])
                    try:
                        curr_mod = importlib.import_module(mod_attempt)
                        # Traverse attributes
                        obj = curr_mod
                        for attr in parts[i:]:
                            obj = getattr(obj, attr)
                        break
                    except Exception:
                        continue

                if obj is not None:
                    from memory.symbol_indexer.extractor import SymbolExtractor
                    raw_doc = inspect.getdoc(obj) or ""
                    short_doc = SymbolExtractor._clean_short_doc(raw_doc)
                    kind = "class" if inspect.isclass(obj) else ("function" if inspect.isfunction(obj) else "method")
                    try:
                        sig = f"{parts[-1]}{inspect.signature(obj)}"
                    except Exception:
                        sig = f"{parts[-1]}(...)" if callable(obj) else str(obj)[:50]
                    try:
                        file_loc = f"{inspect.getfile(obj)}:L{inspect.getsourcelines(obj)[1]}"
                    except Exception:
                        file_loc = None

                    symbol_item = SymbolIndexItem(
                        symbol_path=symbol_path,
                        kind=kind,
                        signature=sig,
                        docstring_short=short_doc,
                        docstring_full=raw_doc[:2000] if raw_doc else None,
                        file_location=file_loc,
                        returns="Self" if "validate" in parts[-1] else None,
                        raises=[],
                        tags=[kind, "live_inspect"],
                        token_cost_cached=SymbolExtractor._estimate_token_cost(short_doc + sig)
                    )

                    # Cache it for future instant hits
                    await symbol_redis_cache.set_symbol(lib_name, ver, symbol_item)
            except Exception as ex:
                logger.warning(f"Dynamic symbol inspection fallback failed: {ex}")

        if not symbol_item:
            return json.dumps({
                "status": "not_found",
                "message": f"Symbol '{symbol_path}' tidak ditemukan di cache v{ver}. Coba periksa penulisan symbol_path."
            }, indent=2)


        # Base Summary Response (Layer 1)
        response_data: Dict[str, Any] = {
            "status": "success",
            "symbol_path": symbol_item.symbol_path,
            "kind": symbol_item.kind,
            "signature": symbol_item.signature,
            "docstring_short": symbol_item.docstring_short,
            "docstring_full": symbol_item.docstring_full,
            "file_location": symbol_item.file_location,
            "returns": symbol_item.returns,
            "raises": symbol_item.raises,
            "token_cost": symbol_item.token_cost_cached
        }


        # Track query popularity for curation prioritization
        if working_memory.client:
            try:
                await working_memory.client.zincrby(
                    working_memory._namespaced_key("metrics:symbol_query_hits"), 1, symbol_item.symbol_path
                )
            except Exception:
                pass

        # Usage Patterns & Snippets (Layer 2)
        if detail_level in ("usage", "full"):
            usage = (
                await symbol_redis_cache.get_usage(lib_name, ver, symbol_path)
                or await symbol_redis_cache.get_usage(lib_name, ver, symbol_item.symbol_path)
            )
            if usage and usage.common_patterns:

                patterns_list = []
                for p in usage.common_patterns:
                    snip_id = p.snippet_ref.split(":")[-1]
                    snip_data = await symbol_redis_cache.get_snippet(lib_name, ver, snip_id)
                    patterns_list.append({
                        "context": p.context,
                        "code": snip_data.code if snip_data else None,
                        "rank": p.frequency_rank
                    })
                response_data["usage_status"] = "curated"
                response_data["usage_patterns"] = patterns_list
                response_data["related_symbols"] = usage.related_symbols
            else:
                response_data["usage_status"] = "not_curated"
                response_data["usage_patterns"] = []
                response_data["usage_note"] = (
                    "Belum ada contoh pola penggunaan (curated pattern) khusus terdaftar untuk simbol ini. "
                    "Gunakan signature & parameter di atas, atau gunakan detail_level='full' untuk membaca potongan source code asli."
                )

        # Full Source Code (Layer 3 - Lazy Load)
        if detail_level == "full" and symbol_item.file_location:
            try:
                file_path, line_str = symbol_item.file_location.split(":L")
                line_no = int(line_str)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                    lines = fp.readlines()
                # Read 40 lines around target
                start = max(0, line_no - 1)
                end = min(len(lines), line_no + 39)
                response_data["source_code"] = "".join(lines[start:end])
            except Exception as e:
                response_data["source_code_error"] = str(e)


        return json.dumps(response_data, indent=2)
    except Exception as e:
        logger.error(f"get_symbol_info failed: {e}")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


def register_tools():
    """Register symbol indexer tools into execution.registry."""
    from execution.registry import registry

    tools_to_register = [
        (get_symbol_info, "get_symbol_info", "Ambil struktur symbol (signature, doc, usage) library Python secara hemat token dari cache Serena/Redis (TASK-125).", "code"),
        (symbol_search, "symbol_search", "Cari simbol kode Python (kelas, method, decorator) di Code Knowledge Graph.", "code"),
        (symbol_get_definition, "symbol_get_definition", "Ambil definisi AST, signature, dan relasi simbol library Python secara presisi.", "code"),
        (symbol_index_library, "symbol_index_library", "Indeks struktur simbol library Python ke Code Knowledge Graph.", "code"),
    ]

    for func, name, desc, cat in tools_to_register:
        try:
            registry.register(func, name=name, description_short=desc, category=cat)
            logger.info(f"Registered symbol indexer tool: {name}")
        except Exception as e:
            logger.warning(f"Failed to register symbol tool {name}: {e}")


