import asyncio
import logging
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, time as time_cls
from typing import Dict, Any, List

from core.monitoring.health_check import HealthCheckService
from core.monitoring.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class SelfHealingAgent:
    def __init__(
        self,
        health_check: HealthCheckService | None = None,
        notifier: TelegramNotifier | None = None,
        daily_time: str | None = None,
        recovery_scripts: List[str] | None = None,
    ):
        self.health_check = health_check or HealthCheckService()
        self.notifier = notifier or TelegramNotifier()
        self.daily_time = daily_time or os.getenv("SELF_HEALING_DAILY_TIME", "00:05")
        self.recovery_scripts = recovery_scripts or self._load_recovery_scripts()

    def _load_recovery_scripts(self) -> List[str]:
        scripts_env = os.getenv("SELF_HEALING_RECOVERY_SCRIPTS", "")
        return [s.strip() for s in scripts_env.split(",") if s.strip()]

    def _should_run_now(self, now: datetime) -> bool:
        target_time = datetime.strptime(self.daily_time, "%H:%M").time()
        return now.time().hour == target_time.hour and now.time().minute == target_time.minute

    async def run_once(self) -> Dict[str, Any]:
        result = await self.health_check.run()
        payload = asdict(result)

        if result.status != "OK":
            recovery_result = await self._recover(payload)
            payload["recovery"] = recovery_result

        self._notify(payload)
        return payload

    async def _recover(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        actions = []
        for script in self.recovery_scripts:
            try:
                logger.info("Running recovery script: %s", script)
                completed = subprocess.run(script, shell=True, capture_output=True, text=True)
                actions.append({
                    "script": script,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout[-2000:],
                    "stderr": completed.stderr[-2000:],
                })
            except Exception as exc:
                actions.append({"script": script, "error": str(exc)})

        # Re-check health after recovery
        post_check = await self.health_check.run()
        return {
            "actions": actions,
            "post_check": asdict(post_check),
        }

    def _notify(self, payload: Dict[str, Any]) -> None:
        status = payload.get("status", "UNKNOWN")
        timestamp = payload.get("timestamp")
        duration = payload.get("duration_ms")
        msg_lines = [
            f"<b>MCP Health Check</b>",
            f"Status: <b>{status}</b>",
            f"Timestamp: {timestamp}",
            f"Duration: {duration:.2f} ms" if duration is not None else "Duration: -",
        ]

        if payload.get("recovery"):
            msg_lines.append("Recovery executed")

        self.notifier.send_message("\n".join(msg_lines))

    async def run_daily(self) -> None:
        last_run_date = None
        while True:
            now = datetime.now()
            if self._should_run_now(now) and last_run_date != now.date():
                last_run_date = now.date()
                await self.run_once()
                await asyncio.sleep(60)
            await asyncio.sleep(30)