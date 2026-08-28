#!/usr/bin/env python3
"""
Load UU 23/2014 Single Source of Truth JSON into PostgreSQL.
Refactored to Psycopg v3, central env loading, and transaction context manager.
"""

import json
import os
import sys
import logging
from pathlib import Path

repo_root = Path(__file__).resolve().parents[3]
core_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(core_root))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("load_uu23")

try:
    from scripts.load_env import load_env
    load_env()
except Exception as e:
    logger.warning(f"Fallback loading env: {e}")

import psycopg

# Candidate JSON paths
json_candidate_paths = [
    repo_root / "workspace" / "Bangda_PUU" / "data" / "workspace" / "lampiran_UU_23" / "processed" / "UU_23_2014_single_source_of_truth.json",
    repo_root / "data" / "UU_23_2014_single_source_of_truth.json",
    repo_root / "storage" / "data" / "UU_23_2014_single_source_of_truth.json"
]


def get_json_path() -> Path:
    for p in json_candidate_paths:
        if p.exists():
            return p
    return json_candidate_paths[0]


def get_db_connection_str() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "mcp_knowledge")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


def main():
    json_path = get_json_path()
    logger.info(f"Loading data from {json_path}...")
    if not json_path.exists():
        logger.error(f"Error: JSON file not found at {json_path}")
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn_str = get_db_connection_str()
    logger.info(f"Connecting to PostgreSQL ({os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')})...")

    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cursor:
            # 1. Truncate existing relational tables
            logger.info("Clearing relational database tables...")
            cursor.execute(
                "TRUNCATE uu23_metadata, uu23_bab, uu23_pasal, uu23_ayat, uu23_butir, "
                "uu23_lampiran_bidang, uu23_lampiran_sub_urusan, uu23_lampiran_kewenangan, "
                "uu23_lampiran_kewenangan_butir RESTART IDENTITY CASCADE;"
            )

            # 2. Insert Metadata
            logger.info("Inserting metadata...")
            meta = data.get("metadata", {})
            cursor.execute(
                "INSERT INTO uu23_metadata (nomor, tahun, tentang, jenis) VALUES (%s, %s, %s, %s) RETURNING id;",
                (
                    meta.get("nomor", "23"),
                    meta.get("tahun", "2014"),
                    meta.get("tentang", "PEMERINTAHAN DAERAH"),
                    meta.get("jenis", "UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 23 TAHUN 2014")
                )
            )
            meta_id = cursor.fetchone()[0]

            # 3. Insert Batang Tubuh
            logger.info("Inserting Batang Tubuh...")
            bab_list = data.get("batang_tubuh", {}).get("bab", [])
            bab_count, pasal_count, ayat_count, butir_count = 0, 0, 0, 0

            for bab in bab_list:
                cursor.execute(
                    "INSERT INTO uu23_bab (nomor, label, judul) VALUES (%s, %s, %s) RETURNING id;",
                    (bab.get("nomor"), bab.get("label"), bab.get("judul"))
                )
                bab_id = cursor.fetchone()[0]
                bab_count += 1

                pasal_items = []
                for bagian in bab.get("bagian", []):
                    bag_urutan = bagian.get("urutan")
                    bag_judul = bagian.get("judul")
                    for pasal in bagian.get("pasal", []):
                        pasal_items.append((pasal, bag_urutan, bag_judul))

                for pasal in bab.get("pasal", []):
                    pasal_items.append((pasal, None, None))

                for pasal, bag_urutan, bag_judul in pasal_items:
                    cursor.execute(
                        "INSERT INTO uu23_pasal (bab_id, nomor, label, teks, bagian_urutan, bagian_judul) "
                        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;",
                        (bab_id, pasal.get("nomor"), pasal.get("label"), pasal.get("teks"), bag_urutan, bag_judul)
                    )
                    pasal_id = cursor.fetchone()[0]
                    pasal_count += 1

                    for butir in pasal.get("butir", []):
                        cursor.execute(
                            "INSERT INTO uu23_butir (pasal_id, ayat_id, nomor, huruf, teks) VALUES (%s, NULL, %s, %s, %s);",
                            (pasal_id, butir.get("nomor"), butir.get("huruf"), butir.get("teks", ""))
                        )
                        butir_count += 1

                    for ayat in pasal.get("ayat", []):
                        cursor.execute(
                            "INSERT INTO uu23_ayat (pasal_id, nomor, teks) VALUES (%s, %s, %s) RETURNING id;",
                            (pasal_id, ayat.get("nomor"), ayat.get("teks"))
                        )
                        ayat_id = cursor.fetchone()[0]
                        ayat_count += 1

                        for butir in ayat.get("butir", []):
                            cursor.execute(
                                "INSERT INTO uu23_butir (pasal_id, ayat_id, nomor, huruf, teks) VALUES (NULL, %s, %s, %s, %s);",
                                (ayat_id, butir.get("nomor"), butir.get("huruf"), butir.get("teks", ""))
                            )
                            butir_count += 1

            logger.info(f"Inserted {bab_count} Bab, {pasal_count} Pasal, {ayat_count} Ayat, {butir_count} Butir.")

            # 4. Insert Lampiran
            logger.info("Inserting Lampiran...")
            bidang_list = data.get("lampiran", {}).get("bidang", [])
            bidang_count, sub_count, kewenangan_count, kewenangan_butir_count = 0, 0, 0, 0

            for bidang in bidang_list:
                ref = bidang.get("referensi_hukum", {})
                cursor.execute(
                    "INSERT INTO uu23_lampiran_bidang (kode, judul, nama_bidang, referensi_pasal, referensi_ayat, referensi_huruf) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;",
                    (bidang.get("kode"), bidang.get("judul"), bidang.get("nama_bidang"), ref.get("pasal"), ref.get("ayat"), ref.get("huruf"))
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

                    for lingkup in ["pemerintah_pusat", "daerah_provinsi", "daerah_kabupaten_kota"]:
                        col_data = sub.get(lingkup, {})
                        cursor.execute(
                            "INSERT INTO uu23_lampiran_kewenangan (sub_urusan_id, lingkup_kewenangan, teks_umum, kosong) "
                            "VALUES (%s, %s, %s, %s) RETURNING id;",
                            (sub_id, lingkup, col_data.get("teks", ""), col_data.get("kosong", False))
                        )
                        kewenangan_id = cursor.fetchone()[0]
                        kewenangan_count += 1

                        for butir in col_data.get("butir", []):
                            cursor.execute(
                                "INSERT INTO uu23_lampiran_kewenangan_butir (kewenangan_id, huruf, teks) VALUES (%s, %s, %s);",
                                (kewenangan_id, butir.get("huruf"), butir.get("teks"))
                            )
                            kewenangan_butir_count += 1

            logger.info(f"Inserted {bidang_count} Bidang, {sub_count} Sub Urusan, {kewenangan_count} Kewenangan columns, {kewenangan_butir_count} Kewenangan Butir items.")
            conn.commit()
            logger.info("🎉 All UU23 relational data loaded into PostgreSQL successfully!")


if __name__ == "__main__":
    main()
