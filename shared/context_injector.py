"""
Context Injector — Auto-load project context untuk agent baru.

Mengambil konteks relevan dari MCP Hub memory dan menyusunnya
menjadi "handover brief" yang siap di-inject ke agent.

Usage:
    from shared.context_injector import ContextInjector

    injector = ContextInjector(client)
    brief = await injector.get_brief()
    print(brief)  # Paste ke agent atau inject ke system prompt
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path


class ContextInjector:
    """
    Membangun context bundle dari memory yang tersimpan di MCP Hub.

    [REVIEWER] Context bundle dirancang untuk:
    1. Minimal token usage — hanya yang relevan
    2. Structured untuk mudah dibaca agent
    3. Actionable — agent langsung tahu apa yang harus dilakukan
    """

    # Keys yang selalu dicari untuk context
    CONTEXT_KEYS = {
        "active_tasks": "task yang sedang berjalan",
        "decisions": "keputusan teknis penting",
        "architecture": "arsitektur sistem",
        "blockers": "blocker atau isu yang belum resolved",
        "last_session": "ringkasan sesi terakhir",
    }

    def __init__(self, client):
        """
        Args:
            client: MCPClient instance yang sudah connected
        """
        self.client = client
        self.namespace = client.namespace

    async def get_brief(self, max_memories: int = 10) -> str:
        """
        Bangun handover brief untuk agent baru.

        Returns:
            String yang siap di-paste ke agent atau di-inject ke system prompt.
        """
        sections = []

        # Header
        sections.append(self._build_header())

        # Section 1: Active tasks
        tasks = await self._get_active_tasks()
        if tasks:
            sections.append(self._format_section("🎯 ACTIVE TASKS", tasks))

        # Section 2: Recent decisions
        decisions = await self._get_decisions()
        if decisions:
            sections.append(self._format_section("⚡ KEY DECISIONS", decisions))

        # Section 3: Blockers
        blockers = await self._get_blockers()
        if blockers:
            sections.append(self._format_section("🚧 BLOCKERS", blockers))

        # Section 4: Recent memories (general)
        recent = await self._get_recent_memories(limit=max_memories)
        if recent:
            sections.append(self._format_section("📝 RECENT CONTEXT", recent))

        # Section 5: Suggested next actions
        sections.append(self._build_footer())

        return "\n\n".join(sections)

    def _build_header(self) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"""# MCP Hub — Context Brief
**Project:** {self.namespace}
**Generated:** {now}
**Hub:** {self.client._base_url}

> Ini adalah context otomatis dari MCP Hub.
> Lanjutkan pekerjaan dari titik ini."""

    def _build_footer(self) -> str:
        return f"""---
**Quick Commands:**
```python
from shared.mcp_client import MCPClient
client = MCPClient()  # namespace: {self.namespace}

# Cari konteks spesifik
results = await client.search_context("topik yang dicari")

# Simpan progress
await client.save_context("session_note", "apa yang dikerjakan hari ini")

# List semua memories
context = await client.get_context()
```"""

    def _format_section(self, title: str, items: List[Dict]) -> str:
        lines = [f"## {title}"]
        for item in items:
            content = item.get("content", "")
            key = item.get("key", "")
            created = item.get("created_at", "")[:10] if item.get("created_at") else ""

            # Truncate panjang content untuk brief
            if len(content) > 200:
                content = content[:200] + "..."

            lines.append(f"- **[{key}]** {content}")
            if created:
                lines.append(f"  *(saved: {created})*")

        return "\n".join(lines)

    async def _get_active_tasks(self) -> List[Dict]:
        """Cari memories yang berhubungan dengan active tasks."""
        result = await self.client.call(
            "memory_search",
            query="active task todo in progress pending",
            limit=5,
            strategy="hybrid"
        )
        return result.get("results", [])

    async def _get_decisions(self) -> List[Dict]:
        """Cari keputusan teknis yang pernah dibuat."""
        result = await self.client.call(
            "memory_search",
            query="decision architecture decided chosen approach",
            limit=3,
            strategy="hybrid"
        )
        return result.get("results", [])

    async def _get_blockers(self) -> List[Dict]:
        """Cari blocker atau isu yang belum resolved."""
        result = await self.client.call(
            "memory_search",
            query="blocker issue problem blocked waiting",
            limit=3,
            strategy="hybrid"
        )
        return result.get("results", [])

    async def _get_recent_memories(self, limit: int = 5) -> List[Dict]:
        """Ambil memories terbaru dari namespace ini."""
        result = await self.client.call(
            "memory_list",
            limit=limit,
            offset=0
        )
        return result.get("memories", [])

    async def save_session_summary(self, summary: str, tags: List[str] = None):
        """
        Simpan ringkasan sesi ini ke memory.
        Dipanggil di akhir sesi agar sesi berikutnya punya konteks.

        Args:
            summary: Apa yang dikerjakan di sesi ini
            tags: Label untuk memudahkan pencarian
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return await self.client.save_context(
            key=f"last_session",
            content=f"[{now}] {summary}",
            metadata={
                "type": "session_summary",
                "tags": tags or [],
                "namespace": self.namespace
            }
        )

    async def save_decision(self, decision_key: str, description: str, rationale: str = ""):
        """
        Simpan keputusan teknis penting.

        Args:
            decision_key: Identifier singkat (e.g. "use_postgres_not_sqlite")
            description: Deskripsi keputusan
            rationale: Alasan di balik keputusan
        """
        content = description
        if rationale:
            content += f"\nRationale: {rationale}"

        return await self.client.save_context(
            key=f"decisions:{decision_key}",
            content=content,
            metadata={
                "type": "decision",
                "rationale": rationale,
                "namespace": self.namespace
            }
        )

    async def save_active_task(self, task_key: str, description: str, status: str = "in_progress"):
        """
        Simpan atau update task yang sedang aktif.

        Args:
            task_key: Identifier task (e.g. "implement_auth")
            description: Deskripsi task dan progress
            status: "in_progress", "blocked", "pending_review"
        """
        return await self.client.save_context(
            key=f"tasks:{task_key}",
            content=description,
            metadata={
                "type": "active_task",
                "status": status,
                "namespace": self.namespace
            }
        )
