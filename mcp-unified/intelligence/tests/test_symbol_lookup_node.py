"""
Unit tests for LangGraph symbol_lookup_node and route_after_lookup (TASK-125 / TASK-120).
"""

import pytest
import pytest_asyncio
import asyncio
from intelligence.symbol_lookup_node import (
    symbol_lookup_node,
    route_after_lookup,
    LookupOutcome,
    AgentState,
)
from memory.working import working_memory


@pytest_asyncio.fixture(autouse=True)
async def manage_redis_lifecycle():
    """Ensure clean redis connect and disconnect lifecycle per test."""
    await working_memory.connect()
    yield
    await working_memory.disconnect()



@pytest.mark.asyncio
async def test_symbol_lookup_curated_flow():
    """Test lookup on a curated symbol (pydantic.BaseModel.model_validate)."""

    
    state: AgentState = {
        "symbol_path": "pydantic.BaseModel.model_validate",
        "requested_detail": "usage"
    }

    out_state = await symbol_lookup_node(state)
    assert out_state["lookup_outcome"] == LookupOutcome.CURATED.value
    assert out_state["needs_full_source"] is False
    assert out_state["needs_llm_fallback"] is False
    assert out_state["token_cost"] > 0

    next_node = route_after_lookup(out_state)
    assert next_node == "generator_node"


@pytest.mark.asyncio
async def test_symbol_lookup_not_curated_long_doc_flow():
    """Test uncurated symbol with long/informative docstring (asyncpg.connect -> generator_node)."""
    await working_memory.connect()
    
    state: AgentState = {
        "symbol_path": "asyncpg.connect",
        "requested_detail": "usage"
    }

    out_state = await symbol_lookup_node(state)
    assert out_state["lookup_outcome"] == LookupOutcome.NOT_CURATED.value
    assert out_state["has_full_docstring"] is True
    assert out_state["needs_full_source"] is False

    next_node = route_after_lookup(out_state)
    assert next_node == "generator_node"




@pytest.mark.asyncio
async def test_symbol_lookup_not_curated_thin_doc_flow():
    """Test uncurated symbol with thin docstring (pydantic.Field -> full_source_fetch_node)."""
    await working_memory.connect()
    
    state: AgentState = {
        "symbol_path": "pydantic.Field",
        "requested_detail": "usage"
    }

    out_state = await symbol_lookup_node(state)
    assert out_state["lookup_outcome"] == LookupOutcome.NOT_CURATED.value
    assert out_state["has_full_docstring"] is False
    assert out_state["needs_full_source"] is True

    next_node = route_after_lookup(out_state)
    assert next_node == "full_source_fetch_node"




@pytest.mark.asyncio
async def test_symbol_lookup_not_found_flow():
    """Test lookup on a non-existent symbol (nonexistent.Lib.foo)."""
    await working_memory.connect()
    
    state: AgentState = {
        "symbol_path": "nonexistent.fake_package_xyz.foo",
        "requested_detail": "usage"
    }

    out_state = await symbol_lookup_node(state)
    assert out_state["lookup_outcome"] == LookupOutcome.NOT_FOUND.value
    assert out_state["needs_llm_fallback"] is True

    next_node = route_after_lookup(out_state)
    assert next_node == "llm_knowledge_fallback_node"


@pytest.mark.asyncio
async def test_symbol_lookup_empty_input_error_flow():
    """Test lookup on empty input triggering validation error routing."""
    state: AgentState = {
        "symbol_path": "",
        "requested_detail": "usage"
    }

    out_state = await symbol_lookup_node(state)
    assert out_state["lookup_outcome"] == LookupOutcome.ERROR.value
    assert out_state["needs_llm_fallback"] is True
    assert "_error" in out_state

    next_node = route_after_lookup(out_state)
    assert next_node == "lookup_error_node"


@pytest.mark.asyncio
async def test_symbol_lookup_infrastructure_crash_error_flow(monkeypatch):
    """
    Test infra failure (e.g. Redis connection refused / socket timeout / network partition)
    during get_symbol_info execution, verifying boundary exception handling and error routing.
    """
    import intelligence.symbol_lookup_node as node_mod

    async def mock_crashing_get_symbol_info(*args, **kwargs):
        raise ConnectionError("Redis cluster connection timeout (simulate infra crash)")

    monkeypatch.setattr(node_mod, "get_symbol_info", mock_crashing_get_symbol_info)

    state: AgentState = {
        "symbol_path": "pydantic.BaseModel.model_validate",
        "requested_detail": "usage"
    }

    out_state = await symbol_lookup_node(state)
    assert out_state["lookup_outcome"] == LookupOutcome.ERROR.value
    assert out_state["symbol_info"] is None
    assert out_state["needs_llm_fallback"] is True
    assert "Redis cluster connection timeout" in out_state.get("_error", "")

    next_node = route_after_lookup(out_state)
    assert next_node == "lookup_error_node"


@pytest.mark.asyncio
async def test_full_source_fetch_node_execution():
    """Verify full_source_fetch_node fetches bounded source code without blowing up token cost."""
    await working_memory.connect()
    
    # Start with a symbol that has thin docstring
    state: AgentState = {
        "symbol_path": "pydantic.Field",
        "requested_detail": "usage"
    }

    # Step 1: Lookup
    state = await symbol_lookup_node(state)
    assert state["needs_full_source"] is True

    # Step 2: Fetch source
    from intelligence.symbol_lookup_node import full_source_fetch_node, generator_node
    state = await full_source_fetch_node(state)
    assert state["needs_full_source"] is False
    assert state["source_snippet"] is not None
    assert len(state["source_snippet"]) <= 2100  # bounded token budget
    assert "pydantic" in state["symbol_info"]["file_location"]

    # Step 3: Generator composition
    state = await generator_node(state)
    assert "[TARGET SOURCE CODE EXCERPT" in state["composed_prompt"]


@pytest.mark.asyncio
async def test_compiled_langgraph_pipeline_execution():
    """Test full LangGraph StateGraph execution from entrypoint to terminal end."""
    await working_memory.connect()
    from intelligence.symbol_lookup_node import build_symbol_orchestrator_graph

    graph = build_symbol_orchestrator_graph()

    # 1. Curated pipeline execution
    res1 = await graph.ainvoke({
        "symbol_path": "pydantic.BaseModel.model_validate",
        "requested_detail": "usage",
        "query_context": "Parse incoming user payload safely."
    })
    assert res1["lookup_outcome"] == "curated"
    assert "[VERIFIED API USAGE PATTERNS]" in res1["composed_prompt"]

    # 2. Thin docstring pipeline execution (routes via full_source_fetch_node)
    res2 = await graph.ainvoke({
        "symbol_path": "pydantic.Field",
        "requested_detail": "usage",
        "query_context": "Define default model field."
    })
    assert res2["lookup_outcome"] == "not_curated"
    assert res2["source_snippet"] is not None
    assert "[TARGET SOURCE CODE EXCERPT" in res2["composed_prompt"]

    # 3. Not found pipeline execution (routes via llm_knowledge_fallback_node)
    res3 = await graph.ainvoke({
        "symbol_path": "nonexistent.fake_package_xyz.foo",
        "requested_detail": "usage"
    })
    assert res3["lookup_outcome"] == "not_found"
    assert "[DISCLAIMER: NO LOCAL GROUND TRUTH FOUND]" in res3["composed_prompt"]

    # 4. Long docstring pipeline execution (direct to generator, no full_source_fetch)
    res4 = await graph.ainvoke({
        "symbol_path": "asyncpg.connect",
        "requested_detail": "usage"
    })
    assert res4["lookup_outcome"] == "not_curated"
    assert res4.get("source_snippet") is None
    assert "[OFFICIAL API SIGNATURE & DOCSTRING]" in res4["composed_prompt"]

    # 5. Empty input error execution (routes via lookup_error_node -> END)
    res5 = await graph.ainvoke({
        "symbol_path": "",
        "requested_detail": "usage"
    })
    assert res5["lookup_outcome"] == "error"
    assert "[SYSTEM ERROR]" in res5["composed_prompt"]
    assert "Empty symbol_path" in res5["routing_reason"]



@pytest.mark.asyncio
async def test_compiled_langgraph_pipeline_infrastructure_crash_flow(monkeypatch):
    """
    Verify compiled LangGraph graph gracefully terminates at lookup_error_node -> END
    without unhandled crashes when underlying Redis/tools infrastructure fails.
    """
    import intelligence.symbol_lookup_node as node_mod
    from intelligence.symbol_lookup_node import build_symbol_orchestrator_graph

    async def mock_crashing_get_symbol_info(*args, **kwargs):
        raise ConnectionError("Redis server connection reset by peer during pipeline execution")

    monkeypatch.setattr(node_mod, "get_symbol_info", mock_crashing_get_symbol_info)

    graph = build_symbol_orchestrator_graph()

    res = await graph.ainvoke({
        "symbol_path": "pydantic.BaseModel.model_validate",
        "requested_detail": "usage"
    })

    assert res["lookup_outcome"] == "error"
    assert res["symbol_info"] is None
    assert "[SYSTEM ERROR]" in res["composed_prompt"]
    assert "Redis server connection reset by peer" in res["composed_prompt"]
    assert "Routing halted due to error" in res["routing_reason"]



