import json
import logging
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import register_tool

logger = logging.getLogger(__name__)

# ─── Helper: baca OLLAMA_URL dari env / .env.ai ────────────────────────────────

_ENV_AI_FILE = Path(__file__).resolve().parents[2] / "config" / "env" / ".env.ai"


def _get_ollama_url() -> str:
    val = os.environ.get("OLLAMA_URL", "")
    if val:
        return val.rstrip("/")
    if _ENV_AI_FILE.exists():
        for line in _ENV_AI_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("OLLAMA_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
    return "http://localhost:11434"


def _is_colab_backend(url: str) -> bool:
    return "localhost" not in url and "127.0.0.1" not in url


# ─── Tools baru: Inference Backend & Colab LLM ────────────────────────────────

@register_tool
def get_inference_backend() -> Dict[str, Any]:
    """
    Mengembalikan informasi backend inferensi LLM yang sedang aktif.

    Returns:
        dict dengan keys: backend ('colab_ollama'|'local_ollama'|'openai'|'none'),
        url, recommended_model, available_models, latency_ms.
    """
    ollama_url = _get_ollama_url()
    is_colab   = _is_colab_backend(ollama_url)

    start = time.time()
    try:
        req = urllib.request.Request(
            f"{ollama_url}/api/tags",
            headers={"User-Agent": "MCP-HybridRouter/1.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            latency_ms  = round((time.time() - start) * 1000, 1)
            data        = json.loads(r.read())
            model_names = [m.get("name") for m in data.get("models", [])]
            preferred   = next(
                (m for m in ["qwen2.5-coder:7b", "qwen2.5-coder:14b", "codellama:13b"]
                 if m in model_names),
                model_names[0] if model_names else "qwen2.5-coder:7b",
            )
            return {
                "backend":           "colab_ollama" if is_colab else "local_ollama",
                "url":               ollama_url,
                "recommended_model": preferred,
                "available_models":  model_names,
                "latency_ms":        latency_ms,
            }
    except Exception as e:
        pass

    # Fallback ke OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        return {
            "backend":           "openai",
            "url":               "https://api.openai.com/v1",
            "recommended_model": "gpt-4o",
            "available_models":  ["gpt-4o", "gpt-4o-mini"],
            "latency_ms":        0,
        }

    return {
        "backend": "none", "url": "", "recommended_model": "",
        "available_models": [], "latency_ms": 0,
        "error": "Tidak ada backend inferensi yang tersedia",
    }


@register_tool
def colab_llm_chat(
    prompt: str,
    model: str = "qwen2.5-coder:7b",
    system_prompt: str = "Kamu adalah coding assistant yang membantu.",
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> Dict[str, Any]:
    """
    Mengirim prompt langsung ke Ollama di Colab GPU dan mengembalikan respons.

    Args:
        prompt:        Pesan/pertanyaan untuk LLM.
        model:         Model Ollama yang digunakan (default: qwen2.5-coder:7b).
        system_prompt: System prompt untuk mengatur perilaku LLM.
        temperature:   Kreativitas respons (0.0 = deterministik, 1.0 = kreatif).
        max_tokens:    Maksimal token respons.

    Returns:
        dict dengan keys: ok, response, model, latency_ms, error.
    """
    ollama_url = _get_ollama_url()
    api_url    = f"{ollama_url}/api/chat"

    payload = json.dumps({
        "model":   model,
        "stream":  False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
        "messages": [
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": prompt},
        ],
    }).encode("utf-8")

    start = time.time()
    try:
        req = urllib.request.Request(
            api_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent":   "MCP-HybridRouter/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            latency_ms = round((time.time() - start) * 1000, 1)
            data       = json.loads(r.read())
            content    = data.get("message", {}).get("content", "")
            return {
                "ok":         True,
                "response":   content,
                "model":      model,
                "latency_ms": latency_ms,
                "backend":    "colab_ollama" if _is_colab_backend(ollama_url) else "local_ollama",
            }
    except Exception as e:
        return {
            "ok":    False,
            "error": str(e),
            "model": model,
            "latency_ms": round((time.time() - start) * 1000, 1),
        }



@register_tool
def browser_route(
    task_description: str,
    task_type: str,
    hint: str = "auto"
) -> Dict[str, Any]:
    """
    Menentukan engine browser mana yang optimal (agent_browser atau playwright).
    
    Args:
        task_description: Deskripsi task natural language
        task_type: "navigate", "fill_form", "extract_data", "screenshot", "multi_step", "visual_verify", "api_intercept"
        hint: "prefer_ab", "prefer_pw", atau "auto"
    """
    
    if hint == "prefer_ab":
        return _build_decision("agent_browser", 1.0, "Forced by hint: prefer_ab", ["ab_navigate"])
    elif hint == "prefer_pw":
        return _build_decision("playwright", 1.0, "Forced by hint: prefer_pw", ["pw_navigate"])
        
    score = 0.0
    reasoning_parts = []
    
    # 1. Task type (Bobot: 35%)
    if task_type in ["navigate", "extract_data", "fill_form"]:
        score += 0.35
        reasoning_parts.append("Task tipe simpel mendukung semantic locators")
    elif task_type in ["visual_verify", "api_intercept", "multi_step"]:
        reasoning_parts.append("Task tipe kompleks atau visual membutuhkan fungsionalitas CDP penuh")
        
    # 2. Estimasi langkah dari deskripsi (Bobot: 20%)
    # Heuristik sederhana: hitung jumlah kata kerja atau 'and'/'then'
    words = task_description.lower().split()
    complexity_markers = ["then", "after", "wait", "verify", "check", "if"]
    markers_found = sum(1 for w in words if w in complexity_markers)
    if markers_found <= 2:
        score += 0.20
        reasoning_parts.append("Langkah diprediksi sedikit (≤ 5)")
    else:
        reasoning_parts.append("Langkah diprediksi banyak/kompleks")
        
    # 3. Kebutuhan screenshot visual (Bobot: 15%)
    if "screenshot" not in task_type and "visual" not in task_description.lower():
        score += 0.15
    else:
        reasoning_parts.append("Terdapat kebutuhan visual yang lebih baik di-handle Playwright")
        
    # 4. Asumsi form statis jika tidak eksplisit disebut dynamic (Bobot: 15%)
    if "dynamic" not in task_description.lower() and "ajax" not in task_description.lower():
        score += 0.15
        
    # 5. Asumsi sesi baru (Bobot: 15%)
    if "continue" not in task_description.lower():
        score += 0.15
        
    recommended_engine = "agent_browser" if score >= 0.6 else "playwright"
    alternative_engine = "playwright" if recommended_engine == "agent_browser" else "agent_browser"
    
    reasoning = " | ".join(reasoning_parts)
    
    # Rekomendasi tools
    tools = []
    if recommended_engine == "agent_browser":
        tools = ["ab_navigate", "ab_snapshot", "ab_extract"]
    else:
        tools = ["pw_navigate", "pw_screenshot"]
        
    return {
        "recommended_engine": recommended_engine,
        "confidence": round(score, 2) if recommended_engine == "agent_browser" else round(1.0 - score, 2),
        "reasoning": reasoning,
        "alternative_engine": alternative_engine,
        "suggested_tools": tools
    }

def _build_decision(engine: str, confidence: float, reasoning: str, tools: List[str]):
    return {
        "recommended_engine": engine,
        "confidence": confidence,
        "reasoning": reasoning,
        "alternative_engine": "playwright" if engine == "agent_browser" else "agent_browser",
        "suggested_tools": tools
    }
