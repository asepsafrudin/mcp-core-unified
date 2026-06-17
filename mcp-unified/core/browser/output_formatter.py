import json
import logging
from typing import Dict, Any
from .config import config

logger = logging.getLogger("output_formatter")

def compact_json(data: Dict[str, Any]) -> str:
    """Compact dict to JSON string without extra whitespace."""
    return json.dumps(data, separators=(',', ':'))

def truncate_text(text: str, max_chars: int) -> str:
    """Truncate text to max_chars and append a marker if truncated."""
    if len(text) <= max_chars:
        return text
    marker = f"\n... [truncated {len(text) - max_chars} chars]"
    return text[:max_chars] + marker

def format_snapshot(elements: list, engine_used: str) -> dict:
    """Format snapshot response compactly."""
    data = {
        "elements": elements,
        "total_elements": len(elements),
        "engine_used": engine_used
    }
    # estimate token count (approx chars / 4)
    data["token_count_estimate"] = len(compact_json(data)) // 4
    return data

def format_extract(data: Any, max_chars: int, engine_used: str) -> dict:
    """Format extract response ensuring it stays within max_chars."""
    if isinstance(data, (dict, list)):
        text = compact_json(data)
    else:
        text = str(data)
        
    text = truncate_text(text, max_chars)
    return {
        "extracted_data": text,
        "engine_used": engine_used,
        "truncated": len(text) == max_chars,
        "token_count_estimate": len(text) // 4
    }

def format_error(error_code: str, message: str, engine_used: str, suggestion: str, elapsed_ms: int = 0, fallback: bool = False) -> dict:
    """Unified error response schema."""
    return {
        "success": False,
        "error_code": error_code,
        "error_message": message,
        "engine_used": engine_used,
        "fallback_attempted": fallback,
        "suggestion": suggestion,
        "elapsed_ms": elapsed_ms
    }

import sys

def log_tool_call(tool: str, engine_used: str, elapsed_ms: int, token_estimate: int, success: bool, fallback_used: bool = False):
    """Log structured JSON to stderr for observability without polluting stdout."""
    log_data = {
        "tool": tool,
        "engine_used": engine_used,
        "elapsed_ms": elapsed_ms,
        "token_estimate": token_estimate,
        "success": success,
        "fallback_used": fallback_used
    }
    print(compact_json(log_data), file=sys.stderr)
    sys.stderr.flush()
