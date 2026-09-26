"""
Telemetry & Security Guardrails for Microsoft Agent Framework (MAF)
Integrates OpenTelemetry observability and enforces workspace safeguard rules:
- Rule #1: Data Loss Prevention (Dangerous SQL rejection)
- Rule #4: Storage Isolation (Prevention of persistent state in code directories)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, Optional

from agent_framework import ToolApprovalMiddleware, ToolApprovalState

logger = logging.getLogger("maf.telemetry")


class MAFTelemetryGuardrails:
    """Provides security middleware and observability for MAF agents."""

    DANGEROUS_SQL_PATTERNS = [
        r"\bDROP\s+TABLE\b",
        r"\bDROP\s+DATABASE\b",
        r"\bTRUNCATE\s+TABLE\b",
        r"\bDELETE\s+FROM\s+\w+\s*(?:;|$)",  # DELETE without WHERE clause
    ]

    @classmethod
    def validate_sql_safety(cls, query: str) -> bool:
        """Validate whether a SQL statement complies with Data Loss Prevention protocols."""
        normalized = query.strip().upper()
        for pattern in cls.DANGEROUS_SQL_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                logger.warning(f"[MAF Guardrail] Destructive SQL pattern detected and blocked: {query[:100]}")
                return False
        return True

    @classmethod
    def validate_storage_path(cls, file_path: str) -> bool:
        """Validate whether a target output file adheres to storage isolation protocols."""
        forbidden_prefixes = ["core/", "scripts/", "docs/00-meta/"]
        normalized = file_path.replace("\\", "/").lower()
        for prefix in forbidden_prefixes:
            if prefix in normalized:
                logger.warning(f"[MAF Guardrail] Storage isolation violation: Cannot write state/data to {file_path}")
                return False
        return True

    @classmethod
    def create_safety_middleware(cls) -> ToolApprovalMiddleware:
        """Create a ToolApprovalMiddleware that automatically blocks unsafe operations."""
        def safety_rule(context: Any) -> ToolApprovalState:
            tool_name = getattr(context, "name", "")
            args = getattr(context, "arguments", {}) or {}

            # Check SQL queries
            if "query" in args and isinstance(args["query"], str):
                if not cls.validate_sql_safety(args["query"]):
                    return ToolApprovalState.REJECTED

            # Check file writes
            if "target_file" in args and isinstance(args["target_file"], str):
                if not cls.validate_storage_path(args["target_file"]):
                    return ToolApprovalState.REJECTED

            return ToolApprovalState.APPROVED

        return ToolApprovalMiddleware(
            source_id="workspace_safety_guardrails",
            auto_approval_rules=[safety_rule],
        )
