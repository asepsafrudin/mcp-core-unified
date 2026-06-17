from typing import Dict, Any

def route_engine(task_type: str, params: Dict[str, Any]) -> str:
    """
    Intelligent Router based on Decision Matrix.
    Determines whether to use 'playwright' or 'agent-browser'.
    """
    pw_score = 0
    ab_score = 0
    
    engine_hint = params.get("engine_hint", "auto")
    
    if engine_hint == "playwright":
        return "playwright"
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
            ab_score += 2  # Agent-browser lebih pintar mendeteksi via visual/hybrid
        
    # Ref (@e1) tersedia
    if target and target.startswith("@e"):
        ab_score += 5  # Mutlak milik agent-browser
        
    # Task type scoring
    if task_type in ("scrape", "extract"):
        pw_score += 2
    elif task_type == "task": # Natural language
        return "agent-browser" # Forced
    elif task_type == "action":
        # Form fill: Playwright cepat, tapi kaku
        pw_score += 1
        
    # SPA / heavy JS (seperti React/Material UI)
    if params.get("spa_heavy", False) or (target and "Mui" in target):
        pw_score -= 2
        ab_score += 3
        
    # Anti-bot
    if params.get("anti_bot_detected", False):
        pw_score -= 5
        ab_score += 5
        
    if not target and task_type not in ("navigate", "task", "screenshot", "wait", "session"):
        pw_score -= 5
        ab_score += 4
        
    return "playwright" if pw_score >= ab_score else "agent-browser"
