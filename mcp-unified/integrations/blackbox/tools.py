#!/usr/bin/env python3
"""BlackboxAI MCP Tools - Connected to LTM for persistent context."""

from typing import Dict, Any, List
import sys
# Path sudah diset oleh PYTHONPATH dan mcp_server_sse.py — tidak perlu inject manual

from tools.base import register_tool
from memory.longterm import memory_save, memory_search, memory_list, memory_get

@register_tool
async def blackbox_code_assist(code_snippet: str, language: str = "python", namespace: str = "default") -> str:
    """AI code assistance with LTM context."""
    search_result = await memory_search(
        query=f"{language} code assistance {code_snippet[:50]}",
        namespace=namespace, limit=3
    )
    suggestion = f'[{namespace}] Saran untuk {language}:'
    if search_result.get('success') and search_result.get('results'):
        suggestion += "\n\nContext dari LTM:"
        for r in search_result['results'][:2]:
            suggestion += f"\n- {r['content'][:100]}..."
    await memory_save(
        key=f"code_assist_{language}_{hash(code_snippet) % 10000}",
        content=f"Code assist for {language}: {code_snippet[:200]}",
        metadata={"type": "code_assist", "language": language},
        namespace=namespace
    )
    return suggestion

@register_tool
async def blackbox_search_project(query: str, path: str = ".", namespace: str = "default") -> Dict[str, Any]:
    """Semantic search using LTM vector store."""
    results = await memory_search(query=query, namespace=namespace, limit=10, strategy="hybrid")
    await memory_save(
        key=f"search_{hash(query) % 100000}",
        content=f"User searched: {query}",
        metadata={"type": "search_query", "path": path},
        namespace=namespace
    )
    return results

@register_tool
async def blackbox_agent_workflow(task: str, namespace: str = "default") -> Dict[str, Any]:
    """Agent workflow with LTM persistence."""
    prev = await memory_get(f"workflow_state_{namespace}", namespace)
    workflow_id = hash(task) % 100000
    await memory_save(
        key=f"workflow_{workflow_id}",
        content=f"Workflow: {task}",
        metadata={"status": "in_progress", "task": task[:100]},
        namespace=namespace
    )
    await memory_save(
        key=f"workflow_state_{namespace}",
        content=f"Last workflow: {task}",
        metadata={"workflow_id": workflow_id, "status": "completed"},
        namespace=namespace
    )
    return {
        "status": "completed",
        "result": f"Workflow selesai untuk: {task}",
        "workflow_id": workflow_id,
        "previous_context": prev.get('content') if prev else None
    }

@register_tool
async def blackbox_save_memory(key: str, content: str, metadata: Dict = None, namespace: str = "default") -> Dict[str, Any]:
    """Direct save to LTM."""
    return await memory_save(key=key, content=content, metadata=metadata or {}, namespace=namespace)

@register_tool
async def blackbox_get_memory(key: str, namespace: str = "default") -> Dict[str, Any]:
    """Direct read from LTM."""
    return await memory_get(key=key, namespace=namespace)

@register_tool
async def blackbox_list_memories(namespace: str = "default", limit: int = 10) -> Dict[str, Any]:
    """List memories in namespace."""
    return await memory_list(namespace=namespace, limit=limit)
