import os
import sys
import psycopg2
from datetime import datetime

# Adjust paths to load workspace models/integrations
sys.path.insert(0, "/home/aseps/MCP/mcp-unified")
sys.path.insert(0, "/home/aseps/MCP/core/mcp-unified")

try:
    from core.secrets import load_runtime_secrets
    load_runtime_secrets()
    print("Secrets loaded successfully.")
except Exception as e:
    print(f"Warning loading secrets: {e}")

from integrations.google_workspace.client import get_google_client

# Database config
DB_PARAMS = {
    "host": "localhost",
    "port": 5433,
    "database": "mcp_knowledge",
    "user": "mcp_user",
    "password": "mcp_password_2024"
}

SPREADSHEET_ID = "1ugCMpcQ2pjY0oscTqjp4-a5tiGetYDwgCY2lUj0jHlY"
RANGE_NAME = "'Form Responses 1'!A1:BF"  # Get all data up to column BF

def parse_timestamp(ts_str):
    if not ts_str or not ts_str.strip():
        return None
    ts_str = ts_str.strip()
    formats = [
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    # Fallback to current time if parsing fails
    print(f"Warning: Could not parse timestamp '{ts_str}', using current time.")
    return datetime.now()

def clean_text(text):
    if text is None:
        return None
    text_str = str(text).strip()
    if not text_str:
        return None
    # Normalize line breaks to standard \n
    text_str = text_str.replace("\r\n", "\n").replace("\r", "\n")
    return text_str

def main():
    print("Initializing Google Sheets API Client...")
    client = get_google_client()
    service = client.sheets
    
    print(f"Fetching data from Google Sheet (ID: {SPREADSHEET_ID})...")
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()
    
    values = result.get('values', [])
    if not values:
        print("Error: No data retrieved from Google Sheet.")
        sys.exit(1)
        
    print(f"Retrieved {len(values)} rows (including header).")
    
    # Connect to PostgreSQL
    print("Connecting to PostgreSQL database...")
    conn = psycopg2.connect(**DB_PARAMS)
    cursor = conn.cursor()
    
    try:
        # Clear existing entries for re-ingest safety
        print("Clearing existing tables for a clean ingest...")
        cursor.execute("TRUNCATE TABLE uu23_implementasi_raw RESTART IDENTITY;")
        cursor.execute("TRUNCATE TABLE uu23_implementasi_clean RESTART IDENTITY;")
        
        # 1. Raw Ingestion (Insert all rows including headers)
        print("Inserting raw data into uu23_implementasi_raw...")
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
        
        for idx, row in enumerate(values):
            # Pad row to 58 items
            padded_row = row + [""] * (58 - len(row))
            # Limit to first 58 items in case of extra columns
            padded_row = padded_row[:58]
            cursor.execute(raw_insert_query, padded_row)
            
        print(f"Raw ingestion complete. Inserted {len(values)} rows.")
        
        # 2. Clean & Normalized Ingestion
        print("Normalizing and inserting clean data into uu23_implementasi_clean...")
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
        
        # Sektoral Column Mapping:
        # Col G (index 6) to Col AL (index 37) are the 32 Concurrent affairs.
        # Let's map column index to cleaned Bidang names
        bidang_names = {}
        for col_idx in range(6, 38):
            header = headers[col_idx]
            # Clean header name to extract Bidang
            # e.g., "Sub Urusan Bidang Pendidikan " -> "Pendidikan"
            # e.g., "Urusan Sub Bidang Perpustakaan" -> "Perpustakaan"
            name = header.replace("Sub Urusan Bidang", "").replace("Urusan Sub Bidang", "").replace("Sub Urusan Pekerjaan Umum dan Penataan Ruang", "Pekerjaan Umum dan Penataan Ruang").replace("Bidang", "").strip()
            # Double check trailing/leading spaces or minor cleanups
            bidang_names[col_idx] = name
            
        clean_count = 0
        for r_idx, row in enumerate(data_rows):
            # Pad row to 58 items
            padded_row = row + [""] * (58 - len(row))
            padded_row = padded_row[:58]
            
            # Extract metadata
            timestamp = parse_timestamp(padded_row[0])
            email = clean_text(padded_row[1])
            if email:
                email = email.lower()
                
            urusan_konkuren = clean_text(padded_row[2])
            
            # Detect Bidang Urusan and Sub Urusan from conditional columns
            bidang_urusan = None
            sub_urusan = None
            for col_idx in range(6, 38):
                val = clean_text(padded_row[col_idx])
                if val:
                    bidang_urusan = bidang_names[col_idx]
                    sub_urusan = val
                    break  # Found the active bidang
                    
            # Extract feedback (Indices 38 to 57)
            feedback = [clean_text(padded_row[i]) for i in range(38, 58)]
            
            # Build values array for query
            # We have 25 placeholders in SQL query
            insert_vals = [
                timestamp,
                email,
                urusan_konkuren,
                bidang_urusan,
                sub_urusan,
                feedback[0],  # permasalahan_umum_pusat
                feedback[1],  # koordinasi_sinergi_pusat
                feedback[2],  # kewenangan_pusat
                feedback[3],  # alokasi_anggaran_pusat
                feedback[4],  # nspk_pusat
                feedback[5],  # penerapan_nspk_pusat
                feedback[6],  # pembinaan_teknis_pusat
                feedback[7],  # kebijakan_pusat
                feedback[8],  # lainnya_pusat
                feedback[9],  # permasalahan_umum_daerah
                feedback[10], # kewenangan_daerah
                feedback[11], # perencanaan_daerah
                feedback[12], # kemampuan_daerah
                feedback[13], # kebijakan_nspk_daerah
                feedback[14], # kebijakan_non_nspk_daerah
                feedback[15], # lainnya_daerah
                feedback[16], # solusi_pusat
                feedback[17], # tindak_lanjut_pusat
                feedback[18], # solusi_daerah
                feedback[19]  # tindak_lanjut_daerah
            ]
            
            cursor.execute(clean_insert_query, insert_vals)
            clean_count += 1
            
        conn.commit()
        print(f"Clean & Normalized ingestion complete. Inserted {clean_count} rows successfully.")
        
    except Exception as db_err:
        conn.rollback()
        print(f"Database transaction error: {db_err}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()
        print("Database connection closed.")

if __name__ == "__main__":
    main()
