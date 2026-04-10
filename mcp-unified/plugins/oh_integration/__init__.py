"""
OpenHands Integration Plugin for MCP Unified.

Provides autonomous coding agent capabilities via OpenHands SDK.
Tools: run_coding_task, get_task_status, list_active_agents, cancel_coding_task

Auto-discovered oleh mcp-unified plugin system.
"""

__all__ = []

# Module import dilakukan lazy oleh discovery.py untuk menghindari
# import-time side effects saat test collection.
