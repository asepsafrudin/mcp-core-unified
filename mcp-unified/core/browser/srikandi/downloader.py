"""
Srikandi Attachment & Document Downloader
Mengunduh naskah dinas, surat, dan lembar disposisi PDF dari SRIKANDI
dengan penerapan Storage Isolation Protocol (storage/documents/srikandi/{profile}/{tahun}/).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from playwright.async_api import async_playwright

from .auth_manager import srikandi_auth_manager, REPO_ROOT

logger = logging.getLogger("srikandi_downloader")

BASE_STORAGE_DOCS = REPO_ROOT / "storage" / "documents" / "srikandi"


class SrikandiDownloader:
    """Downloader untuk lampiran dan dokumen surat SRIKANDI."""

    def __init__(self):
        self.auth_manager = srikandi_auth_manager
        self.base_storage = BASE_STORAGE_DOCS
        self.base_storage.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, text: str) -> str:
        """Membersihkan karakter ilegal pada penamaan file."""
        clean = re.sub(r'[/\\:*?"<>|\s]+', '_', text.strip())
        return clean[:80]

    def _get_target_directory(self, profile_id: str, date_obj: Optional[datetime] = None) -> Path:
        """Membuat dan mengembalikan direktori target penyimpanan terisolasi."""
        d = date_obj or datetime.now()
        target = self.base_storage / profile_id / str(d.year) / f"{d.month:02d}"
        target.mkdir(parents=True, exist_ok=True)
        return target

    async def download_attachment_by_url(
        self,
        url: str,
        profile_id: str = "default",
        nomor_naskah: str = "doc",
        custom_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mengunduh lampiran berdasarkan URL langsung dengan memanfaatkan sesi aktif profil.
        Mendukung streaming S3 cepat untuk signed URL dan browser context untuk dynamic download.
        """
        target_dir = self._get_target_directory(profile_id)
        clean_no = self._sanitize_filename(nomor_naskah)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Ekstrak ekstensi dari URL atau custom_name
        ext = ".pdf"
        if custom_name and "." in custom_name:
            ext = f".{custom_name.split('.')[-1]}"
        elif ".docx" in url.lower():
            ext = ".docx"
        elif ".xlsx" in url.lower():
            ext = ".xlsx"
        elif ".doc" in url.lower():
            ext = ".doc"

        filename = custom_name or f"SRIKANDI_{profile_id}_{clean_no}_{timestamp}{ext}"
        target_file = target_dir / filename

        # 1. Jalur Cepat (High-Performance): Direct S3 Streaming jika Signed URL
        if "s3.arsip.go.id" in url or "X-Amz-Signature" in url:
            try:
                import urllib.request
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    content = resp.read()

                with open(target_file, "wb") as f:
                    f.write(content)

                file_size = len(content)
                sha256 = hashlib.sha256(content).hexdigest()
                is_valid = content.startswith(b"%PDF") or content.startswith(b"PK\x03\x04") or file_size > 0

                logger.info(f"Berhasil mengunduh S3 lampiran: {filename} ({file_size} bytes)")
                return {
                    "success": True,
                    "profile_id": profile_id,
                    "file_path": str(target_file),
                    "file_name": filename,
                    "file_size": file_size,
                    "sha256": sha256,
                    "is_valid": is_valid,
                    "downloaded_at": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.warning(f"Gagal direct S3 stream, mencoba fallback browser context: {e}")

        # 2. Jalur Fallback: Browser Context Download
        async with async_playwright() as p:
            browser, context = await self.auth_manager.create_browser_context(
                p, profile_id=profile_id, headless=True
            )
            page = await context.new_page()

            try:
                # Siapkan download listener
                async with page.expect_download(timeout=45000) as download_info:
                    await page.goto(url, wait_until="domcontentloaded")

                download = await download_info.value
                await download.save_as(str(target_file))

                file_size = target_file.stat().st_size
                with open(target_file, "rb") as f:
                    content = f.read()
                    sha256 = hashlib.sha256(content).hexdigest()
                    is_valid = content.startswith(b"%PDF") or content.startswith(b"PK\x03\x04") or file_size > 0

                return {
                    "success": True,
                    "profile_id": profile_id,
                    "file_path": str(target_file),
                    "file_name": filename,
                    "file_size": file_size,
                    "sha256": sha256,
                    "is_valid": is_valid,
                    "downloaded_at": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"Gagal mengunduh lampiran dari {url}: {e}")
                if target_file.exists():
                    try:
                        target_file.unlink()
                    except Exception:
                        pass
                return {
                    "success": False,
                    "profile_id": profile_id,
                    "url": url,
                    "error": str(e)
                }
            finally:
                await context.close()
                await browser.close()

    async def download_attachments_batch(
        self,
        items: List[Dict[str, Any]],
        profile_id: str = "default",
    ) -> List[Dict[str, Any]]:
        """
        Mengunduh kumpulan lampiran dari hasil scraping secara berurutan.
        """
        results: List[Dict[str, Any]] = []
        for item in items:
            urls = item.get("lampiran_urls", [])
            nomor = item.get("nomor_naskah", "unknown_no")
            for u in urls:
                res = await self.download_attachment_by_url(
                    url=u,
                    profile_id=profile_id,
                    nomor_naskah=nomor
                )
                res["nomor_naskah"] = nomor
                results.append(res)
                await asyncio.sleep(1)  # Rate limiting santai
        return results


srikandi_downloader = SrikandiDownloader()
