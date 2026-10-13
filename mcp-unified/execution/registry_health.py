"""
execution/registry_health.py — Kesehatan registry & fail-fast opt-in (TASK-174).

Menyediakan snapshot kesehatan registry tool (total, per-kategori, tool inti yang
hilang) dan verifikasi pasca-bootstrap. Fail-fast hanya aktif bila,
`ENFORCE_REGISTRY` atau `ORCH_REQUIRE_DEPS` diset truthy — default permisif.
"""
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger("mcp-unified-bootstrap")

# Tool inti yang diharapkan tersedia pada hub (bukan daftar lengkap).
EXPECTED_CORE_TOOLS: List[str] = [
    "read_file", "write_file", "list_dir", "run_shell",
    "query_db", "list_tables", "describe_table", "count_rows",
    "agent_remember", "agent_recall", "agent_forget",
    "knowledge_search",
    "code_agent_execute", "script_pipeline_run",
    "run_ide_agent",
    "run_tests", "build_and_lint", "dependency_install", "edit_file_patch", "fullstack_run",
]


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def snapshot(registry: Any) -> Dict[str, Any]:
    """Ringkasan kesehatan registry: total, per-kategori, tool inti yang hilang, flag."""
    tools = registry.list_tools(slim=True)
    names = {t["name"] for t in tools}
    by_category: Dict[str, int] = {}
    for t in tools:
        cat = t.get("category", "uncategorized")
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "total_tools": len(names),
        "by_category": by_category,
        "expected_missing": [t for t in EXPECTED_CORE_TOOLS if t not in names],
        "enforce_registry": _truthy(os.getenv("ENFORCE_REGISTRY")),
        "orch_require_deps": _truthy(os.getenv("ORCH_REQUIRE_DEPS")),
    }


def verify_after_bootstrap(registry: Any) -> Dict[str, Any]:
    """Verifikasi pasca-bootstrap. Raise hanya bila enforce aktif & ada tool inti hilang."""
    snap = snapshot(registry)
    if snap["expected_missing"]:
        logger.warning("registry_health: tool inti hilang: %s", snap["expected_missing"])
    else:
        logger.info("registry_health: seluruh tool inti tersedia (%d tool).", snap["total_tools"])

    if (snap["enforce_registry"] or snap["orch_require_deps"]) and snap["expected_missing"]:
        raise RuntimeError(f"ENFORCE_REGISTRY/ORCH_REQUIRE_DEPS aktif: tool inti hilang: {snap['expected_missing']}")
    return snap


def safe_snapshot(registry: Any) -> Dict[str, Any]:
    """Snapshot yang tidak pernah raise — untuk endpoint /health (TASK-174).

    Bila registry belum tersedia/bermasalah, kembalikan dict ringkas berisi
    'error' (tanpa path/secret) agar health check tetap merespons.
    """
    try:
        return snapshot(registry)
    except Exception as exc:  # noqa: BLE001 — health check wajib selalu merespons
        logger.warning("registry_health: snapshot gagal di /health: %s", exc)
        return {"error": str(exc)}
