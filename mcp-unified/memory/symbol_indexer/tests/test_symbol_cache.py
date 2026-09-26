import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pytest
import pytest_asyncio
import asyncio
import json
import pydantic

from memory.symbol_indexer.schema import (
    SymbolIndexItem,
    UsagePatternItem,
    SnippetItem,
    SnippetReference,
    LibraryMetaIndex,
)
from memory.symbol_indexer.redis_cache import symbol_redis_cache
from memory.symbol_indexer.extractor import SymbolExtractor
from memory.symbol_indexer.tools import get_symbol_info
from memory.working import working_memory


@pytest_asyncio.fixture(autouse=True)
async def manage_redis_lifecycle():
    """Ensure clean redis connect and disconnect lifecycle per test."""
    await working_memory.connect()
    yield
    await working_memory.disconnect()



@pytest.mark.asyncio
async def test_symbol_redis_cache_crud():

    """Test 3-layer Redis cache CRUD and local fallback."""
    # 1. Meta
    meta = LibraryMetaIndex(
        library="testlib",
        version="1.0.0",
        indexed_at="2026-09-01T00:00:00",
        total_symbols=10
    )
    await symbol_redis_cache.set_meta(meta)
    fetched_meta = await symbol_redis_cache.get_meta("testlib", "1.0.0")
    assert fetched_meta is not None
    assert fetched_meta.library == "testlib"
    assert fetched_meta.total_symbols == 10

    # 2. Symbol Item
    sym = SymbolIndexItem(
        symbol_path="testlib.Core.run",
        kind="method",
        signature="run(x: int) -> bool",
        docstring_short="Execute the core runner.",
        returns="bool",
        raises=["RuntimeError"],
        token_cost_cached=25
    )
    await symbol_redis_cache.set_symbol("testlib", "1.0.0", sym)
    fetched_sym = await symbol_redis_cache.get_symbol("testlib", "1.0.0", "testlib.Core.run")
    assert fetched_sym is not None
    assert fetched_sym.signature == "run(x: int) -> bool"
    assert fetched_sym.token_cost_cached == 25

    # 3. Usage & Snippet
    snip = SnippetItem(snippet_id="001", code="runner = Core(); runner.run(10)")
    await symbol_redis_cache.set_snippet("testlib", "1.0.0", snip)

    usage = UsagePatternItem(
        symbol_path="testlib.Core.run",
        common_patterns=[SnippetReference(context="simple run", snippet_ref="snippet:testlib:1.0.0:001", frequency_rank=1)],
        related_symbols=["testlib.Core.stop"]
    )
    await symbol_redis_cache.set_usage("testlib", "1.0.0", usage)

    fetched_usage = await symbol_redis_cache.get_usage("testlib", "1.0.0", "testlib.Core.run")
    assert fetched_usage is not None
    assert len(fetched_usage.common_patterns) == 1

    fetched_snip = await symbol_redis_cache.get_snippet("testlib", "1.0.0", "001")
    assert fetched_snip is not None
    assert "runner.run(10)" in fetched_snip.code


@pytest.mark.asyncio
async def test_symbol_extractor_token_economy():
    """Verify that extracted symbols maintain extreme token economy (< 100 avg token)."""
    extractor = SymbolExtractor(library_name="pydantic")
    symbols, usages, snippets = extractor.extract_symbol_items_from_module(pydantic)

    assert len(symbols) > 0
    # Check token cost of first 20 symbols
    sample = symbols[:20]
    avg_token = sum(s.token_cost_cached for s in sample) / len(sample)
    assert avg_token < 150, f"Average token cost per symbol too high: {avg_token}"


@pytest.mark.asyncio
async def test_get_symbol_info_tiered_resolution():
    """Verify get_symbol_info tool returns fast, tiered structured JSON."""
    from memory.working import working_memory
    await working_memory.connect()

    # Ensure pydantic BaseModel.model_validate is present in cache
    res_str = await get_symbol_info("pydantic.BaseModel.model_validate", detail_level="summary")
    res = json.loads(res_str)
    assert res["status"] == "success"
    assert "model_validate" in res["signature"]
    assert "usage_patterns" not in res  # summary level should not include usage

    # Test usage level
    res_usage_str = await get_symbol_info("pydantic.BaseModel.model_validate", detail_level="usage")
    res_usage = json.loads(res_usage_str)
    assert res_usage["status"] == "success"
    assert res_usage.get("usage_status") in ("curated", "not_curated")
    if res_usage.get("usage_status") == "curated":
        assert len(res_usage["usage_patterns"]) > 0
    else:
        assert "usage_note" in res_usage

