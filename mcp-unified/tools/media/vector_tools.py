import os
import difflib

ICONS_DIR = "/home/aseps/MCP/mcp-data/icons/lucide"

def search_local_svg(keyword: str) -> dict:
    """
    Search for a local SVG icon by filename.
    Provides offline, zero-latency icon fallback.
    Uses fuzzy matching if exact match is not found.
    """
    if not os.path.exists(ICONS_DIR):
        return {"error": f"Icons directory {ICONS_DIR} not found. Please ensure icons are downloaded."}
        
    all_files = os.listdir(ICONS_DIR)
    svg_files = [f for f in all_files if f.endswith(".svg")]
    
    if not svg_files:
        return {"error": "No SVG files found in local repository."}
        
    keyword = keyword.lower().strip().replace(" ", "-")
    
    # 1. Exact match
    exact_match = f"{keyword}.svg"
    if exact_match in svg_files:
        return {
            "success": True,
            "match_type": "exact",
            "file_name": exact_match,
            "file_path": os.path.join(ICONS_DIR, exact_match)
        }
        
    # 2. Contains match
    for svg in svg_files:
        if keyword in svg:
            return {
                "success": True,
                "match_type": "contains",
                "file_name": svg,
                "file_path": os.path.join(ICONS_DIR, svg)
            }
            
    # 3. Fuzzy match
    matches = difflib.get_close_matches(f"{keyword}.svg", svg_files, n=1, cutoff=0.6)
    if matches:
        best_match = matches[0]
        return {
            "success": True,
            "match_type": "fuzzy",
            "file_name": best_match,
            "file_path": os.path.join(ICONS_DIR, best_match)
        }
        
    return {"error": f"No local icon found for keyword '{keyword}'"}
