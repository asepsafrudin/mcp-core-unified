-- TASK-116-A: Migration — Extend memories table for MemForge Native Integration
-- Dijalankan: 2026-10-01
-- Database: mcp_knowledge (PostgreSQL 16, host: localhost:5433)
-- Dieksekusi oleh: Antigravity (aseps:aseps, tanpa sudo)

-- 1. Extend tabel memories dengan kolom MemForge-style
ALTER TABLE memories ADD COLUMN IF NOT EXISTS importance FLOAT DEFAULT 0.5;
ALTER TABLE memories ADD COLUMN IF NOT EXISTS memory_type TEXT DEFAULT 'episodic';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS agent_id TEXT DEFAULT 'unknown';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- 2. Tambahkan indeks untuk retrieval yang efisien
CREATE INDEX IF NOT EXISTS memories_importance_idx ON memories (namespace, importance DESC);
CREATE INDEX IF NOT EXISTS memories_agent_idx ON memories (agent_id, namespace);
CREATE INDEX IF NOT EXISTS memories_type_idx ON memories (memory_type, namespace);

-- 3. Buat tabel audit log operasi agen memori
CREATE TABLE IF NOT EXISTS puu_agent_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action TEXT NOT NULL,          -- 'remember' | 'recall' | 'forget'
    namespace TEXT NOT NULL,
    agent_id TEXT,
    memory_id UUID,
    memory_key TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS audit_log_ns_idx ON puu_agent_audit_log (namespace, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_agent_idx ON puu_agent_audit_log (agent_id);

-- CATATAN:
-- Apache AGE tidak diinstall sebagai ekstensi (postgresql-16-age tersedia di paket
-- tapi tidak diaktifkan). Graf menggunakan tabel relasional native:
--   - graph_nodes (sudah ada, vector(768))
--   - graph_edges (sudah ada, CASCADE DELETE)
-- Ini adalah pendekatan yang disepakati dalam TASK-116 (graceful fallback).
