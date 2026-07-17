import os
import aiohttp
import json
import logging
from typing import Dict, Any, List

# Tambahkan path ke sys.path jika diperlukan untuk import absolute, namun karena dijalankan dalam MCP, asumsi module path sudah benar.
import sys
sys.path.append("/home/aseps/MCP/core/mcp-unified")
from skills.document_extraction_skill import DocumentExtractionSkill
from knowledge.rag_engine import RAGEngine
import asyncpg

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
SUMMARIZATION_MODEL = "llama3.2:3b" # Gunakan llama3.2:3b sesuai model lokal untuk summarization

class DDFSPipeline:
    """
    Deep Document Fetching & Summarization (DDFS) Pipeline.
    Bertanggung jawab mengatur alur dari dokumen mentah -> OCR -> LLM Summarization -> Chunking -> Vector DB.
    """
    def __init__(self):
        self.ocr_skill = DocumentExtractionSkill()
        self.rag = RAGEngine()
        
    async def process_document(self, file_path: str, document_id: str, namespace: str = "surat_masuk") -> Dict[str, Any]:
        """
        Memproses satu dokumen dari awal hingga tersimpan di Vector DB.
        """
        logger.info(f"Memulai DDFS Pipeline untuk {file_path}")
        
        # Inisialisasi RAG
        await self.rag.initialize()
        
        # 1. Ekstraksi Teks (OCR)
        ext_result = await self.ocr_skill.extract_text(file_path)
        if not ext_result["success"]:
            return {"success": False, "error": ext_result["error"]}
            
        raw_text = ext_result["text"]
        
        if not raw_text or len(raw_text.strip()) < 10:
            return {"success": False, "error": "Teks yang terekstrak terlalu pendek atau kosong."}
            
        # 2. Chunking
        chunks = self._chunk_text(raw_text, max_words_per_chunk=500)
        
        # 3. Summarization menggunakan Ollama
        summary = await self._summarize_text(raw_text)
        
        # 4. Ingestion ke Vector DB (PGVector) via RAGEngine
        logger.info(f"Menyimpan {len(chunks)} chunks ke Vector DB...")
        ingestion_results = []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{i}"
            meta = {
                "parent_kode_surat": document_id,
                "chunk_index": i,
                "document_summary": summary
            }
            # Simpan ke PGVector
            success = await self.rag.add_document(
                doc_id=chunk_id,
                content=chunk,
                metadata=meta,
                namespace=namespace
            )
            ingestion_results.append(success)
            
        # 5. Update tabel surat_masuk di PostgreSQL
        db_updated = False
        try:
            # Gunakan DATABASE_URL dari env (fallback ke standar local dev)
            db_url = os.environ.get("DATABASE_URL", f"postgresql://mcp_user:{os.getenv('PG_PASSWORD') or os.getenv('POSTGRES_PASSWORD')}@localhost:5433/mcp_knowledge")
            conn = await asyncpg.connect(db_url)
            
            # Update field berdasarkan namespace
            if namespace == "arsip_2025":
                await conn.execute(
                    """
                    UPDATE arsip.surat_masuk 
                    SET ringkasan_ai = $1 
                    WHERE kode_surat = $2
                    """,
                    summary, document_id
                )
                logger.info(f"Berhasil meng-update tabel arsip.surat_masuk (ringkasan_ai) untuk document {document_id}")
            else:
                await conn.execute(
                    """
                    UPDATE surat_masuk_puu_internal 
                    SET catatan = COALESCE(catatan, '') || '\n\n[DDFS Summary]\n' || $1 
                    WHERE unique_id = $2 OR nomor_nd = $2
                    """,
                    summary, document_id
                )
                logger.info(f"Berhasil meng-update tabel surat_masuk_puu_internal untuk document {document_id}")
                
            await conn.close()
            db_updated = True
        except Exception as e:
            logger.error(f"Gagal update tabel database: {e}")
            
        return {
            "success": True,
            "document_id": document_id,
            "summary": summary,
            "chunks_count": len(chunks),
            "vector_ingested": all(ingestion_results),
            "db_updated": db_updated,
            "raw_text_length": len(raw_text)
        }
        
    def _chunk_text(self, text: str, max_words_per_chunk: int = 500) -> List[str]:
        """
        Memecah teks panjang menjadi chunk dengan overlap jika diperlukan.
        Implementasi sederhana: split by newline/words.
        """
        words = text.split()
        chunks = []
        for i in range(0, len(words), max_words_per_chunk):
            chunk = " ".join(words[i:i + max_words_per_chunk])
            chunks.append(chunk)
        return chunks
        
    async def _summarize_text(self, text: str) -> str:
        """
        Memanggil Ollama untuk meringkas dokumen.
        """
        # Potong teks jika terlalu panjang agar tidak OOM context (ambil 3000 kata pertama)
        words = text.split()
        if len(words) > 3000:
            text = " ".join(words[:3000]) + "... (terpotong)"
            
        prompt = f"""Tolong buatkan ringkasan eksekutif 1 paragraf (maksimal 3-4 kalimat) dalam Bahasa Indonesia dari isi dokumen berikut. Berikan intisarinya saja tanpa basa-basi:

DOKUMEN:
{text}

RINGKASAN:"""

        payload = {
            "model": SUMMARIZATION_MODEL,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=300) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "").strip()
                    else:
                        logger.warning(f"Ollama summarization gagal: {await response.text()}")
                        return "Gagal membuat ringkasan (Ollama error)."
        except Exception as e:
            logger.warning(f"Ollama summarization timeout atau error: {str(e)}")
            return "Gagal membuat ringkasan (koneksi LLM bermasalah)."

