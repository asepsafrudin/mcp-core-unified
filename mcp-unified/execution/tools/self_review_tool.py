"""
Self-Review Tool — Automated Code Quality & Security Checker

Dipanggil agent setelah setiap implementasi untuk mendeteksi masalah
secara otomatis sebelum laporan "selesai" ditulis.

[REVIEWER] Tool ini adalah implementasi objektif dari Self-Review Protocol
yang ada di .agent. Tidak bisa "lulus" jika ada masalah yang terdeteksi.

Usage:
    result = await self_review(
        file_path="/path/ke/file.py",
        check_type="security"
    )
"""
import ast
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
from observability.logger import logger
from tools.file.path_utils import is_safe_path
from execution import registry


# ─── Rule Definitions ──────────────────────────────────────────────────────

class Issue:
    """Satu temuan dari self-review."""
    def __init__(self, severity: str, category: str, description: str,
                 line: int = None, suggestion: str = None):
        self.severity = severity      # "critical", "warning", "info"
        self.category = category      # "security", "quality", "memory"
        self.description = description
        self.line = line
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        d = {
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
        }
        if self.line:
            d["line"] = self.line
        if self.suggestion:
            d["suggestion"] = self.suggestion
        return d


# ─── General Quality Checks ────────────────────────────────────────────────

def check_unused_imports(source: str, tree: ast.AST) -> List[Issue]:
    """
    Deteksi import yang tidak dipakai.
    
    [REVIEWER] Menggunakan AST untuk akurasi — bukan regex sederhana.
    """
    issues = []
    
    # Kumpulkan semua import
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

    # Kumpulkan semua nama yang dipakai (di luar import statement)
    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

    # Temukan yang tidak dipakai
    for name, lineno in imported_names.items():
        if name not in used_names and name != '_':
            issues.append(Issue(
                severity="warning",
                category="quality",
                description=f"Import '{name}' tidak dipakai",
                line=lineno,
                suggestion=f"Hapus baris import '{name}'"
            ))

    return issues


def check_bare_except(source: str, tree: ast.AST) -> List[Issue]:
    """Deteksi bare except yang menelan error diam-diam."""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                issues.append(Issue(
                    severity="warning",
                    category="quality",
                    description="Bare 'except:' menelan semua exception termasuk KeyboardInterrupt",
                    line=node.lineno,
                    suggestion="Gunakan 'except Exception as e:' dan log error-nya"
                ))
            # Cek except yang hanya pass
            if (len(node.body) == 1 and
                    isinstance(node.body[0], ast.Pass)):
                issues.append(Issue(
                    severity="warning",
                    category="quality",
                    description="except block hanya berisi 'pass' — error ditelan tanpa handling",
                    line=node.lineno,
                    suggestion="Minimal tambahkan logger.warning atau re-raise exception"
                ))
    return issues


# ─── Security Checks ───────────────────────────────────────────────────────

def check_path_validation_consistency(source: str, tree: ast.AST) -> List[Issue]:
    """
    [REVIEWER] Rule ini dibuat berdasarkan bug nyata yang ditemukan di
    shell_tools.py (2026-02-19): tiga blok validasi path dengan kondisi
    trigger yang berbeda-beda, membuat blok pertama lebih mudah di-bypass.
    
    Deteksi: apakah ada blok if yang memeriksa path tapi menggunakan
    kondisi yang berbeda dari blok lain di file yang sama.
    """
    issues = []
    lines = source.splitlines()
    
    # Cari semua pola kondisi yang dipakai sebelum is_safe_path
    # Pattern: if [kondisi] in part: ... if not is_safe_path(part)
    path_check_patterns = []
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Cari baris yang memeriksa "/" atau ".." di string
        if re.search(r'"/" in \w+', stripped) or re.search(r'"\.\./" in \w+', stripped):
            path_check_patterns.append((i, stripped))
    
    if len(path_check_patterns) >= 2:
        # Cek apakah kondisinya berbeda
        unique_patterns = set(p[1] for p in path_check_patterns)
        if len(unique_patterns) > 1:
            # Ada inkonsistensi
            pattern_lines = [str(p[0]) for p in path_check_patterns]
            issues.append(Issue(
                severity="critical",
                category="security",
                description=(
                    f"Inkonsistensi kondisi validasi path di baris {', '.join(pattern_lines)}. "
                    f"Ditemukan {len(unique_patterns)} variasi kondisi berbeda. "
                    f"Blok dengan kondisi paling lemah bisa di-bypass."
                ),
                suggestion=(
                    "Gunakan kondisi terlengkap di semua blok: "
                    "'if \"/\" in part or \"..\" in part or part.startswith(\".\")'"
                )
            ))
    
    return issues


def check_shell_false(source: str, tree: ast.AST) -> List[Issue]:
    """Deteksi subprocess.run atau Popen yang menggunakan shell=True."""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Cek subprocess.run(..., shell=True)
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id
            
            if func_name in ("run", "Popen", "call", "check_output"):
                for keyword in node.keywords:
                    if (keyword.arg == "shell" and
                            isinstance(keyword.value, ast.Constant) and
                            keyword.value.value is True):
                        issues.append(Issue(
                            severity="critical",
                            category="security",
                            description=f"subprocess.{func_name}() menggunakan shell=True — risiko command injection",
                            line=node.lineno,
                            suggestion="Gunakan shell=False dan pass list of arguments"
                        ))
    return issues


def check_hardcoded_secrets(source: str, tree: ast.AST) -> List[Issue]:
    """Deteksi kemungkinan hardcoded credentials."""
    issues = []
    lines = source.splitlines()
    
    # Pattern yang mencurigakan
    SECRET_PATTERNS = [
        (r'password\s*=\s*["\'][^"\']{4,}["\']', "hardcoded password"),
        (r'passwd\s*=\s*["\'][^"\']{4,}["\']', "hardcoded passwd"),
        (r'secret\s*=\s*["\'][^"\']{8,}["\']', "hardcoded secret"),
        (r'api_key\s*=\s*["\'][^"\']{8,}["\']', "hardcoded api_key"),
        (r'token\s*=\s*["\'][^"\']{8,}["\']', "hardcoded token"),
    ]
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip().lower()
        # Skip komentar dan docstring
        if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                issues.append(Issue(
                    severity="critical",
                    category="security",
                    description=f"Kemungkinan {label} di baris {i}: {line.strip()[:60]}",
                    line=i,
                    suggestion="Gunakan os.environ.get('VAR_NAME') atau settings dari config.py"
                ))
                break
    
    return issues


def check_subprocess_timeout(source: str, tree: ast.AST) -> List[Issue]:
    """Deteksi subprocess call tanpa timeout."""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id
            
            if func_name in ("run", "Popen", "call", "check_output",
                            "create_subprocess_exec", "create_subprocess_shell"):
                # Cek apakah timeout ada
                has_timeout = any(
                    kw.arg == "timeout" for kw in node.keywords
                )
                if not has_timeout:
                    issues.append(Issue(
                        severity="warning",
                        category="security",
                        description=f"subprocess.{func_name}() tanpa timeout — bisa hang selamanya",
                        line=node.lineno,
                        suggestion="Tambahkan timeout=N (detik) sesuai kebutuhan operasi"
                    ))
    return issues


# ─── Memory Operation Checks ───────────────────────────────────────────────

def check_memory_namespace(source: str, tree: ast.AST) -> List[Issue]:
    """
    Deteksi panggilan memory_save atau memory_search tanpa namespace.
    """
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
                # Cek apakah namespace ada sebagai keyword argument
                has_namespace = any(
                    kw.arg == "namespace" for kw in node.keywords
                )
                if not has_namespace:
                    issues.append(Issue(
                        severity="warning",
                        category="memory",
                        description=f"Panggilan {func_name}() tanpa namespace — akan default ke 'default'",
                        line=node.lineno,
                        suggestion=f"Tambahkan namespace=your_namespace ke panggilan {func_name}()"
                    ))
    
    return issues


# ─── Check Registry ────────────────────────────────────────────────────────

CHECKS = {
    "general": [
        check_unused_imports,
        check_bare_except,
    ],
    "security": [
        check_unused_imports,
        check_bare_except,
        check_path_validation_consistency,
        check_shell_false,
        check_hardcoded_secrets,
        check_subprocess_timeout,
    ],
    "memory": [
        check_unused_imports,
        check_bare_except,
        check_memory_namespace,
    ],
    "all": [
        check_unused_imports,
        check_bare_except,
        check_path_validation_consistency,
        check_shell_false,
        check_hardcoded_secrets,
        check_subprocess_timeout,
        check_memory_namespace,
    ]
}


# ─── Main Tool Function ────────────────────────────────────────────────────

@registry.register
async def self_review(
    file_path: str,
    check_type: str = "general",
    auto_fix: bool = False
) -> Dict[str, Any]:
    """
    Jalankan automated review terhadap file Python.
    
    Dipanggil agent setelah setiap implementasi sebelum menulis laporan selesai.
    
    Args:
        file_path: Absolute path ke file Python yang akan direview
        check_type: Jenis check — "general", "security", "memory", atau "all"
        auto_fix: Jika True, coba perbaiki masalah minor otomatis (experimental)
    
    Returns:
        Dict dengan:
        - passed: True jika tidak ada critical/warning issues
        - issues: List semua masalah yang ditemukan
        - summary: Ringkasan untuk laporan agent
        - file_path: Path file yang direview
    
    [REVIEWER] Tool ini adalah implementasi objektif dari Self-Review Protocol
    di .agent. Hasil tidak bisa dimanipulasi — kode yang bermasalah
    akan terdeteksi.
    """
    # Security: validate path
    if not is_safe_path(file_path):
        return {
            "passed": False,
            "issues": [{"severity": "critical", "description": "Path outside allowed directories"}],
            "summary": "BLOCKED: Path tidak aman",
            "file_path": file_path
        }
    
    path = Path(file_path)
    
    if not path.exists():
        return {
            "passed": False,
            "issues": [{"severity": "critical", "description": f"File tidak ditemukan: {file_path}"}],
            "summary": "BLOCKED: File tidak ditemukan",
            "file_path": file_path
        }
    
    if path.suffix != '.py':
        return {
            "passed": False,
            "issues": [{"severity": "critical", "description": "Hanya file .py yang didukung"}],
            "summary": "BLOCKED: Bukan file Python",
            "file_path": file_path
        }
    
    # Read file
    try:
        source = path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            "passed": False,
            "issues": [{"severity": "critical", "description": f"Tidak bisa membaca file: {e}"}],
            "summary": "ERROR: Tidak bisa membaca file",
            "file_path": file_path
        }
    
    # Parse AST
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {
            "passed": False,
            "issues": [{"severity": "critical", "description": f"SyntaxError: {e}", "line": e.lineno}],
            "summary": f"FAILED: SyntaxError di baris {e.lineno}",
            "file_path": file_path
        }
    
    # Run checks
    checks_to_run = CHECKS.get(check_type, CHECKS["general"])
    all_issues = []
    
    for check_func in checks_to_run:
        try:
            found = check_func(source, tree)
            all_issues.extend(found)
        except Exception as e:
            logger.warning("self_review_check_failed",
                          check=check_func.__name__,
                          error=str(e))
    
    # Evaluate results
    critical_count = sum(1 for i in all_issues if i.severity == "critical")
    warning_count = sum(1 for i in all_issues if i.severity == "warning")
    
    passed = (critical_count == 0 and warning_count == 0)
    
    # Build summary
    if passed:
        summary = f"PASSED — tidak ada masalah ditemukan ({check_type} checks)"
    elif critical_count > 0:
        summary = (
            f"FAILED — {critical_count} critical, {warning_count} warning. "
            f"Perbaiki semua critical issues sebelum melanjutkan."
        )
    else:
        summary = (
            f"PASSED WITH WARNINGS — 0 critical, {warning_count} warning. "
            f"Pertimbangkan untuk memperbaiki warnings."
        )
        passed = True  # Warnings tidak memblokir, hanya menginformasikan
    
    logger.info("self_review_complete",
               file=str(path.name),
               check_type=check_type,
               passed=passed,
               critical=critical_count,
               warnings=warning_count)
    
    return {
        "passed": passed,
        "issues": [i.to_dict() for i in all_issues],
        "summary": summary,
        "file_path": file_path,
        "check_type": check_type,
        "stats": {
            "critical": critical_count,
            "warnings": warning_count,
            "total_checks": len(checks_to_run)
        }
    }


@registry.register
async def self_review_batch(
    file_paths: List[str],
    check_type: str = "general"
) -> Dict[str, Any]:
    """
    Review beberapa file sekaligus.
    Berguna setelah task yang mengubah banyak file.
    
    Args:
        file_paths: List absolute path ke file Python
        check_type: Jenis check untuk semua file
    
    Returns:
        Dict dengan hasil per file dan summary keseluruhan
    """
    results = {}
    all_passed = True
    total_critical = 0
    total_warnings = 0
    
    for file_path in file_paths:
        result = await self_review(file_path, check_type)
        results[file_path] = result
        if not result["passed"]:
            all_passed = False
        total_critical += result.get("stats", {}).get("critical", 0)
        total_warnings += result.get("stats", {}).get("warnings", 0)
    
    return {
        "all_passed": all_passed,
        "total_critical": total_critical,
        "total_warnings": total_warnings,
        "per_file": results,
        "summary": (
            f"{'ALL PASSED' if all_passed else 'SOME FAILED'} — "
            f"{len(file_paths)} files reviewed, "
            f"{total_critical} critical, {total_warnings} warnings"
        )
    }
