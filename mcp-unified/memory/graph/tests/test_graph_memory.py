"""
Unit & Integration Test Suite for Graph Memory & Hybrid GraphRAG (TASK-122).
"""

import pytest
import tempfile
import json
from pathlib import Path

from memory.graph.schema import GraphNode, GraphEdge, Triple
from memory.graph.store_sqlite import SQLiteGraphStore
from memory.graph.extractor import SemanticTripleExtractor
from memory.graph.traverser import GraphTraverser
from memory.graph.hybrid_search import HybridGraphSearcher
from memory.graph.tools import register_tools
from execution.registry import registry

@pytest.fixture
def temp_store(tmp_path):
    db_file = tmp_path / "test_graph.db"
    return SQLiteGraphStore(db_file)

def test_node_and_edge_crud(temp_store):
    # 1. Upsert nodes
    n1 = GraphNode(id="surat:038_puu", namespace="korespondensi", entity_type="surat", name="Nota Dinas 038")
    n2 = GraphNode(id="pegawai:lady_diana", namespace="korespondensi", entity_type="pegawai", name="Lady Diana Handayani")
    n3 = GraphNode(id="lokasi:banten", namespace="korespondensi", entity_type="lokasi", name="Provinsi Banten")
    
    temp_store.upsert_node(n1)
    temp_store.upsert_node(n2)
    temp_store.upsert_node(n3)
    
    # 2. Add edges
    e1 = GraphEdge(namespace="korespondensi", source_id="surat:038_puu", target_id="pegawai:lady_diana", relation="ditandatangani_oleh")
    e2 = GraphEdge(namespace="korespondensi", source_id="surat:038_puu", target_id="lokasi:banten", relation="tujuan_tugas")
    
    temp_store.add_edge(e1)
    temp_store.add_edge(e2)
    
    # Verify node retrieval
    fetched = temp_store.get_node("surat:038_puu")
    assert fetched is not None
    assert fetched.name == "Nota Dinas 038"
    assert fetched.entity_type == "surat"

def test_triple_ingestion_and_neighbors(temp_store):
    t1 = Triple(
        source_id="surat:038_puu",
        source_name="Nota Dinas 038",
        source_type="surat",
        relation="ditandatangani_oleh",
        target_id="pegawai:lady_diana",
        target_name="Lady Diana",
        target_type="pegawai"
    )
    t2 = Triple(
        source_id="pegawai:lady_diana",
        source_name="Lady Diana",
        source_type="pegawai",
        relation="menjabat_sebagai",
        target_id="jabatan:analis_hukum",
        target_name="Analis Hukum Ahli Madya",
        target_type="jabatan"
    )
    
    temp_store.ingest_triple(t1, namespace="test")
    temp_store.ingest_triple(t2, namespace="test")
    
    # 1-hop neighbors
    subgraph_1hop = temp_store.get_neighbors("surat:038_puu", depth=1, namespace="test")
    assert len(subgraph_1hop.nodes) == 2
    assert any(n.id == "pegawai:lady_diana" for n in subgraph_1hop.nodes)
    
    # 2-hop neighbors (should include jabatan)
    subgraph_2hop = temp_store.get_neighbors("surat:038_puu", depth=2, namespace="test")
    assert len(subgraph_2hop.nodes) == 3
    assert any(n.id == "jabatan:analis_hukum" for n in subgraph_2hop.nodes)

def test_path_finding(temp_store):
    t1 = Triple(source_id="A", source_name="Node A", relation="rel_ab", target_id="B", target_name="Node B")
    t2 = Triple(source_id="B", source_name="Node B", relation="rel_bc", target_id="C", target_name="Node C")
    temp_store.ingest_triple(t1)
    temp_store.ingest_triple(t2)
    
    path = temp_store.find_path("A", "C", max_hops=3)
    assert path is not None
    assert "A" in path and "rel_ab" in path and "B" in path and "rel_bc" in path and "C" in path

def test_extractor_heuristics():
    extractor = SemanticTripleExtractor()
    sample_text = """
    KEMENTERIAN DALAM NEGERI
    Nomor : 000.2.2.4/038/PUU
    Tanggal : 3 Maret 2026
    Hal : Surat Tugas Monitoring
    
    Analis Hukum Ahli Madya
    Lady Diana Handayani, S.H., M.H.
    """
    triples = extractor._heuristic_extractor(sample_text)
    assert len(triples) >= 1
    assert any("000.2.2.4" in t.source_id for t in triples)

def test_hybrid_search(temp_store):
    t1 = Triple(
        source_id="surat:038_puu",
        source_name="Nota Dinas Pengawasan",
        source_type="surat",
        relation="ditandatangani_oleh",
        target_id="pegawai:lady_diana",
        target_name="Lady Diana Handayani",
        target_type="pegawai"
    )
    temp_store.ingest_triple(t1)
    
    searcher = HybridGraphSearcher(temp_store)
    results = searcher.search("Pengawasan", top_k=3, expand_depth=1)
    assert len(results) >= 1
    assert results[0].node.id == "surat:038_puu"
    assert len(results[0].neighbors) >= 1
    assert results[0].neighbors[0].id == "pegawai:lady_diana"

def test_mcp_tools_registration():
    register_tools()
    tool_names = [t["name"] for t in registry.list_tools()]
    assert "graph_add_triple" in tool_names
    assert "graph_extract_and_ingest" in tool_names
    assert "graph_get_neighbors" in tool_names
    assert "graph_find_relation" in tool_names
    assert "graph_hybrid_search" in tool_names
