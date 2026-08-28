#!/usr/bin/env python3
"""
UU 23/2014 Google Sheet Form Responses Ingestion Pipeline.
Refactored to modern Psycopg v3, bulk batching, and dynamic env loading.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Any

# Adjust paths dynamically to workspace root
repo_root = Path(__file__).resolve().parents[3]
core_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(core_root))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_uu23")

# Load environment & secrets
try:
    from scripts.load_env import load_env
    load_env()
except Exception as e:
    logger.warning(f"Fallback loading runtime secrets: {e}")
    try:
        from core.secrets import load_runtime_secrets
        load_runtime_secrets()
    except Exception:
        pass

import psycopg
from integrations.google_workspace.client import get_google_client

SPREADSHEET_ID = os.getenv("UU23_SPREADSHEET_ID", "1ugCMpcQ2pjY0oscTqjp4-a5tiGetYDwgCY2lUj0jHlY")
RANGE_NAME = "'Form Responses 1'!A1:BF"  # All columns up to BF


def get_db_connection_str() -> str:
    """Builds PostgreSQL connection string from central environment."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "mcp_knowledge")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


def parse_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """Parses various timestamp formats from Google Sheets."""
    if not ts_str or not str(ts_str).strip():
        return None
    ts_clean = str(ts_str).strip()
    formats = [
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_clean, fmt)
        except ValueError:
            continue
    logger.warning(f"Could not parse timestamp '{ts_clean}', defaulting to current time.")
    return datetime.now()


def clean_text(text: Any) -> Optional[str]:
    """Normalizes and trims string text."""
    if text is None:
        return None
    text_str = str(text).strip()
    if not text_str:
        return None
    return text_str.replace("\r\n", "\n").replace("\r", "\n")


def main():
    logger.info("Initializing Google Sheets API Client...")
    try:
        client = get_google_client()
        service = client.sheets
        logger.info(f"Fetching data from Google Sheet (ID: {SPREADSHEET_ID})...")
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()
        values = result.get('values', [])
    except Exception as e:
        logger.error(f"Error connecting to Google Sheets API: {e}")
        sys.exit(1)

    if not values:
        logger.error("No data retrieved from Google Sheet.")
        sys.exit(1)

    logger.info(f"Retrieved {len(values)} rows from Google Sheets (including header).")

    conn_str = get_db_connection_str()
    logger.info(f"Connecting to PostgreSQL ({os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')})...")

    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cursor:
            # 1. Truncate target tables for clean state
            logger.info("Clearing existing tables for a clean atomic ingest...")
            cursor.execute("TRUNCATE TABLE uu23_implementasi_raw RESTART IDENTITY;")
            cursor.execute("TRUNCATE TABLE uu23_implementasi_clean RESTART IDENTITY;")

            # 2. Raw Bulk Ingestion
            raw_insert_query = """
                INSERT INTO uu23_implementasi_raw (
                    col_a, col_b, col_c, col_d, col_e, col_f, col_g, col_h, col_i, col_j,
                    col_k, col_l, col_m, col_n, col_o, col_p, col_q, col_r, col_s, col_t,
                    col_u, col_v, col_w, col_x, col_y, col_z,
                    col_aa, col_ab, col_ac, col_ad, col_ae, col_af, col_ag, col_ah, col_ai, col_aj,
                    col_ak, col_al, col_am, col_an, col_ao, col_ap, col_aq, col_ar, col_as, col_at,
                    col_au, col_av, col_aw, col_ax, col_ay, col_az,
                    col_ba, col_bb, col_bc, col_bd, col_be, col_bf
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                );
            """

            raw_rows = []
            for row in values:
                padded = row + [""] * (58 - len(row))
                raw_rows.append(padded[:58])

            logger.info(f"Executing high-speed batch insert of {len(raw_rows)} raw rows...")
            cursor.executemany(raw_insert_query, raw_rows)
            logger.info("Raw bulk ingestion complete.")

            # 3. Clean & Normalized Bulk Ingestion
            headers = values[0]
            data_rows = values[1:]

            clean_insert_query = """
                INSERT INTO uu23_implementasi_clean (
                    timestamp, email_address, urusan_konkuren, bidang_urusan, sub_urusan,
                    permasalahan_umum_pusat, koordinasi_sinergi_pusat, kewenangan_pusat,
                    alokasi_anggaran_pusat, nspk_pusat, penerapan_nspk_pusat, pembinaan_teknis_pusat,
                    kebijakan_pusat, lainnya_pusat,
                    permasalahan_umum_daerah, kewenangan_daerah, perencanaan_daerah, kemampuan_daerah,
                    kebijakan_nspk_daerah, kebijakan_non_nspk_daerah, lainnya_daerah,
                    solusi_pusat, tindak_lanjut_pusat, solusi_daerah, tindak_lanjut_daerah
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                );
            """

            # Build sectoral mapping
            bidang_names = {}
            for col_idx in range(6, 38):
                if col_idx < len(headers):
                    header = headers[col_idx]
                    name = (
                        header.replace("Sub Urusan Bidang", "")
                        .replace("Urusan Sub Bidang", "")
                        .replace("Sub Urusan Pekerjaan Umum dan Penataan Ruang", "Pekerjaan Umum dan Penataan Ruang")
                        .replace("Bidang", "")
                        .strip()
                    )
                    bidang_names[col_idx] = name

            clean_rows = []
            for row in data_rows:
                padded = row + [""] * (58 - len(row))
                padded = padded[:58]

                timestamp = parse_timestamp(padded[0])
                email = clean_text(padded[1])
                if email:
                    email = email.lower()

                urusan_konkuren = clean_text(padded[2])

                bidang_urusan = None
                sub_urusan = None
                for col_idx in range(6, 38):
                    val = clean_text(padded[col_idx])
                    if val:
                        bidang_urusan = bidang_names.get(col_idx)
                        sub_urusan = val
                        break

                feedback = [clean_text(padded[i]) for i in range(38, 58)]

                insert_vals = [
                    timestamp,
                    email,
                    urusan_konkuren,
                    bidang_urusan,
                    sub_urusan,
                    feedback[0], feedback[1], feedback[2], feedback[3], feedback[4],
                    feedback[5], feedback[6], feedback[7], feedback[8], feedback[9],
                    feedback[10], feedback[11], feedback[12], feedback[13], feedback[14],
                    feedback[15], feedback[16], feedback[17], feedback[18], feedback[19]
                ]
                clean_rows.append(insert_vals)

            logger.info(f"Executing batch insert of {len(clean_rows)} normalized clean rows...")
            cursor.executemany(clean_insert_query, clean_rows)
            conn.commit()
            logger.info(f"🎉 Sukses! {len(clean_rows)} baris data form UU23 berhasil dimigrasi & dinormalisasi.")


if __name__ == "__main__":
    main()
