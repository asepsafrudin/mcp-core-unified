"""
deep_tracer.py — Observability Tracer, Latency Breakdown, & Token Cost Calculator for SATRIA.
Captures per-step execution spans (classification, retrieval, LLM reasoning), token consumption,
and monetary cost estimation adhering to official model pricing.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# gpt-4o-mini official pricing per 1M tokens (2025-2026 standard)
PRICING_PER_MILLION = {
    "gpt-4o-mini": {
        "prompt": 0.150,      # $0.150 per 1M prompt tokens
        "completion": 0.600    # $0.600 per 1M completion tokens
    },
    "default": {
        "prompt": 0.150,
        "completion": 0.600
    }
}
USD_TO_IDR = 16000.0  # Kurs acuan stabil


@dataclass
class TokenUsage:
    """Metrik konsumsi token dan estimasi biaya per permintaan."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    estimated_cost_idr: float = 0.0

    @classmethod
    def calculate(cls, prompt_tokens: int, completion_tokens: int, model: str = "gpt-4o-mini") -> "TokenUsage":
        rates = PRICING_PER_MILLION.get(model, PRICING_PER_MILLION["default"])
        cost_prompt = (prompt_tokens / 1_000_000.0) * rates["prompt"]
        cost_completion = (completion_tokens / 1_000_000.0) * rates["completion"]
        total_usd = round(cost_prompt + cost_completion, 6)
        total_idr = round(total_usd * USD_TO_IDR, 2)

        return cls(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost_usd=total_usd,
            estimated_cost_idr=total_idr
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_cost_idr": self.estimated_cost_idr
        }


@dataclass
class LatencyBreakdown:
    """Pemecahan latensi per komponen pipeline SATRIA."""
    classification_ms: float = 0.0
    retrieval_ms: float = 0.0
    llm_inference_ms: float = 0.0
    total_response_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification_ms": round(self.classification_ms, 2),
            "retrieval_ms": round(self.retrieval_ms, 2),
            "llm_inference_ms": round(self.llm_inference_ms, 2),
            "total_response_ms": round(self.total_response_ms, 2)
        }


class TraceSpan:
    """Pengukur durasi waktu eksekusi langkah tertentu."""

    def __init__(self, name: str):
        self.name = name
        self.start_time: float = 0.0
        self.duration_ms: float = 0.0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000.0


class ObservabilityTracer:
    """Orkestrator pencatatan metrik observabilitas mendalam."""

    def span(self, name: str) -> TraceSpan:
        return TraceSpan(name)


satria_tracer = ObservabilityTracer()
