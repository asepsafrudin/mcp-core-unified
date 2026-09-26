"""
Full Live Test Runner for Microsoft Agent Framework (MAF)
Executes Fase 1, Fase 2, and Advanced Security Test Suites.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON_BIN = sys.executable

TESTS = [
    ("Fase 1: Core Scaffolding", REPO_ROOT / "core" / "agent-framework" / "test_maf_core.py"),
    ("Fase 2: Bidirectional MCP & Code Agent", REPO_ROOT / "core" / "agent-framework" / "test_maf_phase2.py"),
    ("Advanced: Security, Persistence & Multi-Vendor", REPO_ROOT / "core" / "agent-framework" / "test_maf_advanced.py"),
    ("Dual-Track Legal & Dynamic Prompt Builder", REPO_ROOT / "core" / "agent-framework" / "test_prompt_builder.py"),
    ("Track A Engine: Legislative Drafting (Ditjen PP)", REPO_ROOT / "scripts" / "test_task133_fase2_track_a.py"),
    ("Track B Engine: Legal Counsel & Advocacy (BPHN)", REPO_ROOT / "scripts" / "test_task133_fase3_track_b.py"),
    ("E2E Integration: Dual-Track Legal Agent di atas MAF", REPO_ROOT / "scripts" / "test_task133_dual_track_legal_maf.py"),
]



def main() -> int:
    print("=" * 65)
    print("LAPORAN STATUS PENGUJIAN LANGSUNG: MICROSOFT AGENT FRAMEWORK (MAF)")
    print("=" * 65)

    all_passed = True
    summary = []

    for name, path in TESTS:
        print(f"\n▶ Menjalankan {name}...")
        res = subprocess.run([PYTHON_BIN, str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Clean output
        lines = [line for line in res.stdout.splitlines() if "could not parse statement" not in line]
        output = "\n".join(lines).strip()
        print(output)

        if res.returncode == 0:
            print(f"👉 Status: ✅ BERHASIL (PASSED)")
            summary.append((name, "PASSED"))
        else:
            print(f"👉 Status: ❌ GAGAL (FAILED)")
            summary.append((name, "FAILED"))
            all_passed = False

    print("\n" + "=" * 65)
    print("RINGKASAN HASIL:")
    for n, s in summary:
        icon = "✅" if s == "PASSED" else "❌"
        print(f"  {icon} {n}: {s}")
    print("=" * 65)

    if all_passed:
        print("🎉 KESIMPULAN: SEMUA PENGUJIAN LULUS 100%! SISTEM SIAP UNTUK FASE 3.")
        return 0
    else:
        print("⚠️ KESIMPULAN: TERDAPAT PENGUJIAN GAGAL.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
