"""
OpenHands Artifact Formatter for Antigravity Chat IDE.
Transforms OpenHands execution logs, diffs, metrics, and reasoning steps into rich GitHub Flavored Markdown.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class OpenHandsTaskReport:
    task_id: str
    title: str
    status: str  # SUCCESS, FAILED, RUNNING, TIMEOUT
    prompt: str
    summary: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    diff_content: Optional[str] = None
    steps_executed: List[Dict[str, Any]] = field(default_factory=list)
    raw_logs: str = ""
    error_message: Optional[str] = None


class OpenHandsArtifactFormatter:
    """Formatter to generate rich markdown artifacts conforming to Antigravity IDE design guidelines."""

    @staticmethod
    def format_status_badge(status: str) -> str:
        s = status.upper()
        if s in ("SUCCESS", "COMPLETED"):
            return "🟢 **COMPLETED**"
        elif s == "RUNNING":
            return "🟡 **IN PROGRESS**"
        elif s == "TIMEOUT":
            return "🟠 **TIMEOUT**"
        elif s == "FAILED":
            return "🔴 **FAILED**"
        return f"⚪ **{s}**"

    @classmethod
    def render_markdown_artifact(cls, report: OpenHandsTaskReport) -> str:
        """Render a complete, rich Markdown artifact document."""
        lines = []

        # Header
        lines.append(f"# 🤖 OpenHands Execution Report: {report.title}")
        lines.append("")
        lines.append(f"> **Task ID:** `{report.task_id}` | **Status:** {cls.format_status_badge(report.status)} | **Duration:** `{report.duration_seconds:.2f}s`")
        lines.append(f"> **Started:** `{report.started_at}` | **Completed:** `{report.completed_at or 'In Progress'}`")
        lines.append("")

        # Alert banner based on status
        if report.status.upper() in ("SUCCESS", "COMPLETED"):
            lines.append("> [!TIP]")
            lines.append(f"> Task berhasil dieksekusi secara otonom oleh OpenHands Sandbox. Seluruh artefak dan perubahan file telah diverifikasi.")
        elif report.status.upper() == "RUNNING":
            lines.append("> [!NOTE]")
            lines.append(f"> Task sedang berjalan di background. Dokumen ini diperbarui secara dinamis.")
        elif report.status.upper() == "TIMEOUT":
            lines.append("> [!WARNING]")
            lines.append(f"> Task melebihi batas waktu eksekusi (timeout). Hasil parsial disimpan.")
        else:
            lines.append("> [!CAUTION]")
            lines.append(f"> Terjadi kendala saat eksekusi: {report.error_message or 'Unknown error'}")

        lines.append("")

        # Executive Summary
        lines.append("## 📋 Executive Summary")
        lines.append("")
        lines.append(report.summary or "Tidak ada ringkasan yang tersedia.")
        lines.append("")

        # Prompt & Objective
        lines.append("## 🎯 Objective & Prompt")
        lines.append("")
        lines.append("```text")
        lines.append(report.prompt.strip())
        lines.append("```")
        lines.append("")

        # Workflow / Mermaid Diagram
        lines.append("## 🔄 Execution Workflow")
        lines.append("")
        lines.append("```mermaid")
        lines.append("flowchart TD")
        lines.append("    A[\"Antigravity Request\"] --> B[\"OpenHands Autonomous Engine\"]")
        lines.append(f"    B --> C{{\"Result: {report.status}\"}}")
        if report.files_modified or report.files_created:
            lines.append("    C --> D[\"Workspace Files Updated\"]")
            lines.append("    D --> E[\"Brain Artifact Generated\"]")
        else:
            lines.append("    C --> E[\"Brain Artifact Generated\"]")
        lines.append("    E --> F[\"Antigravity Chat Notification\"]")
        lines.append("```")
        lines.append("")

        # Files Modified Table
        lines.append("## 📁 File Changes & Impact")
        lines.append("")
        if not report.files_modified and not report.files_created:
            lines.append("_Tidak ada file yang diubah atau dibuat._")
        else:
            lines.append("| Tipe | File Path | Tautan |")
            lines.append("|------|-----------|--------|")
            for f in report.files_created:
                p = Path(f)
                lines.append(f"| 🟢 Created | `{f}` | [{p.name}](file://{f}) |")
            for f in report.files_modified:
                p = Path(f)
                lines.append(f"| 🟡 Modified | `{f}` | [{p.name}](file://{f}) |")
        lines.append("")

        # Diff Section
        if report.diff_content and report.diff_content.strip():
            lines.append("## 🔍 Code Diff")
            lines.append("")
            lines.append("```diff")
            lines.append(report.diff_content.strip())
            lines.append("```")
            lines.append("")

        # Execution Steps
        if report.steps_executed:
            lines.append("## 🐾 Execution Steps & Reasoning")
            lines.append("")
            for idx, step in enumerate(report.steps_executed, 1):
                step_title = step.get("action", f"Step {idx}")
                step_desc = step.get("description", "")
                step_status = step.get("status", "DONE")
                lines.append(f"### Step {idx}: {step_title} (`{step_status}`)")
                if step_desc:
                    lines.append(f"{step_desc}")
                if "output" in step and step["output"]:
                    lines.append("```text")
                    lines.append(str(step["output"]).strip())
                    lines.append("```")
                lines.append("")

        # Raw Logs (Collapsible)
        if report.raw_logs:
            lines.append("## 📜 Execution Logs")
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>Klik untuk melihat log lengkap eksekusi OpenHands</summary>")
            lines.append("")
            lines.append("```text")
            lines.append(report.raw_logs.strip())
            lines.append("```")
            lines.append("</details>")
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def render_chat_summary(cls, report: OpenHandsTaskReport, artifact_path: Optional[Path] = None) -> str:
        """Render a concise, high-impact summary suitable for direct display in Antigravity Chat IDE."""
        lines = []
        badge = cls.format_status_badge(report.status)
        lines.append(f"### 🤖 OpenHands Autonomous Coding: {badge}")
        lines.append(f"**Task ID:** `{report.task_id}` | **Waktu Eksekusi:** `{report.duration_seconds:.2f}s`")
        lines.append("")
        lines.append(f"**Ringkasan:** {report.summary}")
        lines.append("")

        if report.files_modified or report.files_created:
            lines.append("**File Terdampak:**")
            for f in report.files_created:
                p = Path(f)
                lines.append(f"- 🟢 [NEW] [{p.name}](file://{f})")
            for f in report.files_modified:
                p = Path(f)
                lines.append(f"- 🟡 [MODIFIED] [{p.name}](file://{f})")
            lines.append("")

        if artifact_path and artifact_path.exists():
            lines.append(f"📄 **Laporan Lengkap & Diff:** [{artifact_path.name}](file://{artifact_path.resolve()})")

        return "\n".join(lines)
