-- Migration 010: Create Graph Memory Tables (Nodes & Edges) for Hybrid GraphRAG
-- Supports pgvector 768-dimension embeddings for entities and recursive CTE graph traversal.

CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Table graph_nodes (Knowledge Entities)
CREATE TABLE IF NOT EXISTS graph_nodes (
    id VARCHAR(128) PRIMARY KEY,           -- e.g., 'surat:000.2.2.4/038/PUU', 'pegawai:198303062008122001'
    namespace VARCHAR(64) NOT NULL DEFAULT 'default',
    entity_type VARCHAR(32) NOT NULL DEFAULT 'concept',  -- 'surat', 'pegawai', 'instansi', 'regulasi', 'lokasi', 'topik'
    name VARCHAR(255) NOT NULL,
    summary TEXT,
    metadata JSONB DEFAULT '{}',
    embedding vector(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_graph_nodes_ns ON graph_nodes(namespace, entity_type);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_name ON graph_nodes(name);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_embed ON graph_nodes USING hnsw (embedding vector_cosine_ops);

-- 2. Table graph_edges (Directed Relational Edges)
CREATE TABLE IF NOT EXISTS graph_edges (
    id BIGSERIAL PRIMARY KEY,
    namespace VARCHAR(64) NOT NULL DEFAULT 'default',
    source_id VARCHAR(128) NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    target_id VARCHAR(128) NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    relation VARCHAR(64) NOT NULL,         -- 'ditandatangani_oleh', 'merujuk_ke', 'atasan_langsung', 'bertugas_ke'
    weight FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_graph_edge UNIQUE (namespace, source_id, target_id, relation)
);

CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_id, relation);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_id, relation);
CREATE INDEX IF NOT EXISTS idx_graph_edges_ns ON graph_edges(namespace);
