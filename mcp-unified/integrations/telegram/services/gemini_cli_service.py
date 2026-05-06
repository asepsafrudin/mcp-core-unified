"""
Gemini CLI Service
Menangani komunikasi asinkron dengan gemini-pro CLI untuk pemrosesan tugas kompleks.
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class GeminiCLIService:
    """Service untuk menjalankan gemini-pro CLI secara asinkron."""

    def __init__(self, cli_path: str = "/home/aseps/.local/bin/gemini-pro"):
        self.cli_path = cli_path
        if not os.path.exists(self.cli_path):
            logger.warning(f"⚠️ gemini-pro CLI tidak ditemukan di {self.cli_path}")

    async def process_message(self, message: str, system_prompt: Optional[str] = None) -> str:
        """
        Menjalankan gemini-pro CLI dengan input pesan dan mengembalikan outputnya.
        """
        if not os.path.exists(self.cli_path):
            return "❌ Error: gemini-pro CLI tidak terinstal atau jalur salah."

        try:
            # Build command
            cmd = [self.cli_path, message]
            if system_prompt:
                cmd.extend(["--system", system_prompt])

            logger.info(f"🚀 Menjalankan Gemini CLI: {message[:50]}...")
            
            # Run process asinkron
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Tunggu hasil (timeout 5 menit untuk tugas berat)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            except asyncio.TimeoutError:
                process.kill()
                return "❌ Error: Proses Gemini CLI timeout ( > 5 menit)."

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"❌ Gemini CLI Error (Code {process.returncode}): {error_msg}")
                return f"❌ Error saat menjalankan Gemini CLI: {error_msg}"

            # Bersihkan output (menghapus log JSON-RPC jika ada yang bocor ke stdout)
            output = stdout.decode().strip()
            
            # Sederhanakan output jika terlalu teknis (opsional)
            if not output:
                return "⚠️ Gemini CLI tidak memberikan respon."

            return output

        except Exception as e:
            logger.exception(f"❌ Gagal memproses pesan dengan Gemini CLI: {e}")
            return f"❌ Terjadi kesalahan internal: {str(e)}"
