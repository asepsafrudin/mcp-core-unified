"""
tools/browser/captcha_tools.py — MCP Tool Interface untuk Universal Text CAPTCHA Solver

Mengekspos kapabilitas OCR CAPTCHA cepat (< 0.05s warm) berbasis EasyOCR Singleton
ke seluruh AI Agent di ekosistem MCP Unified.
"""

from __future__ import annotations

import logging
import os
from typing import Optional
from pathlib import Path
import sys

# Ensure core path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from core.task import Task, TaskResult
from core.browser.captcha_solver import solve_text_captcha

logger = logging.getLogger("captcha_tools")


@register_tool
class BrowserSolveCaptchaTool(BaseTool):
    """Tool MCP untuk memecahkan teks CAPTCHA alfanumerik dari gambar/canvas."""

    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="browser_solve_captcha",
            description=(
                "Memecahkan teks CAPTCHA alfanumerik dari gambar (Base64 atau data URI) "
                "secara instan (< 50ms) menggunakan EasyOCR Universal Singleton. "
                "Dapat digunakan untuk portal Srikandi, SIKERJA, OSS, JDIH, atau situs kedinasan lainnya."
            ),
            parameters=[
                ToolParameter(
                    name="image_base64",
                    type="string",
                    description="String gambar Base64 CAPTCHA (dengan atau tanpa prefix data:image/...)",
                    required=True,
                ),
                ToolParameter(
                    name="allowlist",
                    type="string",
                    description=(
                        "Karakter yang diizinkan untuk model OCR. "
                        "Default: '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'. "
                        "Untuk angka saja gunakan '0123456789'."
                    ),
                    required=False,
                    default="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                ),
            ],
            returns="JSON berisi teks hasil ekstraksi CAPTCHA yang bersih",
        )

    async def execute(self, task: Task) -> TaskResult:
        try:
            image_b64 = task.parameters.get("image_base64", "")
            allowlist = task.parameters.get(
                "allowlist",
                "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
            )

            if not image_b64:
                return TaskResult(
                    task_id=task.id,
                    status="error",
                    error="Parameter 'image_base64' tidak boleh kosong."
                )

            captcha_text = solve_text_captcha(image_b64, allowlist=allowlist)
            return TaskResult(
                task_id=task.id,
                status="success",
                data={
                    "captcha_text": captcha_text,
                    "confidence": "high" if len(captcha_text) >= 4 else "low",
                    "length": len(captcha_text)
                }
            )
        except Exception as e:
            logger.error(f"Error memecahkan CAPTCHA via tool: {e}")
            return TaskResult(task_id=task.id, status="error", error=str(e))
