"""
MCP tools/list dump profiles.

Default profile is ide-core: only a small daily-use set is advertised to
clients. Hidden tools stay registered and remain callable via tools/call.

Rollback for the review window:
    MCP_TOOL_DUMP_PROFILE=full
"""
from __future__ import annotations

import inspect
import os
from typing import Any, Callable, Dict, FrozenSet, List, Optional

IDE_CORE_DUMP_TOOLS: FrozenSet[str] = frozenset(
    {
        "memory_search",
        "memory_save",
        "memory_list",
        "memory_delete",
        "knowledge_search",
        "knowledge_list_namespaces",
        "query_db",
        "list_tables",
        "describe_table",
        "count_rows",
        "search_korespondensi",
        "parse_surat_status",
        "Desktop-Dokin-2025",
        "create_plan",
        "save_plan_experience",
        "mcp_health_check",
        "ocr_extract_text",
        "ocr_parse_document",
        "scheduler_list_jobs",
        "scheduler_get_status",
        "whatsapp_get_status",
        "whatsapp_list_chats",
    }
)

_HIDDEN_SCHEMA_PARAMS = frozenset({"self", "ctx", "context"})


def get_dump_profile() -> str:
    raw = os.getenv("MCP_TOOL_DUMP_PROFILE", "ide-core").strip().lower()
    if raw in {"full", "all", "off"}:
        return "full"
    return "ide-core"


def should_dump_tool(name: str, profile: Optional[str] = None) -> bool:
    resolved = profile or get_dump_profile()
    if resolved == "full":
        return True
    return name in IDE_CORE_DUMP_TOOLS


def filter_dumped_tools(tool_infos: List[Dict[str, str]]) -> List[Dict[str, str]]:
    profile = get_dump_profile()
    if profile == "full":
        return tool_infos
    return [info for info in tool_infos if info.get("name") in IDE_CORE_DUMP_TOOLS]


def build_input_schema(tool_func: Callable[..., Any]) -> Dict[str, Any]:
    """Public JSON schema for tools/list. Omits MCP-injected ctx/self."""
    sig = inspect.signature(tool_func)
    params: Dict[str, Any] = {}
    required_params: List[str] = []
    type_map = {int: "number", bool: "boolean", list: "array", dict: "object"}

    for param_name, param in sig.parameters.items():
        if param_name in _HIDDEN_SCHEMA_PARAMS:
            continue
        param_type = "string"
        if param.annotation is not inspect.Parameter.empty:
            param_type = type_map.get(param.annotation, "string")
        params[param_name] = {
            "type": param_type,
            "description": param_name.replace("_", " ").title(),
        }
        if param.default is inspect.Parameter.empty:
            required_params.append(param_name)

    schema: Dict[str, Any] = {"type": "object", "properties": params}
    if required_params:
        schema["required"] = required_params
        schema["additionalProperties"] = False
    else:
        schema["required"] = []
        schema["additionalProperties"] = False
        schema["title"] = "no-arguments"
    return schema
