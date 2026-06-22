import asyncio
import os
import sys
import asyncpg
import logging

sys.path.append("/home/aseps/MCP/core/mcp-unified")
from knowledge.ingestion.ddfs_pipeline import DDFSPipeline
from agents.profiles.legal.connectors.gdrive_fetcher import GDriveFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_batch():
    logger.info("=== MEMULAI BATCH PEMROSESAN DDFS (Tahun 2025) ===")
    
    db_url = os.environ.get("DATABASE_URL", "postgresql://mcp_user:mcp_password_2024@localhost:5433/mcp_knowledge")
    conn = await asyncpg.connect(db_url)
    
    # Ambil arsip surat masuk tahun 2025 dari tabel arsip.surat_masuk yang belum memiliki ringkasan
    query = """
        SELECT kode_surat as unique_id, file_link as drive_file_url 
        FROM arsip.surat_masuk 
        WHERE file_link IS NOT NULL 
          AND file_link LIKE 'http%'
          AND ringkasan_ai IS NULL
    """
    rows = await conn.fetch(query)
    await conn.close()
    
    if not rows:
        logger.info("Tidak ada dokumen arsip surat masuk 2025 yang perlu diproses.")
        return
        
    logger.info(f"Ditemukan {len(rows)} dokumen untuk diproses dari arsip.surat_masuk.")
    
    pipeline = DDFSPipeline()
    fetcher = GDriveFetcher()
    
    for row in rows:
        doc_id = row['unique_id']
        url = row['drive_file_url']
        
        logger.info(f"---")
        logger.info(f"Memproses {doc_id} | {url}")
        
        # Modifikasi URL untuk export PDF jika itu Docs
        if "docs.google.com/document" in url:
            import re
            url = re.sub(r'/edit.*$', '/export?format=pdf', url)
            
        success, filepath, mime = await fetcher.fetch_and_detect_mime(url, dest_dir="/home/aseps/MCP/scratch")
        
        if not success or not filepath:
            logger.error(f"Gagal mengunduh GDrive file untuk {doc_id}.")
            continue
            
        try:
            # Gunakan namespace 'arsip_2025' agar pipeline tau ini arsip
            result = await pipeline.process_document(filepath, doc_id, namespace="arsip_2025")
            if result.get("success"):
                logger.info(f"SUKSES {doc_id} -> Chunks: {result.get('chunks_count')} | Vector: {result.get('vector_ingested')}")
            else:
                logger.error(f"GAGAL PIPELINE {doc_id} -> {result.get('error')}")
        except Exception as e:
            logger.error(f"ERROR Kritis saat memproses {doc_id}: {e}")

if __name__ == "__main__":
    asyncio.run(run_batch())
