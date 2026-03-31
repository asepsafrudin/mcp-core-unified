-- ============================================================
-- Migration 008: Disposisi Feedback Table
-- Tanggal: 2026-03-31
--
-- Tujuan:
-- 1. Menyimpan feedback dari PIC (Person In Charge) setelah
--    mailmerge disposisi didistribusikan
-- 2. Mendukung input via database (manual) dan Telegram bot
-- 3. Tracking status dan audit trail
-- ============================================================

-- Tabel untuk menyimpan feedback disposisi
CREATE TABLE IF NOT EXISTS disposisi_feedback (
    id BIGSERIAL PRIMARY KEY,
    lembar_disposisi_id BIGINT NOT NULL REFERENCES lembar_disposisi(id),
    agenda_puu TEXT NOT NULL,
    
    -- Data PIC (Person In Charge)
    pic_nama TEXT NOT NULL,                    -- Nama PIC
    pic_telegram_id TEXT,                      -- Telegram user ID (jika input via bot)
    
    -- Tanggal
    tanggal_autentifikasi DATE NOT NULL,       -- Tanggal autentifikasi lembar dispo
    
    -- Catatan & Status
    catatan TEXT,                              -- Catatan dari PIC
    status TEXT DEFAULT 'baru'                 -- baru, diproses, selesai, ditolak
        CHECK (status IN ('baru', 'diproses', 'selesai', 'ditolak')),
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT DEFAULT 'system',          -- 'system', 'telegram', 'manual'
    
    -- Constraint
    CONSTRAINT uq_feedback_agenda UNIQUE (lembar_disposisi_id, pic_nama, tanggal_autentifikasi)
);

-- Index untuk pencarian cepat
CREATE INDEX IF NOT EXISTS idx_feedback_agenda ON disposisi_feedback(agenda_puu);
CREATE INDEX IF NOT EXISTS idx_feedback_lembar ON disposisi_feedback(lembar_disposisi_id);
CREATE INDEX IF NOT EXISTS idx_feedback_pic ON disposisi_feedback(pic_nama);
CREATE INDEX IF NOT EXISTS idx_feedback_status ON disposisi_feedback(status);
CREATE INDEX IF NOT EXISTS idx_feedback_tanggal ON disposisi_feedback(tanggal_autentifikasi DESC);

-- Komentar untuk dokumentasi
COMMENT ON TABLE disposisi_feedback IS 'Feedback dari PIC setelah mailmerge disposisi didistribusikan';
COMMENT ON COLUMN disposisi_feedback.pic_nama IS 'Nama Person In Charge';
COMMENT ON COLUMN disposisi_feedback.tanggal_autentifikasi IS 'Tanggal autentifikasi lembar disposisi';
COMMENT ON COLUMN disposisi_feedback.catatan IS 'Catatan dari PIC';
COMMENT ON COLUMN disposisi_feedback.status IS 'Status: baru, diproses, selesai, ditolak';
COMMENT ON COLUMN disposisi_feedback.created_by IS 'Sumber input: system, telegram, manual';