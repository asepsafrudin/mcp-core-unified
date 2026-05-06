import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, List

import psutil  # type: ignore

# Avoid shadowing stdlib and fix path injection
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from memory.working import working_memory
from memory.longterm import initialize_db
from execution.registry import registry
from security.scanner import SecurityScanner, Severity

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    status: str
    checks: Dict[str, Any]
    timestamp: str
    duration_ms: float


class HealthCheckService:
    def __init__(self, required_tools: List[str] | None = None):
        self.required_tools = required_tools or [
            "semantic_analyze_file",
            "ai_semantic_analyze",
        ]
        self.enforce_tools = os.getenv("HEALTH_CHECK_ENFORCE_TOOLS", "false").lower() == "true"

    def _check_process(self) -> Dict[str, Any]:
        current_pid = os.getpid()
        try:
            process = psutil.Process(current_pid)
            return {
                "ok": process.is_running(),
                "pid": current_pid,
                "status": process.status(),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "pid": current_pid}

    async def _check_db(self) -> Dict[str, Any]:
        try:
            await initialize_db()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _check_redis(self) -> Dict[str, Any]:
        try:
            await working_memory.connect()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _check_tools(self) -> Dict[str, Any]:
        available = registry.list_tools()
        if not available:
            return {"ok": True, "skipped": True, "reason": "registry empty"}
        missing = []
        for tool_name in self.required_tools:
            if registry.get_tool(tool_name) is None:
                missing.append(tool_name)
        if missing and not self.enforce_tools:
            return {
                "ok": True,
                "skipped": True,
                "missing": missing,
                "reason": "tools not enforced",
            }
        return {"ok": len(missing) == 0, "missing": missing}

    def _check_security(self) -> Dict[str, Any]:
        try:
            # Menggunakan direktori saat ini (mcp-unified)
            base_dir = os.getcwd()
            scanner = SecurityScanner(base_dir)
            vulnerabilities = scanner.scan_directory()
            
            critical_high = [v for v in vulnerabilities if v.severity in [Severity.CRITICAL.value, Severity.HIGH.value]]
            
            return {
                "ok": len(critical_high) == 0,
                "total_vulnerabilities": len(vulnerabilities),
                "critical_high_count": len(critical_high),
                "status": "SECURE" if len(critical_high) == 0 else "VULNERABLE"
            }
        except Exception as exc:
            logger.error(f"Security check failed: {exc}")
            return {"ok": False, "error": str(exc)}
    def _check_efficiency(self) -> Dict[str, Any]:
        try:
            import subprocess
            # Use serena audit to find potential redundancies
            cmd = ["/home/aseps/MCP/services/serena/.venv/bin/python", "/home/aseps/MCP/scripts/serena_audit.py"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            # Additional check: Scan for residuals
            scripts_dir=os.getenv("SCRIPTS_DIR", "/home/aseps/MCP/scripts" if not os.getenv("CI") else "DUMMY")
            residuals = [f for f in os.listdir(scripts_dir) if f.endswith(('.json', '.draft', '_backup.py'))]
            
            status = "OPTIMIZED"
            if "REDUNDANCY WARNING" in result.stdout or residuals:
                status = "REDUNDANT_FOUND"
                
            return {
                "ok": status == "OPTIMIZED",
                "status": status,
                "residual_count": len(residuals),
                "details": result.stdout if result.returncode == 0 else result.stderr
            }
        except Exception as exc:
            logger.error(f"Efficiency check failed: {exc}")
            return {"ok": False, "error": str(exc)}

    def _check_skill_adoption(self) -> Dict[str, Any]:
        """Check if scripts in /scripts are using shared skills where appropriate."""
        try:
            scripts_dir=os.getenv("SCRIPTS_DIR", "/home/aseps/MCP/scripts" if not os.getenv("CI") else "DUMMY")
            adoption_stats = {"ocr_processor": {"total": 0, "adopted": 0, "missing": []}}
            
            for f in os.listdir(scripts_dir):
                if not f.endswith(".py") or f in ['fast_track.py', 'consolidate_scripts.py']:
                    continue
                
                path = os.path.join(scripts_dir, f)
                with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()
                    
                # Heuristic: if it mentions OCR or Vision but doesn't import skills.ocr.processor
                if ("ocr" in f.lower() or "vision" in f.lower()) and "import" in content:
                    adoption_stats["ocr_processor"]["total"] += 1
                    if "skills.ocr.processor" in content or "OCRProcessor" in content:
                        adoption_stats["ocr_processor"]["adopted"] += 1
                    else:
                        adoption_stats["ocr_processor"]["missing"].append(f)
            
            total_applicable = adoption_stats["ocr_processor"]["total"]
            adopted = adoption_stats["ocr_processor"]["adopted"]
            adoption_rate = (adopted / total_applicable * 100) if total_applicable > 0 else 100
            
            return {
                "ok": adoption_rate >= 80,
                "adoption_rate": adoption_rate,
                "missing_adoption": adoption_stats["ocr_processor"]["missing"],
                "status": "HIGH_ADOPTION" if adoption_rate >= 80 else "LOW_ADOPTION"
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def run(self) -> HealthCheckResult:
        start = time.time()
        process_check = self._check_process()
        db_check = await self._check_db()
        redis_check = await self._check_redis()
        tools_check = self._check_tools()
        security_check = self._check_security()
        efficiency_check = self._check_efficiency()
        skill_check = self._check_skill_adoption()

        checks = {
            "process": process_check,
            "database": db_check,
            "redis": redis_check,
            "tools": tools_check,
            "security": security_check,
            "efficiency": efficiency_check,
            "skill_adoption": skill_check,
        }
        status = "OK" if all(item.get("ok") for item in checks.values()) else "FAIL"
        duration_ms = (time.time() - start) * 1000

        return HealthCheckResult(
            status=status,
            checks=checks,
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            duration_ms=duration_ms,
        )