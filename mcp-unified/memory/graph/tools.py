"""
MCP Tools for Graph Memory & Hybrid GraphRAG (TASK-122).
Namespace: graph
Registers tools into execution.registry.
"""

from typing import Dict, Any, List, Optional
from execution.registry import registry
from .schema import Triple
from .store_sqlite import SQLiteGraphStore
from .extractor import SemanticTripleExtractor
from .traverser import GraphTraverser
from .hybrid_search import HybridGraphSearcher

_store = SQLiteGraphStore()
_extractor = SemanticTripleExtractor()
_traverser = GraphTraverser(_store)
_searcher = HybridGraphSearcher(_store)

def register_tools(server=None) -> None:
    """Register Graph Memory tools to MCP registry."""

    @registry.register(name="graph_add_triple")
    async def add_triple(
        source_id: str,
        source_name: str,
        relation: str,
        target_id: str,
        target_name: str,
        source_type: str = "concept",
        target_type: str = "concept",
        namespace: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Menambahkan relasi (Triple: Subjek -> Predikat -> Objek) baru ke Knowledge Graph.

        Args:
            source_id   : ID unik entitas asal (misal: 'surat:038_puu', 'pegawai:19830306')
            source_name : Nama lengkap entitas asal
            relation    : Nama relasi (misal: 'ditandatangani_oleh', 'merujuk_ke', 'menjabat_sebagai')
            target_id   : ID unik entitas tujuan
            target_name : Nama lengkap entitas tujuan
            source_type : Tipe entitas asal (surat|pegawai|instansi|regulasi|lokasi|topik)
            target_type : Tipe entitas tujuan
            namespace   : Namespace isolasi (default: 'default')
            metadata    : Konteks tambahan (dict)

        Returns:
            {"status": "success", "triple": str}
        """
        triple = Triple(
            source_id=source_id,
            source_name=source_name,
            source_type=source_type,
            relation=relation,
            target_id=target_id,
            target_name=target_name,
            target_type=target_type,
            metadata=metadata or {}
        )
        _store.ingest_triple(triple, namespace=namespace)
        return {
            "status": "success",
            "message": f"Triple ditambahkan: ({source_name}) -[{relation}]-> ({target_name})",
            "namespace": namespace
        }

    @registry.register(name="graph_extract_and_ingest")
    async def extract_and_ingest(
        text: str,
        namespace: str = "default",
        doc_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mengekstrak entitas dan relasi (triples) secara otomatis dari teks/dokumen via LLM,
        kemudian langsung menyimpannya ke Knowledge Graph.

        Args:
            text     : Teks dokumen, hasil OCR, atau transkrip percakapan
            namespace: Namespace target penyimpanan
            doc_id   : ID dokumen sumber (opsional)

        Returns:
            {"status": "success", "triples_count": int, "triples": list}
        """
        triples = _extractor.extract_triples_from_text(text)
        ingested = []
        for t in triples:
            if doc_id:
                t.metadata["source_doc_id"] = doc_id
            _store.ingest_triple(t, namespace=namespace)
            ingested.append({
                "source": t.source_name,
                "relation": t.relation,
                "target": t.target_name
            })
        return {
            "status": "success",
            "triples_count": len(ingested),
            "triples": ingested,
            "namespace": namespace
        }

    @registry.register(name="graph_get_neighbors")
    async def get_neighbors(
        node_id: str,
        depth: int = 1,
        namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mengambil entitas tetangga yang terhubung dengan node tertentu hingga N-hop.

        Args:
            node_id  : ID node pusat (misal: 'surat:000.2.2.4_038_puu', 'pegawai:lady_diana')
            depth    : Kedalaman hop penelusuran graf (1 - 3, default: 1)
            namespace: Filter namespace (opsional)

        Returns:
            {"status": "success", "subgraph_markdown": str, "nodes": list, "edges": list}
        """
        subgraph = _traverser.get_subgraph_context(node_id, depth=depth, namespace=namespace)
        md = _traverser.format_subgraph_markdown(subgraph)
        return {
            "status": "success",
            "root_id": node_id,
            "depth": depth,
            "nodes_count": len(subgraph.nodes),
            "edges_count": len(subgraph.edges),
            "subgraph_markdown": md,
            "nodes": [n.model_dump() if hasattr(n, "model_dump") else n.dict() for n in subgraph.nodes],
            "edges": [e.model_dump() if hasattr(e, "model_dump") else e.dict() for e in subgraph.edges]
        }

    @registry.register(name="graph_find_relation")
    async def find_relation(
        source_id: str,
        target_id: str,
        max_hops: int = 3
    ) -> Dict[str, Any]:
        """
        Menemukan rantai relasi terpendek (shortest path) antara dua entitas dalam Knowledge Graph.

        Args:
            source_id: ID entitas awal
            target_id: ID entitas tujuan
            max_hops : Batas maksimal langkah penelusuran (default: 3)

        Returns:
            {"found": bool, "path": str, "explanation": str}
        """
        return _traverser.find_relation_path(source_id, target_id, max_hops=max_hops)

    @registry.register(name="graph_hybrid_search")
    async def hybrid_search(
        query: str,
        namespace: Optional[str] = None,
        top_k: int = 3,
        expand_depth: int = 1
    ) -> Dict[str, Any]:
        """
        Melakukan pencarian Hybrid GraphRAG (pencarian entitas + ekspansi relasi tetangga)
        untuk menghasilkan jawaban multi-relasi tanpa halusinasi.

        Args:
            query       : Kata kunci atau pertanyaan pencarian
            namespace   : Filter namespace (opsional)
            top_k       : Jumlah entitas teratas (default: 3)
            expand_depth: Kedalaman ekspansi graf tetangga (default: 1)

        Returns:
            {"status": "success", "results": list}
        """
        results = _searcher.search(query, namespace=namespace, top_k=top_k, expand_depth=expand_depth)
        return {
            "status": "success",
            "query": query,
            "results_count": len(results),
            "results": [r.model_dump() if hasattr(r, "model_dump") else r.dict() for r in results]
        }
