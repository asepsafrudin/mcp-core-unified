"""
Srikandi MCP Tools Suite
Menyediakan interface tools MCP untuk pengelolaan multi-profil akun SRIKANDI,
verifikasi sesi, ekstraksi data persuratan/disposisi, pengunduhan lampiran, dan sinkronisasi database.
"""

from __future__ import annotations

import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("srikandi_tools")

# Ensure core path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from core.task import Task, TaskResult
from core.browser.srikandi.auth_manager import srikandi_auth_manager, SrikandiAccountProfile
from core.browser.srikandi.scraper import srikandi_scraper
from core.browser.srikandi.downloader import srikandi_downloader
from core.browser.srikandi.db_sync import srikandi_db_sync


@register_tool
class SrikandiListProfilesTool(BaseTool):
    """Tool MCP untuk melihat daftar profil akun SRIKANDI dan status sesi."""

    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="srikandi_list_profiles",
            description="Mendapatkan daftar profil akun SRIKANDI yang terdaftar beserta status keaktifan dan path sesi.",
            parameters=[],
            returns="JSON list profil akun SRIKANDI"
        )

    async def execute(self, task: Task) -> TaskResult:
        try:
            profiles = srikandi_auth_manager.list_profiles(mask_secret=True)
            return TaskResult(
                task_id=task.id,
                status="success",
                data={"profiles": profiles, "total": len(profiles)}
            )
        except Exception as e:
            return TaskResult(task_id=task.id, status="error", error=str(e))


@register_tool
class SrikandiCheckSessionTool(BaseTool):
    """Tool MCP untuk memverifikasi validitas sesi aktif SRIKANDI."""

    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="srikandi_check_session",
            description="Memeriksa apakah sesi browser untuk profil akun SRIKANDI tertentu masih aktif dan valid.",
            parameters=[
                ToolParameter("profile_id", "string", "ID profil akun (default: 'default')", required=False, default="default"),
            ],
            returns="JSON status validitas sesi"
        )

    async def execute(self, task: Task) -> TaskResult:
        payload = task.payload
        profile_id = payload.get("profile_id", "default")
        try:
            res = await srikandi_auth_manager.check_session_validity(profile_id=profile_id)
            return TaskResult(task_id=task.id, status="success", data=res)
        except Exception as e:
            return TaskResult(task_id=task.id, status="error", error=str(e))


@register_tool
class SrikandiFetchSuratTool(BaseTool):
    """Tool MCP untuk mengekstrak daftar surat/disposisi dari SRIKANDI."""

    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="srikandi_fetch_surat",
            description="Mengekstrak metadata surat masuk, surat keluar, disposisi, atau naskah dinas dari SRIKANDI.",
            parameters=[
                ToolParameter("module", "string", "Modul target: surat_masuk, surat_keluar, disposisi, naskah_dinas", required=False, default="surat_masuk"),
                ToolParameter("profile_id", "string", "ID profil akun yang digunakan", required=False, default="default"),
                ToolParameter("max_pages", "integer", "Jumlah halaman maksimal yang di-scrape", required=False, default=1),
                ToolParameter("search_query", "string", "Kata kunci pencarian spesifik", required=False, default=None),
            ],
            returns="JSON daftar surat hasil ekstraksi"
        )

    async def execute(self, task: Task) -> TaskResult:
        payload = task.payload
        module = payload.get("module", "surat_masuk")
        profile_id = payload.get("profile_id", "default")
        max_pages = payload.get("max_pages", 1)
        search_query = payload.get("search_query")

        try:
            res = await srikandi_scraper.fetch_documents(
                module=module,
                profile_id=profile_id,
                max_pages=max_pages,
                search_query=search_query,
            )
            if res.get("success"):
                return TaskResult(task_id=task.id, status="success", data=res)
            else:
                return TaskResult(task_id=task.id, status="error", error=res.get("error", "Ekstraksi gagal"))
        except Exception as e:
            return TaskResult(task_id=task.id, status="error", error=str(e))


@register_tool
class SrikandiDownloadSuratTool(BaseTool):
    """Tool MCP untuk mengunduh lampiran file surat PDF dari SRIKANDI."""

    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="srikandi_download_surat",
            description="Mengunduh file PDF lampiran surat SRIKANDI ke direktori terisolasi storage/documents/srikandi/.",
            parameters=[
                ToolParameter("url", "string", "URL unduhan dokumen/lampiran"),
                ToolParameter("profile_id", "string", "ID profil akun", required=False, default="default"),
                ToolParameter("nomor_naskah", "string", "Nomor naskah dinas/surat untuk penamaan file", required=False, default="doc"),
            ],
            returns="JSON info file terunduh dan hash SHA-256"
        )

    async def execute(self, task: Task) -> TaskResult:
        payload = task.payload
        url = payload.get("url")
        if not url:
            return TaskResult(task_id=task.id, status="error", error="Parameter 'url' wajib diisi.")

        profile_id = payload.get("profile_id", "default")
        nomor_naskah = payload.get("nomor_naskah", "doc")

        try:
            res = await srikandi_downloader.download_attachment_by_url(
                url=url,
                profile_id=profile_id,
                nomor_naskah=nomor_naskah
            )
            if res.get("success"):
                return TaskResult(task_id=task.id, status="success", data=res)
            else:
                return TaskResult(task_id=task.id, status="error", error=res.get("error", "Unduhan gagal"))
        except Exception as e:
            return TaskResult(task_id=task.id, status="error", error=str(e))


@register_tool
class SrikandiSyncDatabaseTool(BaseTool):
    """Tool MCP untuk mengekstrak dan langsung menyinkronkan data surat SRIKANDI ke database."""

    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="srikandi_sync_database",
            description="Ekstraksi batch surat SRIKANDI dan langsung menyimpannya ke database PostgreSQL/SQLite.",
            parameters=[
                ToolParameter("module", "string", "Modul target: surat_masuk, surat_keluar, disposisi", required=False, default="surat_masuk"),
                ToolParameter("profile_id", "string", "ID profil akun", required=False, default="default"),
                ToolParameter("max_pages", "integer", "Jumlah halaman", required=False, default=1),
                ToolParameter("download_attachments", "boolean", "Opsi unduh otomatis PDF lampiran", required=False, default=False),
            ],
            returns="JSON ringkasan sinkronisasi database"
        )

    async def execute(self, task: Task) -> TaskResult:
        payload = task.payload
        module = payload.get("module", "surat_masuk")
        profile_id = payload.get("profile_id", "default")
        max_pages = payload.get("max_pages", 1)
        download_attachments = payload.get("download_attachments", False)

        try:
            # 1. Scrape
            scrape_res = await srikandi_scraper.fetch_documents(
                module=module,
                profile_id=profile_id,
                max_pages=max_pages,
            )
            if not scrape_res.get("success"):
                return TaskResult(task_id=task.id, status="error", error=scrape_res.get("error"))

            records = scrape_res.get("data", [])

            # 2. Download attachments jika diminta
            if download_attachments and records:
                for r in records:
                    urls = r.get("lampiran_urls", [])
                    if urls:
                        down_res = await srikandi_downloader.download_attachment_by_url(
                            url=urls[0],
                            profile_id=profile_id,
                            nomor_naskah=r.get("nomor_naskah", "doc")
                        )
                        if down_res.get("success"):
                            r["local_file_path"] = down_res.get("file_path")

            # 3. Sync to DB
            sync_res = srikandi_db_sync.sync_records(
                records=records,
                profile_id=profile_id,
                module=module
            )

            return TaskResult(
                task_id=task.id,
                status="success",
                data={
                    "scrape_summary": {
                        "total_extracted": len(records),
                        "pages": max_pages,
                        "module": module,
                        "profile_id": profile_id,
                    },
                    "db_sync": sync_res
                }
            )
        except Exception as e:
            return TaskResult(task_id=task.id, status="error", error=str(e))
