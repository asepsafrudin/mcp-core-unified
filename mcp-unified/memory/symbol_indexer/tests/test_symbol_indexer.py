"""
Unit Tests for Serena Symbol Indexer & Code Knowledge Graph (TASK-123).
Tests AST extraction, Pydantic v2 indexing, and deterministic symbol retrieval tools.
"""

import sys
import os
import json
import pytest
from pathlib import Path

# Add project root and core/mcp-unified to path
mcp_unified_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(mcp_unified_root))

from memory.graph.store_sqlite import SQLiteGraphStore
from memory.symbol_indexer.extractor import SymbolExtractor
from memory.symbol_indexer.indexer import LibrarySymbolIndexer
from memory.symbol_indexer.schema import SymbolType, SymbolRelation
from memory.symbol_indexer.tools import symbol_search, symbol_get_definition, symbol_index_library


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_symbol_graph.db"
    store = SQLiteGraphStore(db_path=str(db_file))
    return store


def test_ast_source_code_extraction():
    """Test AST static parsing from Python source code."""
    sample_code = '''
class UserProfile(BaseModel):
    """User profile entity with authentication metadata."""
    
    def get_display_name(self, prefix: str = "User") -> str:
        """Return formatted display name."""
        return f"{prefix}_{self.username}"

def create_user(username: str, email: str) -> UserProfile:
    """Factory function for user creation."""
    pass
'''
    extractor = SymbolExtractor(library_name="custom_app", namespace="test_symbols")
    triples = extractor.extract_from_source_code(sample_code, module_name="auth.models")
    
    assert len(triples) >= 3
    class_triple = next((t for t in triples if t.target_name == "UserProfile"), None)
    assert class_triple is not None
    assert class_triple.target_type == SymbolType.CLASS.value
    assert "User profile entity" in class_triple.metadata.get("docstring", "")

    method_triple = next((t for t in triples if t.target_name == "get_display_name"), None)
    assert method_triple is not None
    assert method_triple.relation == SymbolRelation.HAS_METHOD.value


def test_pydantic_v2_indexing(temp_db):
    """Test indexing of Pydantic v2 library into SQLite graph memory."""
    indexer = LibrarySymbolIndexer(store=temp_db, namespace="test_code_symbols")
    res = indexer.index_pydantic_v2()
    
    assert res["status"] == "success"
    assert res["triples_ingested"] >= 8

    # Verify BaseModel node exists
    base_model_node = temp_db.get_node("class:pydantic.BaseModel", namespace="test_code_symbols")
    assert base_model_node is not None
    assert base_model_node.name == "BaseModel"

    # Verify model_dump method exists and is linked
    neighbors = temp_db.get_neighbors("class:pydantic.BaseModel", namespace="test_code_symbols")
    neighbor_names = [n.name for n in neighbors.nodes]
    assert "model_dump" in neighbor_names
    assert "ConfigDict" in neighbor_names


@pytest.mark.asyncio
async def test_symbol_search_tool():
    """Test symbol_search MCP tool on indexed Pydantic symbols."""
    # Ensure indexing is executed
    await symbol_index_library("pydantic")
    
    # Search for model_dump
    search_json = await symbol_search("model_dump", library="pydantic")
    data = json.loads(search_json)
    
    assert data["status"] == "success"
    assert data["total_matches"] > 0
    match_names = [m["name"] for m in data["matches"]]
    assert any("model_dump" in name for name in match_names)


@pytest.mark.asyncio
async def test_symbol_get_definition_tool():
    """Test symbol_get_definition MCP tool returning exact AST signature and relations."""
    # Ensure indexing is executed
    await symbol_index_library("pydantic")
    
    def_json = await symbol_get_definition("BaseModel", library="pydantic")
    data = json.loads(def_json)
    
    assert data["status"] == "success"
    assert data["symbol"]["name"] == "BaseModel"
    assert len(data["related_nodes"]) > 0
    assert len(data["relations"]) > 0

    # Verify signature contains Pydantic v2 method
    related_names = [n["name"] for n in data["related_nodes"]]
    assert "model_dump" in related_names
    assert "ConfigDict" in related_names
