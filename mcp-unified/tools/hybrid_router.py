import logging
from typing import Dict, Any, List

from .base import register_tool

logger = logging.getLogger(__name__)

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
