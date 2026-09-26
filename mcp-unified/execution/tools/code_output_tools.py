"""
execution/tools/code_output_tools.py — Perkakas MCP untuk Autonomous Code & Output Engine
Mengekspos 3 perkakas deklaratif ke Agentic IDE (Antigravity / Cline):
1. code_agent_execute: Menulis kode terverifikasi AST & sandbox lokal (user aseps)
2. report_agent_render: Merender dokumen formal SATRIA (HTML/Canvas Markdown)
3. script_pipeline_run: Mengeksekusi pipeline/ETL terisolasi di background sandbox
"""

import os
import json
import time
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from execution.registry import registry
from execution.contracts import (
    CodeExecutionRequest,
    CodeExecutionResponse,
    ReportRenderRequest,
    ReportRenderResponse,
    ScriptPipelineRequest,
    ScriptPipelineResponse,
)
from execution.middleware import EnforcementMiddleware, EnforcementError
from execution.sandbox_runner import SandboxRunner
from services.report_service import SATRIAReportService


@registry.register
def code_agent_execute(
    task_description: str,
    target_file: str,
    code_content: str,
    language: str = "python",
    run_dry_run: bool = True
) -> str:
    """
    Menulis dan memvalidasi kode di sandbox workspace aseps:aseps.
    Memeriksa AST secara deterministik dan melakukan dry-run pengujian.
    Mengembalikan ringkasan status terstruktur (< 500 token).
    """
    trace_id = EnforcementMiddleware.generate_trace_id()
    start_time = time.time()

    try:
        # 1. Validasi path & larangan sudo
        validated_path = EnforcementMiddleware.validate_path(target_file)
        EnforcementMiddleware.check_sudo_forbidden(code_content)

        # 2. Verifikasi AST jika bahasa adalah Python
        ast_valid = True
        if language.lower() == "python":
            ast_ok, ast_err = SandboxRunner.verify_ast(code_content)
            if not ast_ok:
                EnforcementMiddleware.audit_log(
                    trace_id=trace_id,
                    tool_name="code_agent_execute",
                    status="failed_ast",
                    details={"error": ast_err, "target": validated_path}
                )
                resp = CodeExecutionResponse(
                    status="failed",
                    target_file=validated_path,
                    summary=f"Pemeriksaan AST Gagal: {ast_err}",
                    trace_id=trace_id,
                    healing_attempts_used=0,
                    ast_valid=False,
                    execution_time_ms=round((time.time() - start_time) * 1000, 2)
                )
                return resp.model_dump_json(indent=2)

        # 3. Tulis kode ke berkas sasaran
        with open(validated_path, "w", encoding="utf-8") as f:
            f.write(code_content)

        # 4. Dry-run jika diminta
        dry_run_note = "Dry-run dilewati."
        if run_dry_run and language.lower() == "python":
            sandbox_res = SandboxRunner.run_script(validated_path, timeout_seconds=60)
            if not sandbox_res.success:
                # Fallback: draft tersimpan namun status warning
                summary = (
                    f"Kode tersimpan di '{validated_path}', namun gagal pada tahap dry-run:\n"
                    f"Exit code: {sandbox_res.exit_code}\n"
                    f"Traceback ringkas: {sandbox_res.error_summary}"
                )
                summary = EnforcementMiddleware.truncate_summary(summary)
                resp = CodeExecutionResponse(
                    status="partial_success_draft",
                    target_file=validated_path,
                    summary=summary,
                    trace_id=trace_id,
                    healing_attempts_used=1,
                    ast_valid=True,
                    execution_time_ms=round((time.time() - start_time) * 1000, 2)
                )
                return resp.model_dump_json(indent=2)
            dry_run_note = f"Dry-run sukses ({sandbox_res.duration_ms} ms)."

        duration_ms = round((time.time() - start_time) * 1000, 2)
        summary = (
            f"Kode berhasil ditulis dan tervalidasi di '{validated_path}'.\n"
            f"- Status AST: Valid (Pass)\n"
            f"- Eksekusi: {dry_run_note}\n"
            f"- Kepatuhan: Beban izin user 'aseps' (No Sudo), isolasi direktori terpenuhi."
        )

        EnforcementMiddleware.audit_log(
            trace_id=trace_id,
            tool_name="code_agent_execute",
            status="success",
            details={"target": validated_path, "duration_ms": duration_ms}
        )

        resp = CodeExecutionResponse(
            status="success",
            target_file=validated_path,
            summary=summary,
            trace_id=trace_id,
            healing_attempts_used=0,
            ast_valid=True,
            execution_time_ms=duration_ms
        )
        return resp.model_dump_json(indent=2)

    except Exception as e:
        EnforcementMiddleware.audit_log(
            trace_id=trace_id,
            tool_name="code_agent_execute",
            status="error",
            details={"error": str(e)}
        )
        resp = CodeExecutionResponse(
            status="failed",
            target_file=target_file,
            summary=f"Gagal mengeksekusi kode: {str(e)}",
            trace_id=trace_id,
            healing_attempts_used=0,
            ast_valid=False,
            execution_time_ms=round((time.time() - start_time) * 1000, 2)
        )
        return resp.model_dump_json(indent=2)


@registry.register
def report_agent_render(
    title: str,
    output_filename: str,
    data_payload: str,
    template_name: str = "satria_formal_html",
    metadata_json: Optional[str] = None,
    generate_canvas_artifact: bool = True
) -> str:
    """
    Merender dokumen laporan formal pemerintah berstandar SATRIA (HTML & Canvas Markdown).
    Menerima data JSON string, memvalidasi schema, dan menyimpan ke storage/reports/.
    """
    try:
        # Parsing JSON payloads jika dikirim sebagai string
        parsed_data = json.loads(data_payload) if isinstance(data_payload, str) else data_payload
        parsed_meta = json.loads(metadata_json) if metadata_json else None

        req = ReportRenderRequest(
            template_name=template_name,
            title=title,
            data_payload=parsed_data,
            output_filename=output_filename,
            metadata=parsed_meta,
            generate_canvas_artifact=generate_canvas_artifact
        )

        res = SATRIAReportService.render_report(req)
        return res.model_dump_json(indent=2)

    except Exception as e:
        trace_id = EnforcementMiddleware.generate_trace_id()
        resp = ReportRenderResponse(
            status="failed",
            report_path="",
            canvas_artifact_path=None,
            summary=f"Gagal memproses data laporan: {str(e)}",
            trace_id=trace_id,
            total_items_rendered=0
        )
        return resp.model_dump_json(indent=2)


@registry.register
def script_pipeline_run(
    script_path: str,
    args: Optional[str] = None,
    timeout_seconds: int = 120
) -> str:
    """
    Mengeksekusi skrip data/ETL di virtualenv workspace aseps tanpa sudo.
    Mengembalikan status eksekusi, exit code, dan ringkasan durasi.
    """
    trace_id = EnforcementMiddleware.generate_trace_id()
    start_time = time.time()

    try:
        args_list = []
        if args:
            args_list = json.loads(args) if args.startswith("[") else args.split()

        sandbox_res = SandboxRunner.run_script(
            script_path=script_path,
            args=args_list,
            timeout_seconds=timeout_seconds
        )

        status_str = "success" if sandbox_res.success else "failed"
        summary = (
            f"Pipeline '{Path(script_path).name}' selesai dengan status: {status_str.upper()}.\n"
            f"- Exit Code: {sandbox_res.exit_code}\n"
            f"- Durasi: {sandbox_res.duration_ms} ms\n"
        )
        if not sandbox_res.success:
            summary += f"- Error Summary: {sandbox_res.error_summary}\n"
        else:
            summary += f"- Log Singkat: {sandbox_res.stdout[-300:] if sandbox_res.stdout else 'Selesai tanpa output'}"

        summary = EnforcementMiddleware.truncate_summary(summary)

        EnforcementMiddleware.audit_log(
            trace_id=trace_id,
            tool_name="script_pipeline_run",
            status=status_str,
            details={"script": script_path, "exit_code": sandbox_res.exit_code}
        )

        resp = ScriptPipelineResponse(
            status=status_str,
            exit_code=sandbox_res.exit_code,
            summary=summary,
            trace_id=trace_id,
            execution_time_ms=sandbox_res.duration_ms
        )
        return resp.model_dump_json(indent=2)

    except Exception as e:
        resp = ScriptPipelineResponse(
            status="error",
            exit_code=1,
            summary=f"Gagal menjalankan pipeline: {str(e)}",
            trace_id=trace_id,
            execution_time_ms=round((time.time() - start_time) * 1000, 2)
        )
        return resp.model_dump_json(indent=2)
