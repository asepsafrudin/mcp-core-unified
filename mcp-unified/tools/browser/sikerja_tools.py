"""
SIKERJA Kemendagri Automation Tools Suite
Menyediakan tool MCP native untuk:
1. sikerja_sync_sheet: Mengunduh data tab bulanan dari Google Spreadsheet 'Laporan sikerja 2026'.
2. sikerja_get_status: Memeriksa ringkasan status login dan transaksi (Belum diperiksa, Disetujui, Ditolak).
3. sikerja_inject_laporan: Menginjeksi batch data laporan kegiatan dengan validasi jam selesai (WIB).
"""

from __future__ import annotations

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("sikerja_tools")

# Ensure core path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from core.task import Task, TaskResult

SA_FILE = "/home/aseps/MCP/config/credentials/google/asepsafrudin/sa-new-mcp-unified.json"
SPREADSHEET_ID="1Zqgs66mY8SR_5FYEWUcSDTB31M7P1h-eXTk-pgH42zk"
DEFAULT_WORKSPACE_DIR = "/home/aseps/MCP/workspace/sikerja_kemendagri/data"
ENV_PATH = "/home/aseps/MCP/workspace/sikerja_kemendagri/.env"


@register_tool
class SikerjaSyncSheetTool(BaseTool):
    """Tool MCP untuk mengunduh data tab Google Spreadsheet 'Laporan sikerja 2026' ke berkas JSON lokal."""

    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="sikerja_sync_sheet",
            description="Mengunduh data tab bulan tertentu dari Google Spreadsheet 'Laporan sikerja 2026' ke JSON lokal.",
            parameters=[
                ToolParameter(
                    name="tab_name",
                    type="string",
                    description="Nama tab yang ingin disinkronkan, misal: 'Oktober', 'September', 'November'",
                    required=True,
                ),
                ToolParameter(
                    name="output_path",
                    type="string",
                    description="Path lokasi penyimpanan JSON opsional. Default: workspace/Gdrive-sync/sikerja/{tab_name}.json",
                    required=False,
                )
            ],
            returns="JSON ringkasan data yang berhasil disinkronkan."
        )

    async def execute(self, task: Task) -> TaskResult:
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            tab_name = task.payload.get("tab_name", "Oktober")
            output_path = task.payload.get("output_path")
            if not output_path:
                os.makedirs(DEFAULT_WORKSPACE_DIR, exist_ok=True)
                output_path = os.path.join(DEFAULT_WORKSPACE_DIR, f"{tab_name.lower()}.json")

            creds = service_account.Credentials.from_service_account_file(
                SA_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
            )
            service = build("sheets", "v4", credentials=creds)

            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{tab_name}!A1:F300"
            ).execute()

            values = result.get("values", [])
            data = {
                "success": True,
                "spreadsheet_id": SPREADSHEET_ID,
                "tab": tab_name,
                "values": values,
                "total_rows": len(values)
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return TaskResult.success_result(
                task_id=task.id,
                data={
                    "tab": tab_name,
                    "total_rows": len(values),
                    "file_path": output_path,
                    "message": f"Berhasil menyinkronkan {len(values)} baris dari tab {tab_name}."
                }
            )
        except Exception as e:
            logger.error(f"Error pada sikerja_sync_sheet: {e}")
            return TaskResult.failure_result(task_id=task.id, error=str(e))



@register_tool
class SikerjaGetStatusTool(BaseTool):
    """Tool MCP untuk mengecek status transaksi di SIKERJA Kemendagri."""

    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="sikerja_get_status",
            description="Memeriksa status login dan jumlah transaksi saat ini di portal SIKERJA Kemendagri (Belum diperiksa, Disetujui, Ditolak).",
            parameters=[],
            returns="Ringkasan jumlah laporan di tiap tahapan SIKERJA."
        )

    async def execute(self, task: Task) -> TaskResult:
        try:
            from dotenv import load_dotenv
            from playwright.async_api import async_playwright

            load_dotenv(ENV_PATH)
            username = os.environ.get("SIKERJA_USER_ASEP")
            password = os.environ.get("SIKERJA_PASSWORD_ASEP")

            if not username or not password:
                return TaskResult(task_id=task.id, status="error", error="Kredensial SIKERJA_USER_ASEP / SIKERJA_PASSWORD_ASEP tidak ditemukan di environment.")

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(ignore_https_errors=True)
                
                await page.goto("https://sikerja.kemendagri.go.id/admin", wait_until="domcontentloaded", timeout=60000)
                await page.fill("#nip", username)
                await page.fill("#password", password)
                await page.click("#btnlogin")
                await page.wait_for_timeout(4000)

                await page.goto("https://sikerja.kemendagri.go.id/transaksi/home2", wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(2000)

                status_summary = await page.evaluate("""() => {
                    let belum = $('#tab_belum_diperiksa .badge').text().trim() || '0';
                    let setuju = $('#tab_disetujui .badge').text().trim() || '0';
                    let tolak = $('#tab_ditolak .badge').text().trim() || '0';
                    return {
                        belum_diperiksa: belum,
                        disetujui: setuju,
                        ditolak: tolak,
                        current_url: window.location.href,
                        title: document.title
                    };
                }""")
                await browser.close()

                return TaskResult.success_result(
                    task_id=task.id,
                    data=status_summary
                )
        except Exception as e:
            logger.error(f"Error pada sikerja_get_status: {e}")
            return TaskResult.failure_result(task_id=task.id, error=str(e))



@register_tool
class SikerjaInjectLaporanTool(BaseTool):
    """Tool MCP untuk menginjeksi batch kegiatan dari JSON ke portal SIKERJA Kemendagri."""

    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="sikerja_inject_laporan",
            description="Menginjeksi baris kegiatan dari dataset JSON ke portal SIKERJA Kemendagri secara aman dengan Future-Date Guard (WIB).",
            parameters=[
                ToolParameter(
                    name="json_path",
                    type="string",
                    description="Path berkas JSON yang memuat baris kegiatan. Misal: '/home/aseps/MCP/workspace/Gdrive-sync/sikerja/oktober.json'",
                    required=True,
                ),
                ToolParameter(
                    name="dry_run",
                    type="boolean",
                    description="Jika true, hanya melakukan simulasi validasi data tanpa melakukan penyimpanan ke server.",
                    required=False,
                )
            ],
            returns="Hasil audit dan jumlah entri yang berhasil diinjeksi."
        )

    async def execute(self, task: Task) -> TaskResult:
        try:
            from dotenv import load_dotenv
            from playwright.async_api import async_playwright

            json_path = task.payload.get("json_path")
            dry_run = task.payload.get("dry_run", False)

            if not os.path.exists(json_path):
                return TaskResult(task_id=task.id, status="error", error=f"Berkas JSON tidak ditemukan: {json_path}")

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            values = data.get("values", [])
            if not values:
                return TaskResult(task_id=task.id, status="error", error="Berkas JSON kosong atau tidak memiliki array values.")

            wib_tz = timezone(timedelta(hours=7))
            now_wib = datetime.now(wib_tz)

            records = []
            future_skipped = 0
            for row in values[1:]:
                if not row or not any(str(x).strip() for x in row):
                    continue
                uraian = row[0].strip() if len(row) > 0 else ""
                mulai = row[1].strip() if len(row) > 1 else ""
                selesai = row[2].strip() if len(row) > 2 else ""
                ket = row[3].strip() if len(row) > 3 else ""
                perbaikan = row[4].strip() if len(row) > 4 else ket
                
                final_ket = perbaikan.strip() if perbaikan.strip() else ket.strip()
                
                # ATURAN KETAT: Dilarang mengisi jika sumber data kosong
                if not uraian or not final_ket or not mulai or not selesai:
                    continue


                try:
                    date_part, time_mulai = mulai.split(" ")
                    _, time_selesai = selesai.split(" ")
                    time_mulai = ":".join([p.zfill(2) for p in time_mulai.split(":")[:2]])
                    time_selesai = ":".join([p.zfill(2) for p in time_selesai.split(":")[:2]])
                    y, m, d = date_part.split("-")
                    formatted_date = f"{d}-{m}-{y}"

                    record_dt = datetime.strptime(f"{formatted_date} {time_selesai}", "%d-%m-%Y %H:%M").replace(tzinfo=wib_tz)
                    if record_dt > now_wib:
                        future_skipped += 1
                        continue
                except Exception:
                    continue

                records.append({
                    "uraian_tugas": uraian,
                    "tanggal": formatted_date,
                    "jam_mulai": time_mulai,
                    "jam_selesai": time_selesai,
                    "keterangan": final_ket
                })

            if dry_run:
                return TaskResult.success_result(
                    task_id=task.id,
                    data={
                        "dry_run": True,
                        "total_valid_ready": len(records),
                        "future_skipped": future_skipped,
                        "records_preview": records[:3]
                    }
                )


            load_dotenv(ENV_PATH)
            username = os.environ.get("SIKERJA_USER_ASEP")
            password = os.environ.get("SIKERJA_PASSWORD_ASEP")

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1280, "height": 720}, ignore_https_errors=True)

                await page.goto("https://sikerja.kemendagri.go.id/admin", wait_until="domcontentloaded", timeout=60000)
                await page.fill("#nip", username)
                await page.fill("#password", password)
                await page.click("#btnlogin")
                await page.wait_for_timeout(4000)

                # Ambil daftar yang sudah ada
                await page.goto("https://sikerja.kemendagri.go.id/transaksi/home2", wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(2000)
                try:
                    await page.click("#tab_belum_diperiksa a")
                    await page.wait_for_timeout(1000)
                except Exception:
                    pass

                existing_items = await page.evaluate("""() => {
                    let items = [];
                    $('#table_belum_diperiksa tbody tr').each(function() {
                        let tds = $(this).find('td');
                        if (tds.length >= 5) {
                            items.push({
                                tgl: tds.eq(1).text().trim().replace(/\\s+/g, ' '),
                                ket: tds.eq(4).text().trim().replace(/\\s+/g, ' ')
                            });
                        }
                    });
                    return items;
                }""")

                success_count = 0
                skip_count = 0
                fail_count = 0

                for record in records:
                    already = any(
                        record['tanggal'] in ex['tgl'] and (record['keterangan'][:30] in ex['ket'] or ex['ket'][:30] in record['keterangan'])
                        for ex in existing_items
                    )
                    if already:
                        skip_count += 1
                        continue

                    try:
                        await page.goto("https://sikerja.kemendagri.go.id/transaksi/home2/add", wait_until="domcontentloaded", timeout=60000)
                        u_text = record["uraian_tugas"]
                        await page.evaluate("""(text) => {
                            let uVal = $('#urtug option').filter(function() { return $(this).text().indexOf(text) !== -1; }).first().val();
                            if (!uVal) {
                                let kw = text.split(' ').slice(0, 4).join(' ');
                                uVal = $('#urtug option').filter(function() { return $(this).text().indexOf(kw) !== -1; }).first().val();
                            }
                            if (!uVal) uVal = $('#urtug option').eq(1).val();
                            if (uVal) $('#urtug').val(uVal).trigger('change');
                        }""", u_text)

                        try:
                            await page.wait_for_selector("#loadprosess", state="hidden", timeout=4000)
                        except Exception:
                            pass

                        await page.evaluate("""(params) => {
                            $('#tgl_mulai').val(params.tgl);
                            $('#tgl_selesai').val(params.tgl);
                            $('#jam_mulai').val(params.jm);
                            $('#jam_selesai').val(params.js);
                        }""", {"tgl": record["tanggal"], "jm": record["jam_mulai"], "js": record["jam_selesai"]})

                        await page.fill("textarea[name='ket_pekerjaan']", record["keterangan"])
                        await page.click("#btn_save")
                        await page.wait_for_timeout(3500)
                        success_count += 1
                    except Exception as e:
                        fail_count += 1
                        logger.warning(f"Gagal injeksi {record['tanggal']}: {e}")

                    await page.wait_for_timeout(2500)

                await browser.close()
                return TaskResult.success_result(
                    task_id=task.id,
                    data={
                        "total_valid_ready": len(records),
                        "future_skipped": future_skipped,
                        "success_injected": success_count,
                        "skipped_existing": skip_count,
                        "failed": fail_count
                    }
                )
        except Exception as e:
            logger.error(f"Error pada sikerja_inject_laporan: {e}")
            return TaskResult.failure_result(task_id=task.id, error=str(e))