"""
Self-Review Tool — Phase 6 Direct Registration

Automated Code Quality & Security Checker.
Direct registration menggunakan @register_tool decorator.
"""
import ast
import re
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from tools.file.path_utils import is_safe_path


class Issue:
    """Satu temuan dari self-review."""
    def __init__(self, severity: str, category: str, description: str,
                 line: int = None, suggestion: str = None):
        self.severity = severity
        self.category = category
        self.description = description
        self.line = line
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        d = {"severity": self.severity, "category": self.category, "description": self.description}
        if self.line:
            d["line"] = self.line
        if self.suggestion:
            d["suggestion"] = self.suggestion
        return d


def check_unused_imports(source: str, tree: ast.AST) -> List[Issue]:
    """Deteksi import yang tidak dipakai."""
    issues = []
    imported_names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split('.')[0]
                imported_names[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                imported_names[name] = node.lineno

    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

    for name, lineno in imported_names.items():
        if name not in used_names and name != '_':
            issues.append(Issue("warning", "quality", f"Import '{name}' tidak dipakai", lineno, f"Hapus baris import '{name}'"))
    return issues


def check_bare_except(source: str, tree: ast.AST) -> List[Issue]:
    """Deteksi bare except."""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                issues.append(Issue("warning", "quality", "Bare 'except:' menelan semua exception", node.lineno, "Gunakan 'except Exception as e:'"))
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                issues.append(Issue("warning", "quality", "except block hanya berisi 'pass'", node.lineno, "Tambahkan logger.warning atau re-raise"))
    return issues


def check_path_validation_consistency(source: str, tree: ast.AST) -> List[Issue]:
    """Deteksi inkonsistensi validasi path."""
    issues = []
    lines = source.splitlines()
    path_check_patterns = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'"/" in \w+', stripped) or re.search(r'"\.\./" in \w+', stripped):
            path_check_patterns.append((i, stripped))
    if len(path_check_patterns) >= 2:
        unique_patterns = set(p[1] for p in path_check_patterns)
        if len(unique_patterns) > 1:
            pattern_lines = [str(p[0]) for p in path_check_patterns]
            issues.append(Issue("critical", "security", f"Inkonsistensi validasi path di baris {', '.join(pattern_lines)}", suggestion="Gunakan kondisi terlengkap di semua blok"))
    return issues


def check_shell_false(source: str, tree: ast.AST) -> List[Issue]:
    """Deteksi subprocess dengan shell=True."""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id
            if func_name in ("run", "Popen", "call", "check_output"):
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        issues.append(Issue("critical", "security", f"subprocess.{func_name}() menggunakan shell=True", node.lineno, "Gunakan shell=False"))
    return issues


def check_hardcoded_secrets(source: str, tree: ast.AST) -> List[Issue]:
    """Deteksi hardcoded credentials."""
    issues = []
    lines = source.splitlines()
    SECRET_PATTERNS = [
        (r'password\s*=\s*["\'][^"\']{4,}["\']', "hardcoded password"),
        (r'secret\s*=\s*["\'][^"\']{8,}["\']', "hardcoded secret"),
        (r'api_key\s*=\s*["\'][^"\']{8,}["\']', "hardcoded api_key"),
        (r'token\s*=\s*["\'][^"\']{8,}["\']', "hardcoded token"),
    ]
    for i, line in enumerate(lines, 1):
        stripped = line.strip().lower()
        if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                issues.append(Issue("critical", "security", f"Kemungkinan {label} di baris {i}", i, "Gunakan os.environ.get('VAR_NAME')"))
                break
    return issues


def check_subprocess_timeout(source: str, tree: ast.AST) -> List[Issue]:
    """Deteksi subprocess tanpa timeout."""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id
            if func_name in ("run", "Popen", "call", "check_output", "create_subprocess_exec", "create_subprocess_shell"):
                has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
                if not has_timeout:
                    issues.append(Issue("warning", "security", f"subprocess.{func_name}() tanpa timeout", node.lineno, "Tambahkan timeout=N"))
    return issues


def check_memory_namespace(source: str, tree: ast.AST) -> List[Issue]:
    """Deteksi memory function tanpa namespace."""
    issues = []
    MEMORY_FUNCTIONS = {"memory_save", "memory_search", "memory_list", "memory_delete"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name in MEMORY_FUNCTIONS:
                has_namespace = any(kw.arg == "namespace" for kw in node.keywords)
                if not has_namespace:
                    issues.append(Issue("warning", "memory", f"Panggilan {func_name}() tanpa namespace", node.lineno, f"Tambahkan namespace=your_namespace"))
    return issues


CHECKS = {
    "general": [check_unused_imports, check_bare_except],
    "security": [check_unused_imports, check_bare_except, check_path_validation_consistency, check_shell_false, check_hardcoded_secrets, check_subprocess_timeout],
    "memory": [check_unused_imports, check_bare_except, check_memory_namespace],
    "all": [check_unused_imports, check_bare_except, check_path_validation_consistency, check_shell_false, check_hardcoded_secrets, check_subprocess_timeout, check_memory_namespace]
}


async def self_review_impl(file_path: str, check_type: str = "general", auto_fix: bool = False) -> Dict[str, Any]:
    """Jalankan automated review terhadap file Python."""
    if not is_safe_path(file_path):
        return {"passed": False, "issues": [{"severity": "critical", "description": "Path outside allowed directories"}], "summary": "BLOCKED: Path tidak aman", "file_path": file_path}
    
    path = Path(file_path)
    if not path.exists():
        return {"passed": False, "issues": [{"severity": "critical", "description": f"File tidak ditemukan: {file_path}"}], "summary": "BLOCKED: File tidak ditemukan", "file_path": file_path}
    if path.suffix != '.py':
        return {"passed": False, "issues": [{"severity": "critical", "description": "Hanya file .py yang didukung"}], "summary": "BLOCKED: Bukan file Python", "file_path": file_path}
    
    try:
        source = path.read_text(encoding='utf-8')
    except Exception as e:
        return {"passed": False, "issues": [{"severity": "critical", "description": f"Tidak bisa membaca file: {e}"}], "summary": "ERROR: Tidak bisa membaca file", "file_path": file_path}
    
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"passed": False, "issues": [{"severity": "critical", "description": f"SyntaxError: {e}", "line": e.lineno}], "summary": f"FAILED: SyntaxError di baris {e.lineno}", "file_path": file_path}
    
    checks_to_run = CHECKS.get(check_type, CHECKS["general"])
    all_issues = []
    for check_func in checks_to_run:
        try:
            found = check_func(source, tree)
            all_issues.extend(found)
        except Exception as e:
            logger.warning("self_review_check_failed", check=check_func.__name__, error=str(e))
    
    critical_count = sum(1 for i in all_issues if i.severity == "critical")
    warning_count = sum(1 for i in all_issues if i.severity == "warning")
    passed = (critical_count == 0 and warning_count == 0)
    
    if passed:
        summary = f"PASSED — tidak ada masalah ditemukan ({check_type} checks)"
    elif critical_count > 0:
        summary = f"FAILED — {critical_count} critical, {warning_count} warning. Perbaiki semua critical issues."
    else:
        summary = f"PASSED WITH WARNINGS — 0 critical, {warning_count} warning."
        passed = True
    
    logger.info("self_review_complete", file=str(path.name), check_type=check_type, passed=passed, critical=critical_count, warnings=warning_count)
    
    return {"passed": passed, "issues": [i.to_dict() for i in all_issues], "summary": summary, "file_path": file_path, "check_type": check_type, "stats": {"critical": critical_count, "warnings": warning_count, "total_checks": len(checks_to_run)}}


async def self_review_batch_impl(file_paths: List[str], check_type: str = "general") -> Dict[str, Any]:
    """Review beberapa file sekaligus."""
    results = {}
    all_passed = True
    total_critical = 0
    total_warnings = 0
    
    for file_path in file_paths:
        result = await self_review_impl(file_path, check_type)
        results[file_path] = result
        if not result["passed"]:
            all_passed = False
        total_critical += result.get("stats", {}).get("critical", 0)
        total_warnings += result.get("stats", {}).get("warnings", 0)
    
    return {"all_passed": all_passed, "total_critical": total_critical, "total_warnings": total_warnings, "per_file": results, "summary": f"{'ALL PASSED' if all_passed else 'SOME FAILED'} — {len(file_paths)} files reviewed, {total_critical} critical, {total_warnings} warnings"}


@register_tool
class SelfReviewTool(BaseTool):
    """Tool untuk automated code review."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="self_review",
            description="Run automated code quality and security review on Python files",
            parameters=[
                ToolParameter(name="file_path", type="string", description="Absolute path ke file Python", required=True),
                ToolParameter(name="check_type", type="string", description="Jenis check: general, security, memory, all", required=False, default="general"),
                ToolParameter(name="auto_fix", type="boolean", description="Coba perbaiki masalah minor otomatis", required=False, default=False)
            ],
            returns="Dict dengan passed, issues, summary, stats"
        )
    
    async def execute(self, task: Task) -> TaskResult:
        payload = task.payload
        result = await self_review_impl(
            file_path=payload.get("file_path"),
            check_type=payload.get("check_type", "general"),
            auto_fix=payload.get("auto_fix", False)
        )
        return TaskResult.success_result(task_id=task.id, data=result, context={"tool": self.name})


@register_tool
class SelfReviewBatchTool(BaseTool):
    """Tool untuk batch code review."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="self_review_batch",
            description="Run automated review on multiple Python files at once",
            parameters=[
                ToolParameter(name="file_paths", type="array", description="List absolute path ke file Python", required=True),
                ToolParameter(name="check_type", type="string", description="Jenis check untuk semua file", required=False, default="general")
            ],
            returns="Dict dengan all_passed, total_critical, total_warnings, per_file"
        )
    
    async def execute(self, task: Task) -> TaskResult:
        payload = task.payload
        result = await self_review_batch_impl(
            file_paths=payload.get("file_paths", []),
            check_type=payload.get("check_type", "general")
        )
        return TaskResult.success_result(task_id=task.id, data=result, context={"tool": self.name})


# Backward compatibility
self_review = self_review_impl
self_review_batch = self_review_batch_impl

__all__ = ["Issue", "CHECKS", "self_review", "self_review_batch"]
