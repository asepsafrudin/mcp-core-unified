"""
Dynamic MCP Registry for Microsoft Agent Framework (MAF)
Provides unified connection to MCP servers via MCPStdioTool and MCPStreamableHTTPTool.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_framework import MCPStdioTool, MCPStreamableHTTPTool

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


class DynamicMCPRegistry:
    """Manages MCP tool connections for MAF agents."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or REPO_ROOT
        self.python_bin = str(VENV_PYTHON if VENV_PYTHON.exists() else sys.executable)
        self._tools: Dict[str, Any] = {}

    def get_unified_stdio_tool(self, allowed_tools: Optional[List[str]] = None) -> MCPStdioTool:
        """Create an MCPStdioTool instance connected to core/mcp-unified."""
        server_script = str(self.repo_root / "core" / "mcp-unified" / "mcp_server.py")
        env = dict(os.environ)

        tool = MCPStdioTool(
            name="mcp-unified",
            command=self.python_bin,
            args=[server_script, "--stdio"],
            env=env,
            allowed_tools=allowed_tools,
            description="Universal MCP toolset for database, memory, search, and document tasks",
        )
        self._tools["mcp-unified"] = tool
        return tool

    def get_unified_http_tool(self, url: str = "http://localhost:8000/sse") -> MCPStreamableHTTPTool:
        """Create an MCPStreamableHTTPTool connected to mcp-unified persistent daemon."""
        tool = MCPStreamableHTTPTool(
            name="mcp-unified-sse",
            url=url,
            description="Persistent SSE MCP toolset for real-time memory and queries",
        )
        self._tools["mcp-unified-sse"] = tool
        return tool

    def get_tools_for_profile(self, profile: str) -> List[Any]:
        """Return curated list of MCP tools based on agent profile.
        
        Profiles:
            - 'legal': Database, knowledge search, legal doctrine evaluator
            - 'coding': Filesystem, bash runner, symbol search, git
            - 'admin': Memory, scheduler, status, database
            - 'full': All tools available
        """
        if profile in ("legal", "legal_full"):
            allowed = [
                "query_db", "describe_table", "knowledge_search",
                "ocr_extract_text", "ocr_parse_document", "legal_evaluate_doctrine",
                "legal_ast_parse", "legal_lint_editorial", "legal_transform_clause",
                "legal_disposition_matrix", "legal_verify_hierarchy", "legal_verify_jurisdiction",
                "legal_mandate_check", "legal_governance_loop",
                "legal_deontic_verify", "legal_anatomy_validate", "legal_naskah_akademik_generate",
                "legal_harmonization_matrix", "legal_opinion_irac", "legal_contract_vetting",
                "legal_litigation_advocacy"
            ]
            return [self.get_unified_stdio_tool(allowed_tools=allowed)]
        elif profile == "legal_drafting":
            allowed = [
                "query_db", "knowledge_search", "legal_ast_parse", "legal_lint_editorial",
                "legal_transform_clause", "legal_disposition_matrix", "legal_verify_hierarchy",
                "legal_deontic_verify", "legal_anatomy_validate", "legal_naskah_akademik_generate",
                "legal_harmonization_matrix"
            ]
            return [self.get_unified_stdio_tool(allowed_tools=allowed)]
        elif profile == "legal_counsel":
            allowed = [
                "query_db", "knowledge_search", "legal_evaluate_doctrine", "legal_verify_jurisdiction",
                "legal_mandate_check", "legal_opinion_irac", "legal_contract_vetting",
                "legal_litigation_advocacy"
            ]
            return [self.get_unified_stdio_tool(allowed_tools=allowed)]
        elif profile == "coding":
            allowed = [
                "memory_search", "memory_save", "query_db"
            ]
            return [self.get_unified_stdio_tool(allowed_tools=allowed)]
        elif profile == "admin":
            allowed = [
                "memory_save", "memory_search", "memory_list",
                "scheduler_list_jobs", "scheduler_get_status", "query_db"
            ]
            return [self.get_unified_stdio_tool(allowed_tools=allowed)]
        else:
            return [self.get_unified_stdio_tool()]

