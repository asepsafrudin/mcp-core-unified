-- Schema for Ingesting and Cleaning Google Sheet UU 23/2014 Problem Inventory

-- 1. Create Raw Table (58 columns matching columns A to BF)
CREATE TABLE IF NOT EXISTS uu23_implementasi_raw (
    id SERIAL PRIMARY KEY,
    col_a TEXT, col_b TEXT, col_c TEXT, col_d TEXT, col_e TEXT, col_f TEXT, col_g TEXT, col_h TEXT, col_i TEXT, col_j TEXT,
    col_k TEXT, col_l TEXT, col_m TEXT, col_n TEXT, col_o TEXT, col_p TEXT, col_q TEXT, col_r TEXT, col_s TEXT, col_t TEXT,
    col_u TEXT, col_v TEXT, col_w TEXT, col_x TEXT, col_y TEXT, col_z TEXT,
    col_aa TEXT, col_ab TEXT, col_ac TEXT, col_ad TEXT, col_ae TEXT, col_af TEXT, col_ag TEXT, col_ah TEXT, col_ai TEXT, col_aj TEXT,
    col_ak TEXT, col_al TEXT, col_am TEXT, col_an TEXT, col_ao TEXT, col_ap TEXT, col_aq TEXT, col_ar TEXT, col_as TEXT, col_at TEXT,
    col_au TEXT, col_av TEXT, col_aw TEXT, col_ax TEXT, col_ay TEXT, col_az TEXT,
    col_ba TEXT, col_bb TEXT, col_bc TEXT, col_bd TEXT, col_be TEXT, col_bf TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create Clean/Normalized Table
CREATE TABLE IF NOT EXISTS uu23_implementasi_clean (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ,
    email_address VARCHAR(255),
    urusan_konkuren VARCHAR(255),
    bidang_urusan VARCHAR(255),
    sub_urusan TEXT,
    
    -- Central Government Feedback
    permasalahan_umum_pusat TEXT,
    koordinasi_sinergi_pusat TEXT,
    kewenangan_pusat TEXT,
    alokasi_anggaran_pusat TEXT,
    nspk_pusat TEXT,
    penerapan_nspk_pusat TEXT,
    pembinaan_teknis_pusat TEXT,
    kebijakan_pusat TEXT,
    lainnya_pusat TEXT,
    
    -- Regional Government Feedback
    permasalahan_umum_daerah TEXT,
    kewenangan_daerah TEXT,
    perencanaan_daerah TEXT,
    kemampuan_daerah TEXT,
    kebijakan_nspk_daerah TEXT,
    kebijakan_non_nspk_daerah TEXT,
    lainnya_daerah TEXT,
    solusi_pusat TEXT,
    tindak_lanjut_pusat TEXT,
    solusi_daerah TEXT,
    tindak_lanjut_daerah TEXT,
    
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for searching and filtering by bidang_urusan
CREATE INDEX IF NOT EXISTS idx_uu23_clean_bidang ON uu23_implementasi_clean(bidang_urusan);
-- Index for email
CREATE INDEX IF NOT EXISTS idx_uu23_clean_email ON uu23_implementasi_clean(email_address);
