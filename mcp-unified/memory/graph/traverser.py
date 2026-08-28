"""
Graph Traverser & Multi-Hop Reasoning Engine (TASK-122).
Handles N-hop subgraph expansion, relation path tracing, and context synthesis.
"""

from typing import List, Dict, Any, Optional
from .schema import GraphNode, GraphEdge, Subgraph
from .store_sqlite import SQLiteGraphStore

class GraphTraverser:
    def __init__(self, store: Optional[SQLiteGraphStore] = None):
        self.store = store or SQLiteGraphStore()

    def get_subgraph_context(
        self, node_id: str, depth: int = 2, namespace: Optional[str] = None
    ) -> Subgraph:
        """
        Fetch N-hop subgraph around a central node.
        """
        return self.store.get_neighbors(node_id=node_id, depth=depth, namespace=namespace)

    def find_relation_path(
        self, source_id: str, target_id: str, max_hops: int = 3
    ) -> Dict[str, Any]:
        """
        Find shortest relational chain connecting two entities.
        """
        path_str = self.store.find_path(source_id, target_id, max_hops=max_hops)
        if not path_str:
            return {
                "found": False,
                "source": source_id,
                "target": target_id,
                "message": f"Tidak ditemukan jalur relasi antara '{source_id}' dan '{target_id}' dalam {max_hops} hop."
            }
            
        return {
            "found": True,
            "source": source_id,
            "target": target_id,
            "path": path_str,
            "explanation": f"Jalur relasi: {path_str}"
        }

    def format_subgraph_markdown(self, subgraph: Subgraph) -> str:
        """
        Render a subgraph into human/LLM-readable markdown graph format.
        """
        if not subgraph.nodes:
            return "Graph kosong (tidak ada entitas terkait ditemukan)."

        lines = [f"### 🕸️ Graph Knowledge Subgraph (Root: `{subgraph.root_id}` | Depth: {subgraph.depth})"]
        lines.append(f"**Total Entitas ({len(subgraph.nodes)}):**")
        for n in subgraph.nodes:
            lines.append(f"- **[{n.entity_type.upper()}]** `{n.id}` ({n.name})")

        if subgraph.edges:
            lines.append(f"\n**Hubungan Relasi ({len(subgraph.edges)}):**")
            for e in subgraph.edges:
                lines.append(f"- `{e.source_id}` ───▶ *({e.relation})* ───▶ `{e.target_id}`")

        return "\n".join(lines)
