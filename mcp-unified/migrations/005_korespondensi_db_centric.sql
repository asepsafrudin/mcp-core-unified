-- ============================================================
-- Migration 005: Database-Centric Korespondensi Schema
-- Menggantikan ketergantungan pada sheet 1BtKu...
-- Source: 6 spreadsheet unit (SEKRETARIAT, PEIPD, SUPD I-IV)
-- ============================================================

-- 1. RAW INBOX POOL (setara POOLING_DATA di sheet)
CREATE TABLE IF NOT EXISTS korespondensi_raw_pool (
    id                  BIGSERIAL PRIMARY KEY,
    unique_id           TEXT NOT NULL,          -- nomor_nd + tanggal (stable key)
    no_agenda           TEXT,
    tanggal             DATE,
    nomor_nd            TEXT NOT NULL,
    dari                TEXT,
    hal                 TEXT,
    posisi              TEXT,
    disposisi           TEXT,
    source_spreadsheet_id TEXT NOT NULL,         -- ID spreadsheet sumber
    source_sheet_name   TEXT NOT NULL,           -- Nama tab (SEKRETARIAT, PEIPD, dst)
    source_row_num      INTEGER,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (unique_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_pool_tanggal
    ON korespondensi_raw_pool (tanggal DESC);
CREATE INDEX IF NOT EXISTS idx_raw_pool_dari
    ON korespondensi_raw_pool (dari);
CREATE INDEX IF NOT EXISTS idx_raw_pool_posisi_gin
    ON korespondensi_raw_pool USING gin (to_tsvector('simple', COALESCE(posisi, '')));


-- 2. SURAT MASUK PUU (setara sheet "Surat Masuk PUU")
--    Hasil filter dari raw_pool: is_puu = true
CREATE TABLE IF NOT EXISTS surat_masuk_puu (
    id                  BIGSERIAL PRIMARY KEY,
    unique_id           TEXT NOT NULL UNIQUE,
    tanggal_surat       DATE,
    nomor_nd            TEXT NOT NULL,
    dari                TEXT,
    hal                 TEXT,
    no_agenda_dispo     TEXT,               -- hasil regex dari kolom disposisi
    is_puu              BOOLEAN NOT NULL DEFAULT TRUE,
    filter_reason       TEXT,               -- alasan lolos filter
    raw_pool_id         BIGINT REFERENCES korespondensi_raw_pool(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_surat_masuk_puu_tanggal
    ON surat_masuk_puu (tanggal_surat DESC);
CREATE INDEX IF NOT EXISTS idx_surat_masuk_puu_hal_gin
    ON surat_masuk_puu USING gin (to_tsvector('simple', COALESCE(hal, '')));


-- 3. LEMBAR DISPOSISI (setara sheet "CETAK_LEMBAR_DISPOSISI")
--    Input manual: DIREKTORAT + TGL DITERIMA
CREATE TABLE IF NOT EXISTS lembar_disposisi (
    id                  BIGSERIAL PRIMARY KEY,
    surat_id            BIGINT NOT NULL REFERENCES surat_masuk_puu(id) ON DELETE CASCADE,
    unique_id           TEXT NOT NULL UNIQUE,
    agenda_puu          TEXT,               -- nomor urut disposisi (mis. 001-I)
    direktorat          TEXT,               -- input manual
    tgl_diterima        DATE,               -- input manual
    status              TEXT DEFAULT 'belum_proses',
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lembar_disposisi_tgl_diterima
    ON lembar_disposisi (tgl_diterima DESC);


-- 4. DOKUMEN DISPOSISI (hasil mail merge, setara file di folder Drive)
CREATE TABLE IF NOT EXISTS disposisi_documents (
    id                  BIGSERIAL PRIMARY KEY,
    lembar_disposisi_id BIGINT NOT NULL REFERENCES lembar_disposisi(id) ON DELETE CASCADE,
    agenda_puu          TEXT NOT NULL,
    doc_id              TEXT,               -- Google Doc ID hasil copy template
    doc_url             TEXT,               -- URL langsung ke file
    file_name           TEXT,               -- "Disposisi - 001-I"
    folder_id           TEXT NOT NULL DEFAULT '1s1WyweDstV0vYgP1SIfQk4rWwDGO0OYw',
    template_id         TEXT NOT NULL DEFAULT '1ixgD-8ISGkyaD018sNfEPznCFvxCOFC5xbGE5GfQVoQ',
    generated_at        TIMESTAMPTZ,
    generation_status   TEXT DEFAULT 'pending' CHECK (generation_status IN ('pending','success','failed','skipped')),
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_disposisi_documents_lembar_id
    ON disposisi_documents (lembar_disposisi_id);
CREATE INDEX IF NOT EXISTS idx_disposisi_documents_status
    ON disposisi_documents (generation_status);


-- 5. KONFIGURASI SUMBER DATA (pengganti hardcode di script)
CREATE TABLE IF NOT EXISTS korespondensi_source_config (
    id                  SERIAL PRIMARY KEY,
    unit_name           TEXT NOT NULL UNIQUE,
    spreadsheet_id      TEXT NOT NULL,
    sheet_name          TEXT NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    last_synced_at      TIMESTAMPTZ,
    last_row_count      INTEGER DEFAULT 0,
    notes               TEXT
);

-- Isi konfigurasi sumber dari script poolingDataOptimasi
INSERT INTO korespondensi_source_config (unit_name, spreadsheet_id, sheet_name) VALUES
    ('SEKRETARIAT', '1tSqu5XljsU9a-ZCS_yk0dswWQgsHEWS9IhF32i4Ll9Y', 'SEKRETARIAT'),
    ('PEIPD',       '10ampyOAQ09JvsZfNfZHCOkbyhi0twWxUWcurgbUR9SI',  'PEIPD'),
    ('SUPD I',      '1rQks2NZbxvAptIU5DTRniNHrbKLZKrb9Y0m4LVdmsh4',  'SUPD I'),
    ('SUPD II',     '1sgWmhrgfnO78ifBVQ3oV6_JzrxhOv5rZ6qnlgL0xPQI',  'SUPD II'),
    ('SUPD III',    '1leTdyDS2QKTkW3D1wsleRsHHFtqlTJTFB-VfYEXte3M',  'SUPD III'),
    ('SUPD IV',     '1XIkaMmobZEWLSuv2YBHepCbyztdZ6muBZ_7sdg-B7TY',  'SUPD IV')
ON CONFLICT (unit_name) DO UPDATE SET
    spreadsheet_id = EXCLUDED.spreadsheet_id,
    sheet_name     = EXCLUDED.sheet_name;
