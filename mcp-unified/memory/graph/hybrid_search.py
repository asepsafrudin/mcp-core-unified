"""
Hybrid GraphRAG Searcher (TASK-122).
Fuses Entity Similarity Search + Graph Neighbor Expansion to synthesize rich relational context.
"""

from typing import List, Dict, Any, Optional
from .schema import GraphNode, Subgraph, HybridSearchResult
from .store_sqlite import SQLiteGraphStore
from .traverser import GraphTraverser

class HybridGraphSearcher:
    def __init__(self, store: Optional[SQLiteGraphStore] = None):
        self.store = store or SQLiteGraphStore()
        self.traverser = GraphTraverser(self.store)

    def search(
        self, query: str, namespace: Optional[str] = None, top_k: int = 3, expand_depth: int = 1
    ) -> List[HybridSearchResult]:
        """
        1. Find top candidate nodes via keyword / semantic match.
        2. Expand each candidate node by N-hops to capture structural context.
        3. Return ranked HybridSearchResults.
        """
        # Extract keywords from query
        words = [w.strip().lower() for w in query.split() if len(w.strip()) > 2]
        matched_nodes_map: Dict[str, GraphNode] = {}
        
        for word in words:
            nodes = self.store.search_nodes_by_keyword(word, namespace=namespace, limit=5)
            for n in nodes:
                matched_nodes_map[n.id] = n

        # Fallback search with full query
        if not matched_nodes_map:
            nodes = self.store.search_nodes_by_keyword(query, namespace=namespace, limit=top_k)
            for n in nodes:
                matched_nodes_map[n.id] = n

        results: List[HybridSearchResult] = []
        for node in list(matched_nodes_map.values())[:top_k]:
            subgraph = self.traverser.get_subgraph_context(node.id, depth=expand_depth, namespace=namespace)
            neighbors = [n for n in subgraph.nodes if n.id != node.id]
            explanation = self.traverser.format_subgraph_markdown(subgraph)
            
            results.append(HybridSearchResult(
                node=node,
                similarity_score=1.0,
                neighbors=neighbors,
                connecting_edges=subgraph.edges,
                explanation=explanation
            ))

        return results
