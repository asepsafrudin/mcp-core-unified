-- ============================================================
-- Migration 007: Add tanggal_diterima_puu & dari_full to surat_masuk_puu
-- Tanggal: 2026-03-31
--
-- Tujuan:
-- 1. Menambahkan kolom tanggal_diterima_puu untuk menyimpan
--    tanggal diterima oleh PUU yang diekstrak dari kolom POSISI
-- 2. DD/M setelah kata "PUU" dalam POSISI = tanggal diterima PUU
-- 3. Menambahkan kolom dari_full untuk menyimpan terjemahan kode DARI
-- 4. Data ini digunakan untuk verifikasi dengan placeholder mail merge
--
-- Contoh parsing tanggal_diterima_puu:
-- - "SES 9/3 PUU 11/3" → tanggal_diterima_puu = 2026-03-11
-- - "PRC, KEU, PUU, Umum 6/1" → tanggal_diterima_puu = 2026-01-06
--
-- Contoh dari_full:
-- - "SD II" → "Subdit Wilayah II"
-- - "BU" → "Bagian Umum"
-- ============================================================

-- Tambah kolom tanggal_diterima_puu
ALTER TABLE surat_masuk_puu
    ADD COLUMN IF NOT EXISTS tanggal_diterima_puu DATE;

-- Tambah kolom dari_full (terjemahan kode DARI)
ALTER TABLE surat_masuk_puu
    ADD COLUMN IF NOT EXISTS dari_full TEXT;

-- Index untuk pencarian berdasarkan tanggal diterima PUU
CREATE INDEX IF NOT EXISTS idx_surat_masuk_puu_tgl_diterima_puu
    ON surat_masuk_puu (tanggal_diterima_puu DESC);

-- Index untuk pencarian berdasarkan dari_full
CREATE INDEX IF NOT EXISTS idx_surat_masuk_puu_dari_full
    ON surat_masuk_puu (dari_full);

-- Komentar untuk dokumentasi
COMMENT ON COLUMN surat_masuk_puu.tanggal_diterima_puu IS 
    'Tanggal diterima oleh PUU, diekstrak dari kolom POSISI (DD/M setelah kata PUU). Digunakan untuk verifikasi dengan mail merge.';

COMMENT ON COLUMN surat_masuk_puu.dari_full IS
    'Nama lengkap pengirim (terjemahan dari kode DARI). Contoh: SD II → Subdit Wilayah II, BU → Bagian Umum.';
