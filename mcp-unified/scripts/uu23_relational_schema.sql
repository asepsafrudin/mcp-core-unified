-- PostgreSQL Relational Schema for UU 23/2014 Single Source of Truth

-- Drop tables if they exist (clean setup)
DROP TABLE IF EXISTS uu23_lampiran_kewenangan_butir CASCADE;
DROP TABLE IF EXISTS uu23_lampiran_kewenangan CASCADE;
DROP TABLE IF EXISTS uu23_lampiran_sub_urusan CASCADE;
DROP TABLE IF EXISTS uu23_lampiran_bidang CASCADE;
DROP TABLE IF EXISTS uu23_butir CASCADE;
DROP TABLE IF EXISTS uu23_ayat CASCADE;
DROP TABLE IF EXISTS uu23_pasal CASCADE;
DROP TABLE IF EXISTS uu23_bab CASCADE;
DROP TABLE IF EXISTS uu23_metadata CASCADE;

-- 1. Metadata Table
CREATE TABLE uu23_metadata (
    id SERIAL PRIMARY KEY,
    nomor VARCHAR(10) NOT NULL,
    tahun VARCHAR(10) NOT NULL,
    tentang TEXT NOT NULL,
    jenis TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Bab (Chapters) Table
CREATE TABLE uu23_bab (
    id SERIAL PRIMARY KEY,
    nomor VARCHAR(10) NOT NULL,
    label VARCHAR(20) NOT NULL,
    judul TEXT NOT NULL
);

-- 3. Pasal (Articles) Table
CREATE TABLE uu23_pasal (
    id SERIAL PRIMARY KEY,
    bab_id INTEGER NOT NULL REFERENCES uu23_bab(id) ON DELETE CASCADE,
    nomor INTEGER NOT NULL,
    label VARCHAR(20) NOT NULL,
    teks TEXT,
    bagian_urutan VARCHAR(20),
    bagian_judul TEXT
);

-- 4. Ayat (Paragraphs) Table
CREATE TABLE uu23_ayat (
    id SERIAL PRIMARY KEY,
    pasal_id INTEGER NOT NULL REFERENCES uu23_pasal(id) ON DELETE CASCADE,
    nomor INTEGER NOT NULL,
    teks TEXT NOT NULL
);

-- 5. Butir (Itemized Lists under Pasal/Ayat) Table
CREATE TABLE uu23_butir (
    id SERIAL PRIMARY KEY,
    pasal_id INTEGER REFERENCES uu23_pasal(id) ON DELETE CASCADE,
    ayat_id INTEGER REFERENCES uu23_ayat(id) ON DELETE CASCADE,
    nomor INTEGER,
    huruf VARCHAR(5),
    teks TEXT NOT NULL,
    CONSTRAINT chk_parent CHECK (pasal_id IS NOT NULL OR ayat_id IS NOT NULL)
);

-- 6. Lampiran Bidang (Sectors) Table
CREATE TABLE uu23_lampiran_bidang (
    id SERIAL PRIMARY KEY,
    kode VARCHAR(5) NOT NULL UNIQUE,
    judul TEXT NOT NULL,
    nama_bidang VARCHAR(100) NOT NULL,
    referensi_pasal INTEGER,
    referensi_ayat INTEGER,
    referensi_huruf VARCHAR(5)
);

-- 7. Lampiran Sub Urusan Table
CREATE TABLE uu23_lampiran_sub_urusan (
    id SERIAL PRIMARY KEY,
    bidang_id INTEGER NOT NULL REFERENCES uu23_lampiran_bidang(id) ON DELETE CASCADE,
    nomor INTEGER NOT NULL,
    nama VARCHAR(255) NOT NULL
);

-- 8. Lampiran Kewenangan (Central, Province, Kab/Kota Columns) Table
CREATE TABLE uu23_lampiran_kewenangan (
    id SERIAL PRIMARY KEY,
    sub_urusan_id INTEGER NOT NULL REFERENCES uu23_lampiran_sub_urusan(id) ON DELETE CASCADE,
    lingkup_kewenangan VARCHAR(50) NOT NULL CHECK (lingkup_kewenangan IN ('pemerintah_pusat', 'daerah_provinsi', 'daerah_kabupaten_kota')),
    teks_umum TEXT,
    kosong BOOLEAN DEFAULT FALSE,
    CONSTRAINT uniq_sub_lingkup UNIQUE (sub_urusan_id, lingkup_kewenangan)
);

-- 9. Lampiran Kewenangan Butir (Itemized Authority Lists) Table
CREATE TABLE uu23_lampiran_kewenangan_butir (
    id SERIAL PRIMARY KEY,
    kewenangan_id INTEGER NOT NULL REFERENCES uu23_lampiran_kewenangan(id) ON DELETE CASCADE,
    huruf VARCHAR(5) NOT NULL,
    teks TEXT NOT NULL
);

-- Indexes for performance and quick searching
CREATE INDEX idx_pasal_nomor ON uu23_pasal(nomor);
CREATE INDEX idx_ayat_pasal ON uu23_ayat(pasal_id);
CREATE INDEX idx_lampiran_bidang_kode ON uu23_lampiran_bidang(kode);
CREATE INDEX idx_lampiran_sub_urusan_bidang ON uu23_lampiran_sub_urusan(bidang_id);
CREATE INDEX idx_lampiran_kewenangan_sub ON uu23_lampiran_kewenangan(sub_urusan_id);
