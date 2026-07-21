#!/usr/bin/env python3
"""
[Rekomendasi #1 & #2] sync_conversations_to_ltm_v2 - Chunked + Re-sync
Tanggal: 7 Juli 2026
Trigger: docs/ltm-token-efficiency-impl-plan-2026-07-07.md (QW #2 + MT #5)

PERBAIKAN dari sync_conversations_to_ltm.py (line 31):
  Bug lama: `content = "...[TRUNCATED]...\n" + content[-50000:]`
  → Hanya simpan 50K karakter terakhir → hilang USER_INPUT & PLANNER_RESPONSE awal

Strategi v2 (CHUNKED):
1. Baca overview.txt dari ~/.gemini/antigravity/brain/{conv_id}/.system_generated/logs/
2. Parse sebagai JSONL (line-delimited JSON steps)
3. Filter hanya steps yang valid (parseable)
4. Simpan dalam chunks of 5000 chars dengan overlap 200 untuk context preservation
5. Parent entry (summary) + chunked entries (linked via parent_key)
6. Hindari duplicate (idempotent by key)

Usage:
    # Re-sync 8 incomplete logs
    python3 scripts/sync_conversations_to_ltm_v2.py --resync-incomplete

    # Sync semua conversation logs dari brain
    python3 scripts/sync_conversations_to_ltm_v2.py --sync-all

    # Sync specific conv_id
    python3 scripts/sync_conversations_to_ltm_v2.py --conv-id <UUID>
"""
import os
import sys
import json
import glob
import asyncio
import argparse
import psycopg
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Paths
BRAIN_DIR = os.path.expanduser("~/.gemini/antigravity/brain")
PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"

# DB Config
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "user": "mcp_user",
    "password": (os.getenv("PG_PASSWORD") or os.getenv("POSTGRES_PASSWORD")),
    "dbname": "mcp_knowledge",
}

# Chunking config
CHUNK_SIZE = 5000
CHUNK_OVERLAP = 200
SUMMARY_HEAD_TAIL = 500  # chars from start + end for summary


def parse_jsonl_steps(content: str) -> List[Dict]:
    """Parse JSONL content menjadi list of step dicts. Returns [] on failure.

    Robust terhadap:
    - Leading '...[TRUNCATED]...' prefix (skip baris-baris sampai JSON valid pertama)
    - Embedded newlines dalam string values
    - Mixed valid/invalid lines
    """
    steps = []
    # Skip leading truncation marker
    content = content.lstrip()
    if content.startswith('...[TRUNCATED]...'):
        # Cari '{' pertama yang menandai JSON valid
        idx = content.find('\n{')
        if idx == -1:
            return []
        content = content[idx+1:]

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Hanya proses baris yang dimulai dengan '{' (JSON object)
        if not line.startswith('{'):
            continue
        try:
            step = json.loads(line)
            if isinstance(step, dict):
                steps.append(step)
        except json.JSONDecodeError:
            continue
    return steps


def chunk_content(content: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split content into chunks with overlap."""
    if len(content) <= chunk_size:
        return [content]
    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(content), step):
        chunk = content[i:i + chunk_size]
        if chunk:
            chunks.append(chunk)
    return chunks


def generate_summary(content: str) -> str:
    """Generate short summary dari head + tail content."""
    if len(content) <= SUMMARY_HEAD_TAIL * 2:
        return content
    return (
        f"[SUMMARY] First {SUMMARY_HEAD_TAIL} chars:\n"
        f"{content[:SUMMARY_HEAD_TAIL]}\n\n"
        f"...[TRUNCATED {len(content) - SUMMARY_HEAD_TAIL * 2} chars]...\n\n"
        f"Last {SUMMARY_HEAD_TAIL} chars:\n"
        f"{content[-SUMMARY_HEAD_TAIL:]}"
    )


def find_incomplete_conversations(conn) -> List[Dict]:
    """Find conversation logs in LTM that are incomplete (0 or <3 steps)."""
    incomplete = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT key, content, LENGTH(content) as size, created_at
            FROM memories
            WHERE namespace = 'agent_conversations'
              AND (metadata->>'type' IS NULL OR metadata->>'type' = 'conversation_summary')
            ORDER BY created_at DESC;
    """)
        for key, content, size, created_at in cur.fetchall():
            steps = parse_jsonl_steps(content)
            types = set(s.get('type', '') for s in steps)
            has_minimum = 'USER_INPUT' in types and 'PLANNER_RESPONSE' in types
            is_complete = has_minimum and len(steps) >= 3
            if not is_complete:
                # Extract conv_id from key (format: antigravity_conv_{UUID})
                parts = key.split('_')
                conv_id = parts[-1] if len(parts) >= 3 else None
                incomplete.append({
                    "key": key,
                    "conv_id": conv_id,
                    "size": size,
                    "steps": len(steps),
                    "types": list(types),
                    "created_at": created_at.isoformat(),
                })
    return incomplete


def save_memory(conn, *, key: str, content: str, metadata: dict):
    """Save or update a memory entry (idempotent)."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO memories (namespace, key, content, metadata)
            VALUES (%s, %s, %s, %s::jsonb)
            ON CONFLICT (namespace, key) DO UPDATE SET
                content = EXCLUDED.content,
                metadata = EXCLUDED.metadata
            RETURNING id;
        """, ("agent_conversations", key, content, json.dumps(metadata)))
        new_id = cur.fetchone()[0]
        conn.commit()
        return str(new_id)


def resync_from_brain(conv_id: str, dry_run: bool = False) -> Dict:
    """Re-sync satu conversation log dari brain dengan chunked strategy.
    
    Returns dict dengan status: synced, chunks_count, steps_count, total_size.
    """
    conv_path = os.path.join(BRAIN_DIR, conv_id)
    if not os.path.isdir(conv_path):
        return {"status": "error", "message": f"Brain dir not found: {conv_path}"}

    overview_path = os.path.join(conv_path, ".system_generated", "logs", "overview.txt")
    if not os.path.exists(overview_path):
        return {"status": "error", "message": f"overview.txt not found in {conv_path}"}

    with open(overview_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse steps
    steps = parse_jsonl_steps(content)
    if not steps:
        return {
            "status": "error",
            "message": f"No parseable JSONL steps in {overview_path}",
            "file_size": len(content),
        }

    types_count = {}
    for s in steps:
        t = s.get('type', 'unknown')
        types_count[t] = types_count.get(t, 0) + 1

    if dry_run:
        return {
            "status": "dry_run",
            "conv_id": conv_id,
            "file_size": len(content),
            "steps_count": len(steps),
            "types_count": types_count,
            "chunks_count": len(chunk_content(content)),
        }

    # Save to DB
    conn = psycopg.connect(**DB_CONFIG)

    # 1. Save parent (summary)
    parent_key = f"antigravity_conv_{conv_id}"
    parent_summary = generate_summary(content)
    parent_meta = {
        "type": "conversation_summary",
        "conv_id": conv_id,
        "total_steps": len(steps),
        "total_size": len(content),
        "source": "antigravity_brain",
        "sync_version": "v2_chunked",
        "types_count": types_count,
    }
    parent_id = save_memory(conn, key=parent_key, content=parent_summary, metadata=parent_meta)

    # 2. Save chunks
    chunks = chunk_content(content)
    chunk_ids = []
    for idx, chunk in enumerate(chunks):
        chunk_key = f"antigravity_conv_chunk_{conv_id}_{idx:03d}"
        chunk_meta = {
            "type": "conversation_chunk",
            "parent_key": parent_key,
            "parent_id": parent_id,
            "chunk_index": idx,
            "total_chunks": len(chunks),
            "chunk_size": len(chunk),
            "sync_version": "v2_chunked",
        }
        cid = save_memory(conn, key=chunk_key, content=chunk, metadata=chunk_meta)
        chunk_ids.append(cid)

    # 3. Save raw steps as JSONL (for parsing convenience)
    raw_key = f"antigravity_conv_raw_{conv_id}"
    raw_content = "\n".join(json.dumps(s, ensure_ascii=False) for s in steps)
    raw_meta = {
        "type": "conversation_raw_jsonl",
        "parent_key": parent_key,
        "conv_id": conv_id,
        "steps_count": len(steps),
        "types_count": types_count,
        "sync_version": "v2_chunked",
    }
    raw_id = save_memory(conn, key=raw_key, content=raw_content, metadata=raw_meta)

    conn.close()

    return {
        "status": "synced",
        "conv_id": conv_id,
        "parent_id": parent_id,
        "chunks_count": len(chunks),
        "chunk_ids": chunk_ids,
        "raw_id": raw_id,
        "steps_count": len(steps),
        "types_count": types_count,
        "total_size": len(content),
    }


def main():
    parser = argparse.ArgumentParser(description="Sync conversation logs from Antigravity brain to LTM (v2 chunked)")
    parser.add_argument("--resync-incomplete", action="store_true",
                        help="Re-sync incomplete conversation logs (steps < 3 or missing required types)")
    parser.add_argument("--sync-all", action="store_true",
                        help="Sync all conversation logs from brain (idempotent)")
    parser.add_argument("--conv-id", type=str, help="Sync specific conv_id")
    parser.add_argument("--dry-run", action="store_true", help="Dry run, don't save to DB")
    parser.add_argument("--list-incomplete", action="store_true", help="List incomplete convs only")
    parser.add_argument("--days", type=int, help="Only sync conversations modified in the last N days")
    args = parser.parse_args()

    print("=" * 70)
    print("🔄 sync_conversations_to_ltm_v2 (Chunked Strategy)")
    print("=" * 70)

    if args.list_incomplete or args.resync_incomplete:
        conn = psycopg.connect(**DB_CONFIG)
        incomplete = find_incomplete_conversations(conn)
        conn.close()

        print(f"\n📊 Found {len(incomplete)} incomplete conversation logs:\n")
        for inc in incomplete:
            print(f"   ❌ {inc['key']}")
            print(f"      conv_id: {inc['conv_id']}")
            print(f"      size: {inc['size']:,} chars | steps: {inc['steps']} | types: {inc['types']}")

        if args.list_incomplete:
            return 0

        if not args.resync_incomplete:
            return 0

        # Re-sync mode
        print(f"\n🔄 Re-syncing {len(incomplete)} incomplete conversations...")
        success = 0
        error = 0
        for inc in incomplete:
            if not inc['conv_id']:
                print(f"   ⚠️  {inc['key']} - no conv_id, skip")
                error += 1
                continue
            print(f"\n   → {inc['conv_id']}")
            result = resync_from_brain(inc['conv_id'], dry_run=args.dry_run)
            print(f"      Status: {result.get('status')}")
            if result.get('status') == 'synced':
                print(f"      Steps: {result['steps_count']} | Chunks: {result['chunks_count']} | Size: {result['total_size']:,} chars")
                print(f"      Types: {result['types_count']}")
                success += 1
            elif result.get('status') == 'dry_run':
                print(f"      [DRY RUN] Steps: {result['steps_count']} | Chunks: {result['chunks_count']}")
            else:
                print(f"      Error: {result.get('message')}")
                error += 1

        print(f"\n✅ Done: {success} synced, {error} error")
        return 0 if error == 0 else 1

    elif args.sync_all or args.conv_id:
        if args.conv_id:
            conv_ids = [args.conv_id]
        else:
            # List all conv dirs in brain
            if not os.path.isdir(BRAIN_DIR):
                print(f"❌ Brain dir not found: {BRAIN_DIR}")
                return 1
            
            import time
            current_time = time.time()
            conv_ids = []
            for d in os.listdir(BRAIN_DIR):
                full_path = os.path.join(BRAIN_DIR, d)
                if os.path.isdir(full_path):
                    if args.days:
                        mtime = os.path.getmtime(full_path)
                        if (current_time - mtime) > (args.days * 86400):
                            continue
                    conv_ids.append(d)

        print(f"\n🔄 Syncing {len(conv_ids)} conversations from brain...")
        success = 0
        for cid in conv_ids:
            print(f"   → {cid} ...", end=" ")
            result = resync_from_brain(cid, dry_run=args.dry_run)
            status = result.get('status', 'unknown')
            print(status)
            if status == 'synced':
                success += 1

        print(f"\n✅ {success}/{len(conv_ids)} synced successfully")
        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
