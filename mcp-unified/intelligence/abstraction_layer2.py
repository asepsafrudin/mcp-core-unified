#!/usr/bin/env python3
"""
[QW #3] Abstraction Layer 2 - Knowledge Distillation
Tanggal: 7 Juli 2026
Trigger: docs/ltm-token-efficiency-impl-plan-2026-07-07.md (QW #3)

Implementasi Layer 2 Abstraction: Ekstrak patterns, rules, generalizations
dari LTM entries yang ada dan simpan ke knowledge_documents table.

Menggunakan Groq API (GROQ_API_KEY_BOT_WHATSAPP) dengan model llama-3.1-8b-instant
untuk efisiensi cost dan latency.

Usage:
    # Run untuk semua entries (default: 7 hari terakhir)
    python3 scripts/abstraction_layer2_v1.py

    # Run dengan batch size tertentu
    python3 scripts/abstraction_layer2_v1.py --batch-size 5 --since-days 30

    # Dry run (tidak save ke DB)
    python3 scripts/abstraction_layer2_v1.py --dry-run
"""
import os
import sys
import json
import time
import argparse
import psycopg
import requests
from typing import List, Dict, Optional
from datetime import datetime

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Config
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5433")),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("PG_PASSWORD") or os.getenv("POSTGRES_PASSWORD"),
    "dbname": os.getenv("POSTGRES_DB", "mcp_knowledge"),
}

GROQ_API_KEY = os.getenv("GROQ_API_KEY_BOT_WHATSAPP", "")
GROQ_MODEL = "llama-3.1-8b-instant"  # User-specified
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

# Source namespaces yang akan di-abstraksi
SOURCE_NAMESPACES = [
    "antigravity",
    "agent_conversations",
    "mcp_knowledge_base",
    "mcp-unified",
]


def call_groq_api(messages: List[Dict], max_tokens: int = 1024, temperature: float = 0.3) -> Optional[str]:
    """Call Groq API with messages. Returns content string or None on error."""
    if not GROQ_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": {"type": "json_object"},  # Force JSON output
    }

    try:
        response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"   ⚠️ Groq API error: {e}")
        return None


def get_unprocessed_entries(conn, batch_size: int, since_days: int) -> List[Dict]:
    """Ambil LTM entries yang belum ter-abstraksi.

    Note: knowledge_documents table sudah ada dengan schema:
    - id (text), content (text), embedding (vector 768), metadata (jsonb),
      namespace (text), created_at (timestamp)
    Source tracking dilakukan via metadata.source_key dan metadata.source_namespace.
    """
    with conn.cursor() as cur:
        # Ambil entries yang belum ada di knowledge_documents
        # Cek di metadata JSON apakah sudah ter-abstraksi
        cur.execute("""
            SELECT m.id, m.namespace, m.key, m.content, m.created_at
            FROM memories m
            WHERE m.namespace = ANY(%s)
              AND m.created_at > NOW() - (%s || ' days')::INTERVAL
              AND LENGTH(m.content) > 200
              AND NOT EXISTS (
                  SELECT 1 FROM knowledge_documents k
                  WHERE k.metadata->>'source_key' = m.key
                    AND k.metadata->>'source_namespace' = m.namespace
              )
            ORDER BY m.created_at DESC
            LIMIT %s;
    """, (SOURCE_NAMESPACES, str(since_days), batch_size))
        return [
            {"id": str(r[0]), "namespace": r[1], "key": r[2], "content": r[3], "created_at": r[4]}
            for r in cur.fetchall()
        ]


def build_prompt(entries: List[Dict]) -> List[Dict]:
    """Build prompt messages untuk Groq API."""
    entries_text = []
    for e in entries[:10]:  # Limit 10 entries per batch
        snippet = e["content"][:800] if len(e["content"]) > 800 else e["content"]
        entries_text.append(
            f"### Entry: {e['key']} (namespace: {e['namespace']})\n{snippet}\n"
        )

    system_prompt = """You are an expert knowledge engineer. Analyze the given memory entries
and extract structured knowledge. Respond ONLY with valid JSON in this exact structure:

{
  "patterns": [
    {"name": "short_name", "description": "what pattern this is", "evidence": "which entries"}
  ],
  "generalizations": [
    {"rule": "abstract rule statement", "context": "when this applies"}
  ],
  "entity_relationships": [
    {"entity1": "X", "relation": "uses/creates/depends_on", "entity2": "Y"}
  ],
  "action_templates": [
    {"template": "reusable action description", "applies_to": "context"}
  ],
  "summary": "one-line overall summary"
}

If no useful patterns, return empty arrays. Be concise."""

    user_prompt = f"""Analyze these {len(entries_text)} memory entries and extract knowledge:

{chr(10).join(entries_text)}

Return valid JSON only."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def save_abstractions(conn, entry: Dict, abstractions: Dict) -> int:
    """Save abstractions to knowledge_documents. Returns count saved.

    Note: Schema existing menggunakan kolom 'namespace' (bukan source_namespace)
    dan 'metadata' jsonb untuk track source. doc_type disimpan di metadata.
    """
    import uuid
    saved = 0
    with conn.cursor() as cur:
        for ab_type in ["patterns", "generalizations", "entity_relationships", "action_templates"]:
            items = abstractions.get(ab_type, [])
            if not items:
                continue
            for item in items:
                kd_id = f"abstraction_{uuid.uuid4().hex[:12]}"
                metadata = {
                    "doc_type": ab_type,
                    "source_key": entry["key"],
                    "source_namespace": entry["namespace"],
                    "extracted_at": datetime.utcnow().isoformat(),
                    "model": GROQ_MODEL,
                }
                cur.execute("""
                    INSERT INTO knowledge_documents
                      (id, content, namespace, metadata)
                    VALUES (%s, %s, %s, %s::jsonb)
            """, (
                    kd_id,
                    json.dumps(item, ensure_ascii=False),
                    f"abstraction/{entry['namespace']}",  # Group by source namespace
                    json.dumps(metadata)
                ))
                saved += 1
    conn.commit()
    return saved


def main():
    parser = argparse.ArgumentParser(description="QW #3: Abstraction Layer 2")
    parser.add_argument("--batch-size", type=int, default=10, help="Jumlah entries per batch")
    parser.add_argument("--since-days", type=int, default=7, help="Entry dalam N hari terakhir")
    parser.add_argument("--dry-run", action="store_true", help="Dry run, tidak save ke DB")
    args = parser.parse_args()

    print("=" * 70)
    print("🧠 QW #3: Abstraction Layer 2 - Knowledge Distillation")
    print("=" * 70)

    # Check API key
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY_BOT_WHATSAPP tidak ditemukan di .env")
        sys.exit(1)
    print(f"✅ Groq API key loaded (model: {GROQ_MODEL})")

    # Connect DB
    conn = psycopg.connect(**DB_CONFIG)

    # Get unprocessed entries
    print(f"\n📋 Mengambil entries (batch_size={args.batch_size}, since_days={args.since_days})...")
    entries = get_unprocessed_entries(conn, args.batch_size, args.since_days)
    print(f"   Ditemukan {len(entries)} entries untuk di-abstraksi")

    if not entries:
        print("\n✅ Tidak ada entries baru yang perlu di-abstraksi!")
        conn.close()
        return 0

    if args.dry_run:
        print("\n🔍 DRY RUN - entries yang akan di-process:")
        for e in entries[:5]:
            print(f"   - [{e['namespace']}] {e['key']} ({len(e['content'])} chars)")
        if len(entries) > 5:
            print(f"   ... dan {len(entries)-5} lainnya")
        conn.close()
        return 0

    # Process
    total_saved = 0
    total_time = 0
    success = 0
    error = 0

    for i, entry in enumerate(entries, 1):
        print(f"\n[{i}/{len(entries)}] Processing: {entry['key']} ({len(entry['content'])} chars)")
        start = time.time()

        # Build prompt & call API
        messages = build_prompt([entry])
        response_text = call_groq_api(messages, max_tokens=1024)

        if not response_text:
            error += 1
            continue

        # Parse JSON
        try:
            abstractions = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"   ⚠️ JSON parse error: {e}")
            print(f"   Response (first 200): {response_text[:200]}")
            error += 1
            continue

        # Save
        saved = save_abstractions(conn, entry, abstractions)
        
        # QW #3: Delete the original layer1 file to reclaim tokens
        if saved > 0:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM memories WHERE key = %s AND namespace = %s", (entry["key"], entry["namespace"]))
            conn.commit()
            print(f"   🗑️  Deleted original entry {entry['key']} to reclaim tokens")
            
        elapsed = time.time() - start
        total_saved += saved
        total_time += elapsed
        success += 1

        print(f"   ✅ {saved} abstractions saved ({elapsed:.1f}s)")
        if saved > 0:
            types_found = [k for k in ["patterns", "generalizations", "entity_relationships", "action_templates"]
                           if abstractions.get(k)]
            print(f"   Types: {types_found}")

    # Summary
    print("\n" + "=" * 70)
    print(f"📊 Summary:")
    print(f"   Entries processed: {success} success, {error} error")
    print(f"   Total abstractions saved: {total_saved}")
    print(f"   Avg time per entry: {total_time/max(success,1):.1f}s")
    print(f"   Model used: {GROQ_MODEL}")

    # Update memory status
    print(f"\n💾 Updating memory status...")
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO memories (namespace, key, content, metadata)
            VALUES (%s, %s, %s, %s::jsonb)
            ON CONFLICT (namespace, key) DO UPDATE SET
                content = EXCLUDED.content,
                metadata = EXCLUDED.metadata;
        """, (
            "mcp-unified",
            "abstraction_layer2_last_run",
            json.dumps({
                "timestamp": datetime.utcnow().isoformat(),
                "entries_processed": success,
                "abstractions_saved": total_saved,
                "model": GROQ_MODEL,
                "errors": error,
            }),
            json.dumps({"type": "abstraction_status", "status": "OK"}),
        ))
        conn.commit()
    print(f"   ✅ Status saved to LTM")

    conn.close()
    print(f"\n✅ DONE - QW #3 selesai!")
    return 0 if error == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
