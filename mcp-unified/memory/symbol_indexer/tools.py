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


def register_tools():
    """Register symbol indexer tools into execution.registry."""
    from execution.registry import registry

    tools_to_register = [
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

