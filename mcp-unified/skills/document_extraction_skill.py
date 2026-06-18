import os
import aiohttp
import logging
from pydantic import BaseModel
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DocumentExtractionSkill:
    """
    Skill untuk menghubungkan Agen MCP dengan docTR Worker Service (FastAPI)
    yang berjalan di WSL. Bertugas mengirim dokumen dan menerima ekstraksi teks.
    """
    def __init__(self, doctr_worker_url: str = "http://127.0.0.1:8080/extract"):
        self.doctr_worker_url = doctr_worker_url

    async def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        Mengirim dokumen (PDF/Image) ke docTR worker dan mengembalikan teksnya.
        """
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File tidak ditemukan: {file_path}"
            }
            
        logger.info(f"Mengirim {file_path} ke docTR Worker...")
        
        try:
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    # Mengirim file via multipart/form-data
                    data = aiohttp.FormData()
                    data.add_field('file', f, filename=os.path.basename(file_path))
                    
                    async with session.post(self.doctr_worker_url, data=data) as response:
                        if response.status == 200:
                            result = await response.json()
                            return {
                                "success": True,
                                "text": result.get("text", "")
                            }
                        else:
                            error_text = await response.text()
                            return {
                                "success": False,
                                "error": f"docTR Worker HTTP Error {response.status}: {error_text}"
                            }
        except aiohttp.ClientConnectorError:
            return {
                "success": False,
                "error": "Gagal terhubung ke docTR Worker. Pastikan layanan berjalan di port 8080."
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ekstraksi gagal: {str(e)}"
            }
