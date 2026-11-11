"""
Sub-paket handlers untuk SATRIA WhatsApp Bot.
Menyediakan modularitas untuk persona prompts, routing, retrieval, dan tool execution.
"""

from .prompts import (
    SATRIA_PERSONAL_ASSISTANT_PROMPT,
    SATRIA_LEGAL_MADYA_PROMPT,
    SATRIA_ADMIN_PERSURATAN_PROMPT,
    SATRIA_SYSTEM_PROMPT,
)
from .persona_router import detect_satria_persona

__all__ = [
    "SATRIA_PERSONAL_ASSISTANT_PROMPT",
    "SATRIA_LEGAL_MADYA_PROMPT",
    "SATRIA_ADMIN_PERSURATAN_PROMPT",
    "SATRIA_SYSTEM_PROMPT",
    "detect_satria_persona",
]

