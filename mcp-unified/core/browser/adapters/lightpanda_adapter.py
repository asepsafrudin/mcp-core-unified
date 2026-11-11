"""
Lightpanda Pure-Headless Browser Adapter
========================================
Adapter untuk eksekusi JavaScript cepat dan ekstraksi DOM/Markdown berkecepatan tinggi
menggunakan engine Lightpanda (Zig + V8) via CLI Direct & CDP WebSocket.

Fitur:
1. Fast Fetch Markdown / HTML (< 300ms via Lightpanda V8 engine).
2. Playwright CDP Connection via ws://127.0.0.1:9222/.
3. Auto-recovery daemon jika server belum aktif.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

from playwright.async_api import async_playwright, Page, BrowserContext, Browser

logger = logging.getLogger("lightpanda_adapter")

REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_BIN = REPO_ROOT / "bin" / "lightpanda"
DEFAULT_CDP_URL = os.getenv("LIGHTPANDA_CDP_URL", "ws://127.0.0.1:9222/")
RUNNER_SCRIPT = REPO_ROOT / "scripts" / "run_lightpanda_daemon.sh"


class LightpandaAdapter:
    """Adapter untuk berkomunikasi dengan Lightpanda browser."""

    def __init__(self, bin_path: Optional[Path] = None, cdp_url: str = DEFAULT_CDP_URL):
        self.bin_path = bin_path or DEFAULT_BIN
        self.cdp_url = cdp_url
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def is_available(self) -> bool:
        """Mengecek apakah biner Lightpanda tersedia dan executable."""
        return self.bin_path.exists() and os.access(str(self.bin_path), os.X_OK)

    def ensure_daemon_running(self) -> bool:
        """Memastikan daemon CDP aktif di port 9222."""
        try:
            res = subprocess.run([str(RUNNER_SCRIPT), "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                return True
            # Jalankan start jika belum aktif
            logger.info("Memulai Lightpanda CDP Daemon...")
            start_res = subprocess.run([str(RUNNER_SCRIPT), "start"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return start_res.returncode == 0
        except Exception as e:
            logger.debug(f"Gagal memeriksa/menjalankan daemon Lightpanda: {e}")
            return False

    async def fetch_markdown_async(self, url: str, timeout: int = 20) -> Dict[str, Any]:
        """
        Mengekstrak konten web langsung menjadi Markdown bersih menggunakan V8 runtime Lightpanda.
        Kecepatan: < 300ms untuk sebagian besar halaman.
        """
        if not self.is_available():
            return {"success": False, "error": f"Biner Lightpanda tidak ditemukan di {self.bin_path}"}

        cmd = [
            str(self.bin_path),
            "fetch",
            "--dump", "markdown",
            "--log-filter", "all",
            "--log-level", "fatal",
            url
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="ignore").strip()

            if proc.returncode == 0 and output:
                return {
                    "success": True,
                    "url": url,
                    "markdown": output,
                    "chars_count": len(output),
                    "engine": "lightpanda-v8"
                }
            return {
                "success": False,
                "error": stderr.decode("utf-8", errors="ignore").strip() or "Output kosong",
                "url": url
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Timeout {timeout}s saat fetching {url}"}
        except Exception as e:
            return {"success": False, "error": str(e), "url": url}

    def fetch_markdown(self, url: str, timeout: int = 20) -> Dict[str, Any]:
        """Versi sinkron untuk fetch_markdown_async."""
        return asyncio.run(self.fetch_markdown_async(url, timeout=timeout))

    async def connect_cdp(self) -> Optional[Page]:
        """Menghubungkan Playwright ke Lightpanda WebSocket CDP daemon."""
        if not self.ensure_daemon_running():
            logger.warning("Lightpanda daemon tidak dapat diaktifkan.")
            return None

        try:
            if not self.playwright:
                self.playwright = await async_playwright().start()

            if not self.browser:
                self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)
                self.context = await self.browser.new_context(
                    viewport={"width": 1440, "height": 900}
                )
                self.page = await self.context.new_page()

            return self.page
        except Exception as e:
            logger.error(f"Gagal koneksi ke Lightpanda CDP ({self.cdp_url}): {e}")
            return None

    async def navigate_cdp(self, url: str, wait_for: str = "domcontentloaded", timeout: int = 20000) -> Dict[str, Any]:
        """Navigasi via CDP connection."""
        page = await self.connect_cdp()
        if not page:
            return {"success": False, "error": "Koneksi CDP gagal"}

        try:
            resp = await page.goto(url, wait_until=wait_for, timeout=timeout)
            title = await page.title()
            content = await page.content()
            return {
                "success": True,
                "url": page.url,
                "title": title,
                "html": content,
                "http_status": resp.status if resp else None,
                "engine": "lightpanda-cdp"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "url": url}

    async def close_cdp(self):
        """Menutup koneksi CDP."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        finally:
            self.context = None
            self.browser = None
            self.playwright = None
            self.page = None


# Singleton instance
lightpanda_adapter = LightpandaAdapter()
