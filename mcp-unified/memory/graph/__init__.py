"""
Graph Memory & Hybrid GraphRAG Engine for MCP Unified (TASK-122).
Provides relational knowledge graph traversal, entity-relation triple extraction,
and multi-hop reasoning over PostgreSQL and SQLite.
"""

from importlib import import_module

# Lazy (PEP 562) — hindari circular import saat execution/discovery memuat submodul
# graf sebagai paket top-level `graph.*` (mis. `graph.store_sqlite`) sehingga
# `from .schema import ...` memicu inisialisasi ulang paket induk `graph`.
_LAZY_ATTRS = {
    "GraphNode": "schema",
    "GraphEdge": "schema",
    "Triple": "schema",
    "GraphPath": "schema",
    "Subgraph": "schema",
    "SQLiteGraphStore": "store_sqlite",
    "SemanticTripleExtractor": "extractor",
    "GraphTraverser": "traverser",
    "HybridGraphSearcher": "hybrid_search",
}

__all__ = list(_LAZY_ATTRS)


def __getattr__(name):
    module_name = _LAZY_ATTRS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{module_name}"), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
