#!/usr/bin/env python3
"""
[Quick-Win #1] Real-Time Token Usage Tracker
Tanggal: 7 Juli 2026
Trigger: docs/ltm-token-efficiency-audit-2026-07-07.md (Quick-Win #1)

Module untuk log token usage ke PostgreSQL (mcp_knowledge.token_usage).
Dirancang sebagai drop-in wrapper untuk LLM calls.

Usage:
    from scripts.token_tracker_v1 import track_tokens, get_session_summary

    # Track satu LLM call
    track_tokens(
        task_id="task_001",
        agent_id="openai_agent",
        model="gpt-4",
        prompt_tokens=1200,
        completion_tokens=350,
        metadata={"temperature": 0.7}
    )

    # Lihat summary session
    summary = get_session_summary("task_001")
    print(summary)
"""
import os
import json
import psycopg
from typing import Optional, Dict, List
from contextlib import contextmanager
from datetime import datetime

# DB Config (samakan dengan .env)
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5433")),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("PG_PASSWORD") or os.getenv("POSTGRES_PASSWORD"),
    "dbname": os.getenv("POSTGRES_DB", "mcp_knowledge"),
}


class TokenTracker:
    """Real-time token usage logger ke PostgreSQL."""

    def __init__(self, db_config: Optional[dict] = None):
        self.db_config = db_config or DB_CONFIG
        self._conn = None

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(**self.db_config)
        return self._conn

    def log(
        self,
        *,
        task_id: str,
        agent_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        metadata: Optional[dict] = None,
    ) -> str:
        """Insert satu record ke token_usage table.

        Returns:
            UUID dari record yang baru dibuat.
        """
        total = prompt_tokens + completion_tokens
        with self._get_conn().cursor() as cur:
            cur.execute(
                """
                INSERT INTO token_usage
                  (task_id, agent_id, model, prompt_tokens, completion_tokens,
                   total_tokens, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id;
                """,
                (task_id, agent_id, model, prompt_tokens, completion_tokens,
                 total, json.dumps(metadata or {})),
            )
            record_id = str(cur.fetchone()[0])
            self._get_conn().commit()
            return record_id

    def get_session_total(self, task_id: str) -> List[Dict]:
        """Aggregate token usage per model untuk satu task/session.

        Returns:
            List of dicts dengan keys: model, total_prompt, total_completion,
            total_all, calls.
        """
        with self._get_conn().cursor() as cur:
            cur.execute(
                """
                SELECT model,
                       SUM(prompt_tokens) AS total_prompt,
                       SUM(completion_tokens) AS total_completion,
                       SUM(total_tokens) AS total_all,
                       COUNT(*) AS calls
                FROM token_usage
                WHERE task_id = %s
                GROUP BY model
                ORDER BY total_all DESC;
                """,
                (task_id,),
            )
            columns = ["model", "total_prompt", "total_completion", "total_all", "calls"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_agent_summary(
        self, agent_id: str, since_days: int = 30
    ) -> Dict:
        """Get total usage untuk satu agent dalam N hari terakhir."""
        with self._get_conn().cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS total_calls,
                       SUM(prompt_tokens) AS total_prompt,
                       SUM(completion_tokens) AS total_completion,
                       SUM(total_tokens) AS total_all,
                       MIN(created_at) AS first_call,
                       MAX(created_at) AS last_call
                FROM token_usage
                WHERE agent_id = %s
                  AND created_at > NOW() - (%s || ' days')::INTERVAL;
                """,
                (agent_id, str(since_days)),
            )
            row = cur.fetchone()
            return {
                "agent_id": agent_id,
                "total_calls": row[0] or 0,
                "total_prompt_tokens": row[1] or 0,
                "total_completion_tokens": row[2] or 0,
                "total_tokens": row[3] or 0,
                "first_call": row[4].isoformat() if row[4] else None,
                "last_call": row[5].isoformat() if row[5] else None,
                "since_days": since_days,
            }

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()


# Module-level singleton
_tracker: Optional[TokenTracker] = None


def get_tracker() -> TokenTracker:
    """Get singleton TokenTracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = TokenTracker()
    return _tracker


# Convenience functions
def track_tokens(
    *,
    task_id: str,
    agent_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    metadata: Optional[dict] = None,
) -> str:
    """Quick helper untuk track satu LLM call."""
    return get_tracker().log(
        task_id=task_id,
        agent_id=agent_id,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        metadata=metadata,
    )


def get_session_summary(task_id: str) -> List[Dict]:
    """Get session summary by task_id."""
    return get_tracker().get_session_total(task_id)


@contextmanager
def tracked_call(task_id: str, agent_id: str, model: str, metadata: Optional[dict] = None):
    """Context manager helper (untuk future use dengan timing).

    Usage:
        with tracked_call("task_001", "agent_x", "gpt-4") as tracker:
            response = openai_client.chat.completions.create(...)
            # Auto-extract from response.usage
    """
    call_meta = dict(metadata or {})
    call_meta["started_at"] = datetime.utcnow().isoformat()
    yield call_meta
    call_meta["ended_at"] = datetime.utcnow().isoformat()
    # Caller should invoke track_tokens manually after the call


# CLI interface untuk testing
if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("🔧 Quick-Win #1: Token Tracker v1 - Test Run")
    print("=" * 70)

    # Test 1: Log 3 sample calls
    print("\n📋 Test 1: Logging 3 sample token usage records...")
    tracker = get_tracker()
    test_task_id = f"test_token_tracker_v1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    test_calls = [
        ("gpt-4", 1500, 450, {"temperature": 0.7, "purpose": "analysis"}),
        ("gpt-4", 800, 220, {"temperature": 0.7, "purpose": "summary"}),
        ("claude-3-sonnet", 2000, 600, {"temperature": 0.5, "purpose": "reasoning"}),
    ]

    for model, prompt, completion, meta in test_calls:
        rid = tracker.log(
            task_id=test_task_id,
            agent_id="test_agent",
            model=model,
            prompt_tokens=prompt,
            completion_tokens=completion,
            metadata=meta,
        )
        print(f"   ✅ Logged: {rid} ({model}: {prompt}+{completion}={prompt+completion} tokens)")

    # Test 2: Get session summary
    print(f"\n📊 Test 2: Session summary for task_id={test_task_id}...")
    summary = tracker.get_session_total(test_task_id)
    for row in summary:
        print(f"   Model: {row['model']} | Calls: {row['calls']} | Total: {row['total_all']} tokens")

    # Test 3: Agent summary
    print(f"\n📈 Test 3: Agent summary (last 30 days)...")
    agent_sum = tracker.get_agent_summary("test_agent", since_days=30)
    print(f"   Total calls: {agent_sum['total_calls']}")
    print(f"   Total tokens: {agent_sum['total_tokens']}")

    print(f"\n✅ DONE - Token tracker v1 berfungsi dengan baik!")
    print(f"   Test task_id: {test_task_id}")
    print(f"   Total records inserted: {len(test_calls)}")
    print(f"   Total tokens tracked: {sum(c[1]+c[2] for c in test_calls)}")

    tracker.close()
    sys.exit(0)
