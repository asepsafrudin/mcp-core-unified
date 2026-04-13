#!/usr/bin/env python3
"""
Daily Report Service - Notifikasi Telegram untuk Cron Jobs

Service untuk mengirim laporan harian status cron jobs ke Telegram.
Standalone - tidak bergantung pada modul telegram lain.

Usage:
    python3 daily_report_service.py
    
Cron:
    30 23 * * * cd /home/aseps/MCP/mcp-unified/integrations/telegram && \
        python3 services/daily_report_service.py
"""

import os
import sys
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, cast
import asyncio

# Load .env from parent directory
def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key, value)

load_env()


class JobReport:
    """Represents a single job report."""
    
    def __init__(self, job_id: str, name: str, schedule: str):
        self.job_id = job_id
        self.name = name
        self.schedule = schedule
        self.status = "⚪ Unknown"
        self.last_run = None
        self.details = ""
        self.error_count = 0
        self.success_count = 0


class DailyReportService:
    """Service untuk laporan harian job rutin."""
    
    # Log directories
    LOG_DIRS = {
        "workspace": "/home/aseps/logs",
        "onedrive": "/home/aseps/MCP/logs/onedrive",
        "extractor": "/home/aseps/logs/extractor",
    }
    
    # Job definitions
    JOBS = {
        "batch_scanner": {
            "name": "🔍 Batch Scanner",
            "log_file": "scanner.log",
            "log_dir": "workspace",
            "pattern": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
            "success_pattern": r"completed|success|finished|selesai|berhasil",
            "schedule": "Setiap 30 menit"
        },
        "extraction_pipeline": {
            "name": "📥 Extraction Pipeline",
            "log_file": "extraction.log",
            "log_dir": "workspace",
            "pattern": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
            "success_pattern": r"completed|success|extracted|selesai|berhasil",
            "schedule": "Setiap 35 menit"
        },
        "backup_supabase": {
            "name": "💾 Backup Supabase",
            "log_file": "backup.log",
            "log_dir": "workspace",
            "pattern": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
            "success_pattern": r"✅|successful|completed|selesai|berhasil",
            "error_pattern": r"❌|ERROR|gagal|failed",
            "schedule": "02:00 Harian"
        },
        "onedrive_sync": {
            "name": "☁️ OneDrive PUU Sync",
            "log_file": "cron_sync_*.log",
            "log_dir": "onedrive",
            "pattern": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
            "success_pattern": r"completed|success|indexed|selesai|berhasil",
            "schedule": "23:00 Harian"
        },
        "production_extraction": {
            "name": "🏭 Production Extraction",
            "log_file": "cron.log",
            "log_dir": "extractor",
            "pattern": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
            "success_pattern": r"completed|success|extracted|selesai|berhasil|BATCH SUMMARY|items",
            "schedule": "06:00 Harian"
        }
    }
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.report_dir = Path("/home/aseps/MCP/logs/daily_reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    def get_today_datetime(self) -> datetime:
        """Get today's datetime at midnight."""
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def parse_log_timestamp(self, line: str, pattern: str) -> Optional[datetime]:
        """Extract timestamp from log line."""
        match = re.search(pattern, line)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
            except:
                pass
        return None
    
    def analyze_job_log(self, job_config: Dict) -> JobReport:
        """Analyze log file for a specific job."""
        report = JobReport(
            job_id="",
            name=job_config["name"],
            schedule=job_config["schedule"]
        )
        
        log_dir = self.LOG_DIRS.get(job_config["log_dir"], "")
        if not log_dir:
            report.status = "⚪ No log dir"
            return report
        
        log_path = Path(log_dir)
        if not log_path.exists():
            report.status = "⚪ No logs"
            return report
        
        log_pattern = job_config["log_file"]
        if "*" in log_pattern:
            log_files = sorted(log_path.glob(log_pattern), key=lambda x: x.stat().st_mtime, reverse=True)
        else:
            log_file = log_path / log_pattern
            log_files = [log_file] if log_file.exists() else []
        
        if not log_files:
            report.status = "⚪ No log file"
            return report
        
        today = self.get_today_datetime()
        tomorrow = today + timedelta(days=1)
        
        for log_file in log_files[:3]:
            try:
                # Check file modification time as fallback
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                file_is_today = today <= mtime < tomorrow
                
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                for line in lines:
                    timestamp = self.parse_log_timestamp(line, job_config["pattern"])
                    
                    # If line has timestamp, use it
                    if timestamp and today <= timestamp < tomorrow:
                        report.last_run = timestamp
                        
                    # Target patterns can be on lines without timestamps (e.g. summary blocks)
                    # We accept them if the line has a valid today's timestamp OR 
                    # if we found ANY today's timestamp in this file OR
                    # if the file itself was modified today and we are looking at the latest lines.
                    if (timestamp and today <= timestamp < tomorrow) or (not timestamp and file_is_today):
                        if re.search(job_config.get("success_pattern", ""), line, re.IGNORECASE):
                            report.success_count += 1
                        
                        if "error_pattern" in job_config and re.search(job_config["error_pattern"], line, re.IGNORECASE):
                            report.error_count += 1
                            report.details += f"❌ {line.strip()[:100]}\n"
                
                # If we didn't find a timestamp in the text but file is today,
                # set last_run to file mtime so it doesn't show as "Not run"
                if not report.last_run and file_is_today:
                    report.last_run = mtime
                
            except Exception as e:
                report.details += f"Error reading {log_file}: {e}\n"
        
        if report.error_count > 0:
            report.status = f"❌ Failed ({report.error_count} errors)"
        elif report.success_count > 0:
            report.status = f"✅ Success ({report.success_count} OK)"
        elif report.last_run:
            report.status = "🟡 Ran (status unclear)"
        else:
            report.status = "⚪ Not run today"
        
        return report
    
    async def get_ltm_tasks(self) -> str:
        """Fetch active tasks from LTM database."""
        try:
            import psycopg
            from psycopg.rows import dict_row
            
            # Use credentials from environment or default to local
            conn_str = "host={} port={} dbname={} user={} password={}".format(
                os.getenv("POSTGRES_SERVER", os.getenv("PG_HOST", "localhost")),
                os.getenv("POSTGRES_PORT", os.getenv("PG_PORT", "5433")),
                os.getenv("POSTGRES_DB", os.getenv("PG_DATABASE", "mcp_knowledge")),
                os.getenv("POSTGRES_USER", os.getenv("PG_USER", "mcp_user")),
                os.getenv("POSTGRES_PASSWORD", os.getenv("PG_PASSWORD", ""))
            )
            
            with psycopg.connect(conn_str, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    # 1. Try project_memories first
                    try:
                        cur.execute("""
                            SELECT content
                            FROM project_memories
                            WHERE project_name = 'MCP Unified Tasks'
                        """)
                        project_row = cast(Any, cur.fetchone())

                        if project_row and project_row.get("content"):
                            content = project_row["content"]
                            if isinstance(content, str):
                                try:
                                    content = json.loads(content)
                                except:
                                    pass

                            if isinstance(content, dict):
                                metrics = content.get("metrics", {})
                                current_tasks = content.get("current_tasks", [])
                                summary_lines = [
                                    (
                                        "   • Ringkasan: "
                                        f"{metrics.get('active_tasks', 0)} aktif, "
                                        f"{metrics.get('completed_tasks', 0)} selesai"
                                    )
                                ]
                                summary_lines.extend(f"   • {task}" for task in current_tasks[:3])
                                return "\n".join(summary_lines)
                    except Exception as table_err:
                        # Tabel mungkin belum ada, lanjut ke fallback
                        pass

                    # 2. Fallback to memories table
                    cur.execute("""
                        SELECT key, content, metadata
                        FROM memories
                        WHERE namespace = 'mcp_tasks'
                        ORDER BY created_at DESC
                        LIMIT 3
                    """)
                    rows = cur.fetchall()
                    
                    if not rows:
                        return "   • Tidak ada tugas aktif."
                    
                    task_lines = []
                    for row in cast(List[Any], rows):
                        meta = row['metadata'] if isinstance(row['metadata'], dict) else json.loads(row['metadata'] or '{}')
                        progress = meta.get('progress', 0)
                        status = meta.get('status', 'TODO')
                        task_lines.append(f"   • {row['key']}: {progress}% - {status}")
                    
                    return "\n".join(task_lines)
        except Exception as e:
            return f"   (Gagal mengambil data LTM: {e})"

    async def generate_report(self) -> Tuple[str, List[JobReport]]:
        """Generate the daily report — menggunakan output /dashboard."""
        try:
            import sys as _sys
            _sys.path.insert(0, "/home/aseps/MCP/mcp-unified")
            from services.correspondence_dashboard import CorrespondenceDashboard
            message = CorrespondenceDashboard().get_recent_summary()
            return message, []
        except Exception as e:
            now = datetime.now()
            message = (
                f"📊 *DASHBOARD KORESPONDENSI PUU*\n"
                f"_{now.strftime('%d %B %Y, %H:%M')} WIB_\n\n"
                f"⚠️ Gagal memuat data: `{str(e)}`\n"
            )
            return message, []

    async def _generate_report_legacy(self) -> Tuple[str, List[JobReport]]:
        """(Legacy) Job cron status report — tidak digunakan lagi."""
        now = datetime.now()
        date_str = now.strftime("%d %B %Y")

        reports = []
        for job_id, config in self.JOBS.items():
            report = self.analyze_job_log(config)
            report.job_id = job_id
            reports.append(report)

        success_count = sum(1 for r in reports if "✅" in r.status)
        failed_count = sum(1 for r in reports if "❌" in r.status)
        unknown_count = len(reports) - success_count - failed_count
        
        # Get LTM tasks
        ltm_status = await self.get_ltm_tasks()
        
        message = f"""📊 *LAPORAN HARIAN JOB RUTIN*
📅 {date_str}

*Ringkasan Status:*
✅ Berhasil: {success_count}
❌ Gagal: {failed_count}
⚪ Lainnya: {unknown_count}

*Detail Job:*
"""
        
        for report in reports:
            last_run_str = report.last_run.strftime("%H:%M") if report.last_run else "—"
            message += f"\n{report.name}\n"
            message += f"├ Status: {report.status}\n"
            message += f"├ Jadwal: {report.schedule}\n"
            message += f"└ Terakhir: {last_run_str}\n"
        
        message += f"""
*Status Task (LTM):*
{ltm_status}

*Catatan:*
_• Laporan ini dibuat otomatis setiap malam_
_• Waktu dalam format WIB (UTC+7)_

💡 Gunakan `/status` untuk cek real-time status.
"""
        
        return message, reports
    
    async def send_telegram_message(self, message: str) -> bool:
        """Send message to Telegram."""
        if not self.bot_token or not self.chat_id:
            print("⚠️  ***REMOVED_TOKEN***atau TELEGRAM_CHAT_ID tidak diset")
            print("📝 Pesan yang akan dikirim:")
            print("=" * 50)
            print(message)
            print("=" * 50)
            return False
        
        try:
            import aiohttp
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            print(f"✅ Laporan berhasil dikirim ke Telegram")
                            return True
                        else:
                            print(f"❌ Telegram API error: {result.get('description')}")
                    else:
                        print(f"❌ HTTP error {response.status}")
                        
        except ImportError:
            print("⚠️ aiohttp tidak terinstall. Install dengan: pip install aiohttp")
            print("📝 Pesan:")
            print(message)
        except Exception as e:
            print(f"❌ Error: {e}")
        
        return False
    
    def save_report_json(self, reports: List[JobReport]):
        """Save report to JSON file for history."""
        today = datetime.now().strftime("%Y%m%d")
        report_file = self.report_dir / f"report_{today}.json"
        
        data = {
            "date": datetime.now().isoformat(),
            "jobs": [
                {
                    "id": r.job_id,
                    "name": r.name,
                    "status": r.status,
                    "schedule": r.schedule,
                    "last_run": r.last_run.isoformat() if r.last_run else None,
                    "success_count": r.success_count,
                    "error_count": r.error_count,
                    "details": r.details
                }
                for r in reports
            ]
        }
        
        with open(report_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Laporan disimpan ke: {report_file}")
    
    async def send_daily_report(self) -> bool:
        """Generate and send daily dashboard report ke Telegram."""
        print("📊 Daily Dashboard Report")
        print("=" * 50)
        print(f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        message, _ = await self.generate_report()

        success = await self.send_telegram_message(message)

        if not success:
            print("\n📋 PESAN:")
            print(message)

        print("\n✅ Selesai!")
        return success


async def main():
    """Main function for CLI usage."""
    service = DailyReportService()
    success = await service.send_daily_report()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
