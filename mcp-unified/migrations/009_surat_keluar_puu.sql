-- ============================================================
-- Migration 009: Surat Keluar PUU Table
-- Tanggal: 2026-03-31
--
-- Tujuan:
-- 1. Menyimpan surat keluar dari PUU (NOMOR ND berakhiran /PUU)
-- 2. Format agenda menggunakan NOMOR ND asli dari sheet
-- ============================================================

CREATE TABLE IF NOT EXISTS surat_keluar_puu (
    id BIGSERIAL PRIMARY KEY,
    unique_id TEXT NOT NULL UNIQUE,
    tanggal_surat DATE,
    nomor_nd TEXT NOT NULL,
    dari TEXT,
    hal TEXT,
    tujuan TEXT,                   -- Penerima surat keluar
    filter_reason TEXT,            -- Alasan filter (bukan surat masuk)
    raw_pool_id BIGINT REFERENCES korespondensi_raw_pool(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_surat_keluar_puu_nomor_nd ON surat_keluar_puu(nomor_nd);
CREATE INDEX IF NOT EXISTS idx_surat_keluar_puu_tanggal ON surat_keluar_puu(tanggal_surat DESC);
CREATE INDEX IF NOT EXISTS idx_surat_keluar_puu_unique ON surat_keluar_puu(unique_id);

-- Komentar
COMMENT ON TABLE surat_keluar_puu IS 'Surat keluar dari unit PUU (NOMOR ND berakhiran /PUU)';