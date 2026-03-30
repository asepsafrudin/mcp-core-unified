-- ============================================================
-- Migration 006: Fix Schema Gaps & Backlog Items
-- Tanggal: 2026-03-30
--
-- Perbaikan:
-- 1. disposisi_documents: tambah sync_status, synced_at, local_file_path
--    (dibutuhkan generate_disposisi_docs.py & sync_disposisi_to_gdrive.py)
-- 2. disposisi_documents: tambah UNIQUE (lembar_disposisi_id)
--    (dibutuhkan ON CONFLICT clause)
-- 3. surat_masuk_puu: tambah dari_full (caching nama lengkap DARI)
-- 4. korespondensi_source_config: tambah skip_sheets (backlog ETL)
-- 5. DARI lookup: UN → "Unit/Bagian Lain" (backlog pending)
-- ============================================================

-- 1. Kolom yang hilang di disposisi_documents
ALTER TABLE disposisi_documents
    ADD COLUMN IF NOT EXISTS sync_status    TEXT    NOT NULL DEFAULT 'pending'
        CHECK (sync_status IN ('pending','synced','error')),
    ADD COLUMN IF NOT EXISTS synced_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS local_file_path TEXT;

CREATE INDEX IF NOT EXISTS idx_disposisi_documents_sync_status
    ON disposisi_documents (sync_status);

-- 2. UNIQUE constraint pada lembar_disposisi_id
--    (diperlukan untuk ON CONFLICT (lembar_disposisi_id) di generate_disposisi_docs.py)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'disposisi_documents_lembar_disposisi_id_key'
          AND conrelid = 'disposisi_documents'::regclass
    ) THEN
        ALTER TABLE disposisi_documents
            ADD CONSTRAINT disposisi_documents_lembar_disposisi_id_key
            UNIQUE (lembar_disposisi_id);
    END IF;
END$$;


-- 3. Kolom dari_full di surat_masuk_puu
--    Diisi ETL dengan nama lengkap dari kode DARI (Bagian Umum, Subdit Wilayah I, dst)
ALTER TABLE surat_masuk_puu
    ADD COLUMN IF NOT EXISTS dari_full TEXT;

CREATE INDEX IF NOT EXISTS idx_surat_masuk_puu_dari_full
    ON surat_masuk_puu (dari_full);


-- 4. Kolom skip_sheets di korespondensi_source_config
--    JSON array nama tab yang diabaikan saat ETL
--    Contoh: '["surat keluar PUU"]'
ALTER TABLE korespondensi_source_config
    ADD COLUMN IF NOT EXISTS skip_sheets JSONB NOT NULL DEFAULT '[]'::jsonb;

-- SEKRETARIAT: abaikan tab "surat keluar PUU" (surat outbound PUU — bukan surat masuk)
UPDATE korespondensi_source_config
SET skip_sheets = '["surat keluar PUU"]'::jsonb
WHERE unit_name = 'SEKRETARIAT';


-- 5. Tabel referensi DARI_LOOKUP (opsional, untuk konsistensi multi-script)
CREATE TABLE IF NOT EXISTS dari_lookup (
    id          SERIAL PRIMARY KEY,
    kode_raw    TEXT NOT NULL UNIQUE,   -- kode apa adanya di spreadsheet (uppercase, normalized)
    nama_lengkap TEXT NOT NULL,
    notes       TEXT
);

INSERT INTO dari_lookup (kode_raw, nama_lengkap) VALUES
    ('BU',         'Bagian Umum'),
    ('UM',         'Bagian Umum'),
    ('TU',         'Tata Usaha'),
    ('TU SUPD II', 'Tata Usaha SUPD II'),
    ('PRC',        'Bagian Perencanaan'),
    ('PUU',        'Substansi Perundang-Undangan'),
    ('KEU',        'Bagian Keuangan'),
    ('SD I',       'Subdit Wilayah I'),
    ('SD.I',       'Subdit Wilayah I'),
    ('SD 1',       'Subdit Wilayah I'),
    ('SD II',      'Subdit Wilayah II'),
    ('SD.II',      'Subdit Wilayah II'),
    ('SD III',     'Subdit Wilayah III'),
    ('SD.III',     'Subdit Wilayah III'),
    ('SD IV',      'Subdit Wilayah IV'),
    ('SD.IV',      'Subdit Wilayah IV'),
    ('SD V',       'Subdit Wilayah V'),
    ('SD.V',       'Subdit Wilayah V'),
    ('SD VI',      'Subdit Wilayah VI'),
    ('SD.VI',      'Subdit Wilayah VI'),
    ('SD PMIPD',   'Subdit PMIPD'),
    ('SD.PMIPD',   'Subdit PMIPD'),
    ('SD PIMPD',   'Subdit PMIPD'),
    ('SD',         'Subdit'),
    ('PEIPD',      'Direktorat PEIPD'),
    ('PMIPD',      'Subdit PMIPD'),
    ('SUPD I',     'Direktorat SUPD I'),
    ('SUPD II',    'Direktorat SUPD II'),
    ('SUPD III',   'Direktorat SUPD III'),
    ('SUPD IV',    'Direktorat SUPD IV'),
    ('PPK',        'Pejabat Pembuat Komitmen'),
    ('BANGDA',     'Ditjen Bina Pembangunan Daerah'),
    ('UN',         'Unit Pengelola (Belum Terdefinisi)')   -- backlog: user akan mengkonfirmasi
ON CONFLICT (kode_raw) DO UPDATE SET
    nama_lengkap = EXCLUDED.nama_lengkap;
