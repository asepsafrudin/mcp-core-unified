import json
import os
import sys
from pathlib import Path
import psycopg2

# Paths
json_path = Path("/home/aseps/MCP/workspace/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_single_source_of_truth.json")

# Read database URL from .env
db_url = None
env_path = Path("/home/aseps/MCP/.env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            db_url = line.split("=", 1)[1].strip().strip('"').strip("'")

if not db_url:
    db_url = "postgresql://mcp_user:mcp_password_2024@localhost:5433/mcp_knowledge"

def main():
    print(f"Loading data from {json_path.name}...")
    if not json_path.exists():
        print("Error: JSON file not found.")
        sys.exit(1)
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print("Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
        # Use transaction
        cursor = conn.cursor()
        
        # 1. Clear existing data to be safe (schema already dropped/recreated, but clean insert is good)
        print("Clearing database tables...")
        cursor.execute("TRUNCATE uu23_metadata, uu23_bab, uu23_pasal, uu23_ayat, uu23_butir, uu23_lampiran_bidang, uu23_lampiran_sub_urusan, uu23_lampiran_kewenangan, uu23_lampiran_kewenangan_butir RESTART IDENTITY CASCADE;")
        
        # 2. Insert Metadata
        print("Inserting metadata...")
        meta = data.get("metadata", {})
        cursor.execute(
            "INSERT INTO uu23_metadata (nomor, tahun, tentang, jenis) VALUES (%s, %s, %s, %s) RETURNING id;",
            (meta.get("nomor", "23"), meta.get("tahun", "2014"), meta.get("tentang", "PEMERINTAHAN DAERAH"), meta.get("jenis", "UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 23 TAHUN 2014"))
        )
        meta_id = cursor.fetchone()[0]
        
        # 3. Insert Batang Tubuh (Bab, Pasal, Ayat, Butir)
        print("Inserting Batang Tubuh...")
        bab_list = data.get("batang_tubuh", {}).get("bab", [])
        
        bab_count = 0
        pasal_count = 0
        ayat_count = 0
        butir_count = 0
        
        for bab in bab_list:
            cursor.execute(
                "INSERT INTO uu23_bab (nomor, label, judul) VALUES (%s, %s, %s) RETURNING id;",
                (bab.get("nomor"), bab.get("label"), bab.get("judul"))
            )
            bab_id = cursor.fetchone()[0]
            bab_count += 1
            
            # Pasal can be directly in bab, or inside bagian in bab
            pasal_items = []
            
            # Check if there are bagian items
            bagian_list = bab.get("bagian", [])
            for bagian in bagian_list:
                bag_urutan = bagian.get("urutan")
                bag_judul = bagian.get("judul")
                for pasal in bagian.get("pasal", []):
                    pasal_items.append((pasal, bag_urutan, bag_judul))
            
            # Direct pasal
            for pasal in bab.get("pasal", []):
                pasal_items.append((pasal, None, None))
                
            # Process all pasal items for this bab
            for pasal, bag_urutan, bag_judul in pasal_items:
                cursor.execute(
                    "INSERT INTO uu23_pasal (bab_id, nomor, label, teks, bagian_urutan, bagian_judul) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;",
                    (bab_id, pasal.get("nomor"), pasal.get("label"), pasal.get("teks"), bag_urutan, bag_judul)
                )
                pasal_id = cursor.fetchone()[0]
                pasal_count += 1
                
                # Check for direct butir under pasal (e.g. Pasal 1 definitions)
                for butir in pasal.get("butir", []):
                    # Butir under pasal has 'nomor' or 'huruf'
                    b_num = butir.get("nomor")
                    b_letter = butir.get("huruf")
                    b_text = butir.get("teks", "")
                    cursor.execute(
                        "INSERT INTO uu23_butir (pasal_id, ayat_id, nomor, huruf, teks) VALUES (%s, NULL, %s, %s, %s);",
                        (pasal_id, b_num, b_letter, b_text)
                    )
                    butir_count += 1
                    
                # Check for ayat under pasal
                for ayat in pasal.get("ayat", []):
                    cursor.execute(
                        "INSERT INTO uu23_ayat (pasal_id, nomor, teks) VALUES (%s, %s, %s) RETURNING id;",
                        (pasal_id, ayat.get("nomor"), ayat.get("teks"))
                    )
                    ayat_id = cursor.fetchone()[0]
                    ayat_count += 1
                    
                    # Check for butir under ayat
                    for butir in ayat.get("butir", []):
                        b_num = butir.get("nomor")
                        b_letter = butir.get("huruf")
                        b_text = butir.get("teks", "")
                        cursor.execute(
                            "INSERT INTO uu23_butir (pasal_id, ayat_id, nomor, huruf, teks) VALUES (NULL, %s, %s, %s, %s);",
                            (ayat_id, b_num, b_letter, b_text)
                        )
                        butir_count += 1
                        
        print(f"  Inserted {bab_count} Bab, {pasal_count} Pasal, {ayat_count} Ayat, {butir_count} Butir.")

        # 4. Insert Lampiran (Bidang, Sub Urusan, Kewenangan, Kewenangan Butir)
        print("Inserting Lampiran...")
        bidang_list = data.get("lampiran", {}).get("bidang", [])
        
        bidang_count = 0
        sub_count = 0
        kewenangan_count = 0
        kewenangan_butir_count = 0
        
        for bidang in bidang_list:
            ref = bidang.get("referensi_hukum", {})
            ref_pasal = ref.get("pasal")
            ref_ayat = ref.get("ayat")
            ref_huruf = ref.get("huruf")
            
            cursor.execute(
                "INSERT INTO uu23_lampiran_bidang (kode, judul, nama_bidang, referensi_pasal, referensi_ayat, referensi_huruf) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;",
                (bidang.get("kode"), bidang.get("judul"), bidang.get("nama_bidang"), ref_pasal, ref_ayat, ref_huruf)
            )
            bidang_id = cursor.fetchone()[0]
            bidang_count += 1
            
            for sub in bidang.get("sub_urusan", []):
                cursor.execute(
                    "INSERT INTO uu23_lampiran_sub_urusan (bidang_id, nomor, nama) VALUES (%s, %s, %s) RETURNING id;",
                    (bidang_id, sub.get("nomor"), sub.get("nama"))
                )
                sub_id = cursor.fetchone()[0]
                sub_count += 1
                
                # Check three columns
                for lingkup in ["pemerintah_pusat", "daerah_provinsi", "daerah_kabupaten_kota"]:
                    col_data = sub.get(lingkup, {})
                    teks_umum = col_data.get("teks", "")
                    kosong = col_data.get("kosong", False)
                    
                    cursor.execute(
                        "INSERT INTO uu23_lampiran_kewenangan (sub_urusan_id, lingkup_kewenangan, teks_umum, kosong) VALUES (%s, %s, %s, %s) RETURNING id;",
                        (sub_id, lingkup, teks_umum, kosong)
                    )
                    kewenangan_id = cursor.fetchone()[0]
                    kewenangan_count += 1
                    
                    # Insert items if present
                    for butir in col_data.get("butir", []):
                        cursor.execute(
                            "INSERT INTO uu23_lampiran_kewenangan_butir (kewenangan_id, huruf, teks) VALUES (%s, %s, %s);",
                            (kewenangan_id, butir.get("huruf"), butir.get("teks"))
                        )
                        kewenangan_butir_count += 1
                        
        print(f"  Inserted {bidang_count} Bidang, {sub_count} Sub Urusan, {kewenangan_count} Kewenangan columns, {kewenangan_butir_count} Kewenangan Butir items.")
        
        # Commit transaction
        conn.commit()
        print("\nAll data loaded into PostgreSQL successfully!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\nMigration failed! Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
