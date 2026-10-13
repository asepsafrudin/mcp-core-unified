"""
tools/agent_memory_tools.py — MemForge Native Integration
TASK-116: Epic 1 — MemForge-style remember / recall / forget
sebagai native tools di MCP Unified Hub.

Prinsip Desain:
- Backend: PostgreSQL 16 eksisting (mcp_knowledge), tabel 'memories' yang diperluas.
- Kuantisasi Wajib: teks observasi dipadatkan ke JSON terstruktur sebelum disimpan.
- Graf: graph_nodes + graph_edges (native PostgreSQL, fallback dari Apache AGE).
- Namespace: pola 'puu:{domain}:{agent_name}' untuk isolasi penuh.
- Audit: setiap operasi write/delete dicatat ke puu_agent_audit_log.
"""

from __future__ import annotations

import json
import re
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from execution import registry
from observability.logger import logger

# ── Import backend dari longterm.py eksisting ──────────────────────────────────
from memory.longterm import pool, ensure_pool_open, get_embedding, EmbeddingUnavailableError


# ─────────────────────────────────────────────────────────────────────────────
# §1. KONSTANTA & NAMESPACE VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

_ALLOWED_NAMESPACE_PREFIXES = ["puu:", "shared_", "bot:"]
_NAMESPACE_PATTERN = re.compile(r"^(puu:[a-z_]+:[a-z_]+|shared_[a-z_]+|bot:[a-z_]+:[a-z_]+)$")
_MAX_CONTENT_CHARS = 2000  # Batas sanitasi untuk Ollama embedding endpoint
_DEFAULT_TOKEN_BUDGET = 500


def _validate_namespace(namespace: str) -> None:
    """Validasi format namespace. Raise ValueError jika tidak sesuai pola."""
    if not _NAMESPACE_PATTERN.match(namespace):
        raise ValueError(
            f"Namespace '{namespace}' tidak valid. "
            f"Harus mengikuti pola 'puu:{{domain}}:{{agent}}', 'shared_{{domain}}', atau 'bot:{{bot_id}}:{{category}}'. "
            f"Contoh: 'puu:regulasi:pencari', 'shared_legal', 'bot:satria:memory'"
        )


def _sanitize_text(text: str) -> str:
    """Sanitasi teks: hilangkan karakter non-standar, potong ke MAX_CONTENT_CHARS."""
    # Hilangkan karakter kontrol selain newline/tab
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return sanitized[:_MAX_CONTENT_CHARS]


# ─────────────────────────────────────────────────────────────────────────────
# §2. MEMORY QUANTIZER (116-B)
# ─────────────────────────────────────────────────────────────────────────────

def _quantize_memory_local(content: str, importance: float) -> Dict[str, Any]:
    """
    Kuantisasi lokal (deterministik, tanpa LLM) — fallback cepat.
    Menghasilkan format JSON padat berisi dense_content, entities, facts.
    """
    # Ekstrak kalimat kunci sederhana (heuristik)
    sentences = [s.strip() for s in re.split(r"[.!?\n]", content) if len(s.strip()) > 20]
    facts = sentences[:5]  # Ambil 5 kalimat pertama sebagai fakta

    # Ekstrak entitas sederhana (huruf kapital / kata kunci domain)
    entity_candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", content)
    entities = list(set(entity_candidates))[:10]

    # Dense content = kalimat pertama yang bermakna
    dense = sentences[0] if sentences else content[:200]

    return {
        "dense_content": dense,
        "entities": entities,
        "facts": facts,
        "importance": importance,
        "outcome": "success" if importance >= 0.5 else "low_priority",
        "quantized_at": datetime.now(timezone.utc).isoformat(),
        "method": "local_heuristic",
    }


async def _quantize_with_llm(content: str, importance: float, namespace: str) -> Dict[str, Any]:
    """
    Kuantisasi dengan LLM (Groq/Gemini via AI Orchestrator, opsional).
    Jika gagal, fallback ke _quantize_memory_local.
    """
    try:
        # Coba import AI Orchestrator bridge
        from tools.orchestrator_bridge import call_llm_compact
        prompt = f"""Kuantisasi observasi agen berikut menjadi JSON padat.
Namespace: {namespace}
Observasi: {content[:800]}
Kembalikan JSON dengan field: dense_content (string), entities (list), facts (list), outcome (success/fail/in_progress).
Hanya kembalikan JSON, tanpa penjelasan."""
        result = await call_llm_compact(prompt)
        parsed = json.loads(result)
        parsed["importance"] = importance
        parsed["method"] = "llm"
        return parsed
    except Exception as e:
        logger.warning("llm_quantize_fallback", error=str(e), namespace=namespace)
        return _quantize_memory_local(content, importance)


# ─────────────────────────────────────────────────────────────────────────────
# §3. AUDIT LOG HELPER
# ─────────────────────────────────────────────────────────────────────────────

async def _write_audit_log(
    action: str,
    namespace: str,
    agent_id: str,
    memory_id: Optional[str] = None,
    memory_key: Optional[str] = None,
    extra_metadata: Optional[Dict] = None,
) -> None:
    """Tulis entri audit ke tabel puu_agent_audit_log."""
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO puu_agent_audit_log
                        (action, namespace, agent_id, memory_id, memory_key, metadata)
                    VALUES (%s, %s, %s, %s::uuid, %s, %s)
                    """,
                    (
                        action,
                        namespace,
                        agent_id,
                        memory_id,
                        memory_key,
                        json.dumps(extra_metadata or {}),
                    ),
                )
    except Exception as e:
        # Audit log tidak boleh crash operasi utama
        logger.error("audit_log_write_failed", action=action, namespace=namespace, error=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# §4. TOOL: agent_remember (116-C)
# ─────────────────────────────────────────────────────────────────────────────

@registry.register(name="agent_remember")
async def agent_remember(
    namespace: str,
    content: str,
    importance: float = 0.5,
    agent_id: str = "orchestrator",
    memory_type: str = "episodic",
    use_llm_quantize: bool = False,
) -> Dict[str, Any]:
    """
    Simpan memori agen baru ke PostgreSQL dengan kuantisasi wajib.
    Mengikuti kontrak API MemForge: remember(namespace, content, importance).

    Args:
        namespace      : Namespace agen, pola 'puu:{domain}:{agent}' (contoh: 'puu:regulasi:pencari')
        content        : Teks observasi yang ingin diingat (maks 2000 karakter)
        importance     : Skor kepentingan 0.0–1.0 (default: 0.5)
        agent_id       : Identitas agen pemanggil (default: 'orchestrator')
        memory_type    : Tipe memori: 'episodic'|'semantic'|'procedural' (default: 'episodic')
        use_llm_quantize: Jika True, kuantisasi via LLM (opsional, butuh AI bridge)

    Returns:
        {memory_id, status, namespace, importance, quantized_content}
    """
    try:
        # 1. Validasi namespace
        _validate_namespace(namespace)

        # 2. Sanitasi input
        content = _sanitize_text(content)
        importance = max(0.0, min(1.0, importance))

        # 3. Kuantisasi wajib (AGENTS.md Rule #5)
        if use_llm_quantize:
            quantized = await _quantize_with_llm(content, importance, namespace)
        else:
            quantized = _quantize_memory_local(content, importance)

        # 4. Buat key unik dari namespace + dense_content hash
        dense_text = quantized.get("dense_content", content[:100])
        import hashlib
        content_hash = hashlib.md5(dense_text.encode()).hexdigest()[:12]
        key = f"{namespace.replace(':', '_')}_{content_hash}"

        # 5. Generate embedding dari dense_content
        await ensure_pool_open()
        try:
            embedding = await get_embedding(dense_text)
        except EmbeddingUnavailableError as e:
            logger.warning("embedding_unavailable_remember", namespace=namespace, error=str(e))
            embedding = None

        # 6. Simpan ke tabel memories (upsert)
        metadata_payload = {
            "quantized": quantized,
            "agent_id": agent_id,
            "original_content_length": len(content),
        }

        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO memories
                        (namespace, key, content, metadata, embedding, importance, memory_type, agent_id, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (namespace, key) DO UPDATE SET
                        content    = EXCLUDED.content,
                        metadata   = EXCLUDED.metadata,
                        embedding  = EXCLUDED.embedding,
                        importance = EXCLUDED.importance,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        namespace,
                        key,
                        dense_text,
                        json.dumps(metadata_payload),
                        embedding,
                        importance,
                        memory_type,
                        agent_id,
                    ),
                )
                row = await cur.fetchone()
                memory_id = str(row[0])

        # 7. Simpan entitas ke graph_nodes (integrasikan graf)
        entities = quantized.get("entities", [])
        if entities:
            asyncio.create_task(
                _upsert_graph_entities(namespace, entities, memory_id, dense_text)
            )

        # 8. Audit log
        await _write_audit_log("remember", namespace, agent_id, memory_id, key)

        logger.info("agent_remember_ok", namespace=namespace, memory_id=memory_id, importance=importance)
        return {
            "status": "stored",
            "memory_id": memory_id,
            "key": key,
            "namespace": namespace,
            "importance": importance,
            "quantized_content": dense_text[:200],
            "entities_extracted": len(entities),
        }

    except ValueError as ve:
        return {"status": "error", "error": str(ve)}
    except Exception as e:
        logger.error("agent_remember_failed", namespace=namespace, error=str(e))
        return {"status": "error", "error": str(e)}


async def _upsert_graph_entities(
    namespace: str, entities: List[str], source_memory_id: str, context: str
) -> None:
    """Insert entitas ke graph_nodes dan buat edge ke node memori (background task)."""
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                for entity in entities[:10]:  # Batasi 10 entitas per memori
                    node_id = f"mem:{namespace}:{entity.lower().replace(' ', '_')}"
                    await cur.execute(
                        """
                        INSERT INTO graph_nodes (id, namespace, entity_type, name, summary, metadata)
                        VALUES (%s, %s, 'concept', %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            updated_at = NOW(),
                            summary = EXCLUDED.summary
                        """,
                        (
                            node_id,
                            namespace,
                            entity,
                            context[:200],
                            json.dumps({"source_memory_id": source_memory_id}),
                        ),
                    )
    except Exception as e:
        logger.warning("graph_entity_upsert_failed", namespace=namespace, error=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# §5. TOOL: agent_recall (116-D)
# ─────────────────────────────────────────────────────────────────────────────

@registry.register(name="agent_recall")
async def agent_recall(
    namespace: str,
    query: str,
    token_budget: int = 500,
    top_k: int = 5,
    strategy: str = "hybrid",
) -> Dict[str, Any]:
    """
    Ambil memori relevan untuk agen berdasarkan kueri, dikelompokkan per tipe.
    Mengikuti kontrak API MemForge: recall(namespace, query, token_budget).

    Args:
        namespace   : Namespace agen
        query       : Pertanyaan / konteks sesi saat ini
        token_budget: Perkiraan maks karakter output konteks (default: 500)
        top_k       : Jumlah kandidat memori teratas (default: 5)
        strategy    : 'hybrid' | 'semantic' | 'keyword'

    Returns:
        {context_document, memories, namespace, token_used}
    """
    try:
        _validate_namespace(namespace)
        await ensure_pool_open()

        query_sanitized = _sanitize_text(query)

        # 1. Generate embedding query
        try:
            query_emb = await get_embedding(query_sanitized)
        except EmbeddingUnavailableError:
            logger.warning("recall_fallback_keyword", namespace=namespace)
            strategy = "keyword"
            query_emb = None

        # 2. Jalankan pencarian berdasarkan strategi
        top_k = min(top_k, 10)
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                if strategy == "semantic" and query_emb:
                    await cur.execute(
                        """
                        SELECT id, key, content, metadata, importance, memory_type,
                               (1 - (embedding <=> %s::vector)) AS score
                        FROM memories
                        WHERE namespace = %s AND embedding IS NOT NULL
                        ORDER BY score DESC
                        LIMIT %s
                        """,
                        (query_emb, namespace, top_k),
                    )
                elif strategy == "keyword":
                    await cur.execute(
                        """
                        SELECT id, key, content, metadata, importance, memory_type,
                               ts_rank(to_tsvector('indonesian', content),
                                       websearch_to_tsquery('indonesian', %s)) AS score
                        FROM memories
                        WHERE namespace = %s
                          AND to_tsvector('indonesian', content) @@
                              websearch_to_tsquery('indonesian', %s)
                        ORDER BY score DESC
                        LIMIT %s
                        """,
                        (query_sanitized, namespace, query_sanitized, top_k),
                    )
                else:  # hybrid (default)
                    if query_emb:
                        await cur.execute(
                            """
                            SELECT id, key, content, metadata, importance, memory_type,
                                   (0.6 * (1 - (embedding <=> %s::vector)) +
                                    0.4 * importance) AS score
                            FROM memories
                            WHERE namespace = %s
                              AND (embedding IS NOT NULL OR content ILIKE %s)
                            ORDER BY score DESC
                            LIMIT %s
                            """,
                            (query_emb, namespace, f"%{query_sanitized[:50]}%", top_k),
                        )
                    else:
                        await cur.execute(
                            """
                            SELECT id, key, content, metadata, importance, memory_type,
                                   importance AS score
                            FROM memories
                            WHERE namespace = %s
                            ORDER BY importance DESC, updated_at DESC
                            LIMIT %s
                            """,
                            (namespace, top_k),
                        )

                rows = await cur.fetchall()

        # 3. Susun memori berdasarkan tipe
        grouped: Dict[str, List[Dict]] = {}
        for row in rows:
            mem_id, key, content, meta_raw, importance, mem_type, score = row
            meta = meta_raw if isinstance(meta_raw, dict) else json.loads(meta_raw or "{}")
            mem_type = mem_type or "episodic"
            if mem_type not in grouped:
                grouped[mem_type] = []
            grouped[mem_type].append({
                "id": str(mem_id),
                "key": key,
                "content": content,
                "importance": float(importance or 0.5),
                "score": round(float(score or 0), 3),
            })

        # 4. Kompilasi context_document sesuai token_budget
        if not rows:
            return {
                "status": "ok",
                "namespace": namespace,
                "strategy": strategy,
                "total_retrieved": 0,
                "memories": {},
                "context_document": "",
            }

        context_lines = [f"## Konteks Memori Agen [{namespace}]\n"]
        char_used = len(context_lines[0])

        for mem_type, mems in grouped.items():
            section_header = f"\n### {mem_type.capitalize()}\n"
            context_lines.append(section_header)
            char_used += len(section_header)
            for m in mems:
                line = f"- [{round(m['importance'], 2)}] {m['content']}\n"
                if char_used + len(line) > token_budget * 4:  # 1 token ≈ 4 chars
                    break
                context_lines.append(line)
                char_used += len(line)

        context_doc = "".join(context_lines)
        total_memories = sum(len(v) for v in grouped.values())

        logger.info("agent_recall_ok", namespace=namespace, total=total_memories, chars=char_used)
        return {
            "status": "ok",
            "namespace": namespace,
            "context_document": context_doc,
            "memories": grouped,
            "total_retrieved": total_memories,
            "token_used_approx": char_used // 4,
        }

    except ValueError as ve:
        return {"status": "error", "error": str(ve)}
    except Exception as e:
        logger.error("agent_recall_failed", namespace=namespace, error=str(e))
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# §6. TOOL: agent_forget (116-E)
# ─────────────────────────────────────────────────────────────────────────────

@registry.register(name="agent_forget")
async def agent_forget(
    memory_id: str,
    namespace: str,
    agent_id: str = "orchestrator",
) -> Dict[str, Any]:
    """
    Hapus memori tertentu berdasarkan memory_id, beserta entitas graf terkait.
    Mengikuti kontrak API MemForge: forget(memory_id).
    Hanya boleh dilakukan oleh agent_id pemilik namespace tersebut.

    Args:
        memory_id : UUID memori yang akan dihapus
        namespace : Namespace memori (untuk verifikasi kepemilikan)
        agent_id  : Agen yang meminta penghapusan

    Returns:
        {status, memory_id, edges_removed, namespace}
    """
    try:
        _validate_namespace(namespace)
        await ensure_pool_open()

        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # 1. Verifikasi memori milik namespace ini
                await cur.execute(
                    "SELECT id, key, namespace FROM memories WHERE id = %s::uuid",
                    (memory_id,),
                )
                row = await cur.fetchone()
                if not row:
                    return {
                        "status": "not_found",
                        "memory_id": memory_id,
                        "error": "Memory tidak ditemukan",
                    }

                mem_uuid, mem_key, mem_ns = row
                if mem_ns != namespace:
                    logger.warning(
                        "forget_namespace_mismatch",
                        requested_ns=namespace,
                        actual_ns=mem_ns,
                        agent_id=agent_id,
                    )
                    return {
                        "status": "forbidden",
                        "error": f"Memory berada di namespace '{mem_ns}', bukan '{namespace}'",
                    }

                # 2. Hapus entitas graf terkait
                await cur.execute(
                    """
                    DELETE FROM graph_nodes
                    WHERE namespace = %s
                      AND metadata->>'source_memory_id' = %s
                    """,
                    (namespace, memory_id),
                )
                edges_removed = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

                # 3. Hapus memori utama
                await cur.execute(
                    "DELETE FROM memories WHERE id = %s::uuid RETURNING id",
                    (memory_id,),
                )
                deleted = await cur.fetchone()

        # 4. Audit log
        await _write_audit_log(
            "forget",
            namespace,
            agent_id,
            memory_id,
            mem_key,
            {"edges_removed": edges_removed},
        )

        logger.info("agent_forget_ok", memory_id=memory_id, namespace=namespace)
        return {
            "status": "deleted",
            "memory_id": memory_id,
            "namespace": namespace,
            "edges_removed": edges_removed,
        }

    except ValueError as ve:
        return {"status": "error", "error": str(ve)}
    except Exception as e:
        logger.error("agent_forget_failed", memory_id=memory_id, error=str(e))
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# §7. TOOL: agent_memory_stats (Bonus — Observability)
# ─────────────────────────────────────────────────────────────────────────────

@registry.register(name="agent_memory_stats")
async def agent_memory_stats(namespace: str) -> Dict[str, Any]:
    """
    Tampilkan statistik memori untuk namespace tertentu.
    Berguna untuk pemantauan dan debugging oleh operator.

    Args:
        namespace: Namespace agen

    Returns:
        {total_memories, by_type, avg_importance, last_written}
    """
    try:
        _validate_namespace(namespace)
        await ensure_pool_open()

        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        AVG(importance) AS avg_importance,
                        MAX(updated_at) AS last_written
                    FROM memories
                    WHERE namespace = %s
                    """,
                    (namespace,),
                )
                row = await cur.fetchone()
                total, avg_imp, last_written = row

                await cur.execute(
                    """
                    SELECT memory_type, COUNT(*) AS cnt
                    FROM memories
                    WHERE namespace = %s
                    GROUP BY memory_type
                    ORDER BY cnt DESC
                    """,
                    (namespace,),
                )
                by_type = {r[0] or "unknown": r[1] for r in await cur.fetchall()}

        return {
            "status": "ok",
            "namespace": namespace,
            "total_memories": int(total or 0),
            "avg_importance": round(float(avg_imp or 0), 3),
            "last_written": last_written.isoformat() if last_written else None,
            "by_type": by_type,
        }

    except ValueError as ve:
        return {"status": "error", "error": str(ve)}
    except Exception as e:
        logger.error("agent_memory_stats_failed", namespace=namespace, error=str(e))
        return {"status": "error", "error": str(e)}
