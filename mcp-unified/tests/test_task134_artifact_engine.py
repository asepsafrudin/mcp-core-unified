"""
tests/test_task134_artifact_engine.py — Unit & Integration Test Suite untuk TASK-134
Menguji seluruh pilar Autonomous Coder & Output Engine (MAF-Based):
1. EnforcementMiddleware (Path allowlist, no-sudo check, token truncation)
2. SandboxRunner (AST parsing, virtualenv execution)
3. code_agent_execute tool
4. report_agent_render tool (SATRIA standard)
5. script_pipeline_run tool
"""

import os
import sys
import json
import pytest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from execution.middleware import EnforcementMiddleware, EnforcementError
from execution.sandbox_runner import SandboxRunner
from execution.contracts import CodeExecutionResponse, ReportRenderResponse, ScriptPipelineResponse
from execution.tools.code_output_tools import code_agent_execute, report_agent_render, script_pipeline_run


def test_middleware_path_allowlist():
    """Memastikan hanya direktori yang diizinkan yang dapat ditulis."""
    # Path aman (harus lolos)
    safe_script = str(PROJECT_ROOT.parent.parent / "scripts" / "test.py")
    safe_storage = str(PROJECT_ROOT.parent.parent / "storage" / "reports" / "test.html")
    safe_scratch = str(PROJECT_ROOT.parent.parent / "scratch" / "test.tmp")

    assert EnforcementMiddleware.validate_path(safe_script)
    assert EnforcementMiddleware.validate_path(safe_storage)
    assert EnforcementMiddleware.validate_path(safe_scratch)

    # Path root (harus ditolak)
    root_file = str(PROJECT_ROOT.parent.parent / "illegal_root_file.txt")
    with pytest.raises(EnforcementError):
        EnforcementMiddleware.validate_path(root_file)

    # Path sistem (harus ditolak)
    with pytest.raises(EnforcementError):
        EnforcementMiddleware.validate_path("/etc/passwd")


def test_middleware_sudo_forbidden():
    """Memastikan perintah sudo dilarang keras secara deterministik."""
    with pytest.raises(EnforcementError):
        EnforcementMiddleware.check_sudo_forbidden("sudo apt-get update")

    with pytest.raises(EnforcementError):
        EnforcementMiddleware.check_sudo_forbidden("import os; os.system('sudo rm -rf /')")

    # Command aman
    EnforcementMiddleware.check_sudo_forbidden("pip install pydantic")


def test_sandbox_ast_verifier():
    """Memastikan parser AST mendeteksi error sintaksis sebelum eksekusi."""
    valid_code = "def hello():\n    return 'world'\n"
    ok, err = SandboxRunner.verify_ast(valid_code)
    assert ok is True
    assert err is None

    invalid_code = "def hello( broken syntax"
    ok, err = SandboxRunner.verify_ast(invalid_code)
    assert ok is False
    assert "SyntaxError" in err


def test_code_agent_execute_tool():
    """Menguji eksekusi penulisan kode di sandbox scratch/."""
    target_file = str(PROJECT_ROOT.parent.parent / "scratch" / "test_calc.py")
    code = (
        "def tambah(a, b):\n"
        "    return a + b\n\n"
        "if __name__ == '__main__':\n"
        "    hasil = tambah(10, 20)\n"
        "    print(f'HASIL: {hasil}')\n"
    )

    res_raw = code_agent_execute(
        task_description="Buat fungsi penambahan sederhana",
        target_file=target_file,
        code_content=code,
        language="python",
        run_dry_run=True
    )

    res_json = json.loads(res_raw)
    assert res_json["status"] == "success"
    assert res_json["ast_valid"] is True
    assert "TRC-" in res_json["trace_id"]
    assert os.path.exists(target_file)


def test_report_agent_render_tool():
    """Menguji perenderan laporan formal berstandar SATRIA."""
    output_filename = "test_laporan_satria.html"
    sample_data = [
        {
            "nomor": "PERMENDAGRI No. 1 Tahun 2026",
            "tahun": "2026",
            "tentang": "Pedoman Pengelolaan Regulasi Daerah",
            "status": "Berlaku",
            "drive_link": "https://drive.google.com/test",
            "size": "1.2 MB"
        }
    ]

    res_raw = report_agent_render(
        title="Laporan Uji Coba SATRIA Report Engine",
        output_filename=output_filename,
        data_payload=json.dumps(sample_data),
        metadata_json=json.dumps({"institution": "Ditjen Bina Pembangunan Daerah"}),
        generate_canvas_artifact=True
    )

    res_json = json.loads(res_raw)
    assert res_json["status"] == "success"
    assert res_json["total_items_rendered"] == 1
    assert os.path.exists(res_json["report_path"])

    # Verifikasi isi HTML memuat komponen SATRIA
    with open(res_json["report_path"], "r", encoding="utf-8") as f:
        content = f.read()
        assert "SATRIA" in content
        assert "KEMENTERIAN DALAM NEGERI" in content
        assert "PERMENDAGRI No. 1 Tahun 2026" in content


def test_script_pipeline_run_tool():
    """Menguji eksekusi skrip via pipeline runner."""
    script_file = str(PROJECT_ROOT.parent.parent / "scratch" / "test_calc.py")
    res_raw = script_pipeline_run(script_path=script_file)
    res_json = json.loads(res_raw)

    assert res_json["status"] == "success"
    assert res_json["exit_code"] == 0
    assert "HASIL: 30" in res_json["summary"]
