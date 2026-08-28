from typing import Dict, Any

def route_engine(task_type: str, params: Dict[str, Any]) -> str:
    """
    Intelligent Router based on Decision Matrix.
    Determines whether to use 'playwright', 'browser-use', or 'agent-browser'.
    
    Urutan prioritas:
    1. Playwright (primary) — cepat, deterministik, hemat token
    2. browser-use (AI-driven) — memahami halaman via LLM, cocok untuk task kompleks
    3. agent-browser (fallback) — visual/OCR, tangguh untuk anti-bot
    """
    pw_score = 0
    bu_score = 0
    ab_score = 0
    
    engine_hint = params.get("engine_hint", "auto")
    
    if engine_hint == "playwright":
        return "playwright"
    elif engine_hint == "browser-use":
        return "browser-use"
    elif engine_hint == "agent-browser":
        return "agent-browser"
        
    # CSS selector tersedia & spesifik
    target = params.get("target") or params.get("selector")
    if target:
        if target.startswith(("#", ".")):
            pw_score += 3
        # Jika selector menggunakan atribut kompleks (misal: input[name='x'])
        if "[" in target and "]" in target:
            pw_score -= 1  # Playwright rentan gagal jika elemen tersembunyi oleh framework
            bu_score += 2  # browser-use lebih pintar via LLM
            ab_score += 2  # Agent-browser lebih pintar mendeteksi via visual/hybrid
        
    # Ref (@e1) tersedia
    if target and target.startswith("@e"):
        ab_score += 5  # Mutlak milik agent-browser
        
    # Task type scoring
    if task_type in ("scrape", "extract"):
        pw_score += 2
    elif task_type == "task": # Natural language
        return "browser-use" # AI-driven lebih cocok untuk task natural language
    elif task_type == "action":
        # Form fill: Playwright cepat, tapi kaku
        pw_score += 1
        
    # SPA / heavy JS (seperti React/Material UI)
    if params.get("spa_heavy", False) or (target and "Mui" in target):
        pw_score -= 2
        bu_score += 3
        ab_score += 3
        
    # Anti-bot
    if params.get("anti_bot_detected", False):
        pw_score -= 5
        bu_score += 3
        ab_score += 5
        
    if not target and task_type not in ("navigate", "task", "screenshot", "wait", "session"):
        pw_score -= 5
        bu_score += 3
        ab_score += 4
        
    # Decision: Playwright > browser-use > agent-browser
    if pw_score >= bu_score and pw_score >= ab_score:
        return "playwright"
    elif bu_score >= ab_score:
        return "browser-use"
    else:
        return "agent-browser"
