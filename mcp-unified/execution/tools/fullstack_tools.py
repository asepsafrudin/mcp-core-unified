"""
execution/tools/fullstack_tools.py — MCP tool: fullstack_run (TASK-172).

Menjembatani `FullstackAgenticWorkflow` (smolagents; servers/orchestrator/workflows)
ke registry MCP Unified. Lazy-import agar hub tidak bergantung keras pada paket
`servers/` (bila tak tersedia → status `unavailable`, bukan error senyap).
"""
import json
import sys
import time
from pathlib import Path

from execution.registry import registry
from execution.middleware import EnforcementMiddleware

WORKSPACE_ROOT = Path("/home/aseps/MCP").resolve()
_PHASES = ["ARCHITECT", "BACKEND", "FRONTEND", "QA", "DONE"]


def _load_workflow_class():
    if str(WORKSPACE_ROOT) not in sys.path:
        sys.path.insert(0, str(WORKSPACE_ROOT))
    from servers.orchestrator.workflows.fullstack_graph import FullstackAgenticWorkflow

    return FullstackAgenticWorkflow


@registry.register(category="code")
def fullstack_run(task_description: str, hitl_enabled: bool = False, dry_run: bool = False) -> str:
    """
    Menjalankan workflow fullstack agentic (ARCHITECT → BACKEND → FRONTEND → QA).

    Args:
        task_description: Deskripsi kebutuhan proyek.
        hitl_enabled: Aktifkan gerbang approval manusia (HITL) bila didukung.
        dry_run: Bila True, hanya mengembalikan daftar fase (tanpa eksekusi).

    Mengembalikan JSON: status, current_phase, ringkasan artefak per fase,
    phase_metrics, errors, dan durasi. Jalur nyata memakai `FullstackAgenticWorkflow`.
    """
    trace_id = EnforcementMiddleware.generate_trace_id()
    start = time.time()
    try:
        if not task_description or len(task_description.strip()) < 10:
            return json.dumps({"status": "rejected", "summary": "task_description terlalu pendek (min 10 karakter)."}, indent=2)

        if dry_run:
            return json.dumps({
                "status": "dry_run",
                "phases": _PHASES,
                "summary": "Rencana workflow fullstack (tanpa eksekusi).",
            }, indent=2)

        try:
            Workflow = _load_workflow_class()
        except Exception as e:
            return json.dumps({"status": "unavailable", "summary": f"FullstackAgenticWorkflow tidak tersedia: {type(e).__name__}: {e}"}, indent=2)

        wf = Workflow(hitl_enabled=hitl_enabled)
        state = wf.execute_workflow(task_description)
        duration_ms = round((time.time() - start) * 1000, 2)

        status = "ok" if not state.recent_errors else "completed_with_errors"
        EnforcementMiddleware.audit_log(
            trace_id=trace_id, tool_name="fullstack_run", status=status,
            details={"current_phase": state.current_phase, "errors": len(state.recent_errors)},
        )

        return json.dumps({
            "status": status,
            "current_phase": state.current_phase,
            "blueprint_chars": len(state.blueprint or ""),
            "backend_chars": len(state.backend_summary or ""),
            "frontend_chars": len(state.frontend_summary or ""),
            "qa_chars": len(state.qa_result or ""),
            "errors": state.recent_errors,
            "phase_metrics": state.phase_metrics,
            "workflow_duration_seconds": state.total_execution_time_seconds,
            "duration_ms": duration_ms,
            "summary": f"Workflow selesai (phase={state.current_phase}, errors={len(state.recent_errors)}).",
        }, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "summary": f"{type(e).__name__}: {e}"}, indent=2)
