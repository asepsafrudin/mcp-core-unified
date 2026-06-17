import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

SESSION_DIR = Path("/home/aseps/MCP/mcp-data/browser_sessions")
SESSION_DIR.mkdir(parents=True, exist_ok=True)

class SessionManager:
    """Manages browser sessions, auth state, and tabs."""
    
    def __init__(self):
        self.active_tabs: Dict[str, Any] = {}
        self.current_tab_id: str = "default"
        
    def save_state(self, name: str, state_data: str, encrypt: bool = True) -> bool:
        """Save auth state to disk."""
        # Simple mock of saving state
        file_path = SESSION_DIR / f"{name}.json"
        
        # In a real implementation, encrypt if encrypt=True
        data = {
            "state": state_data,
            "encrypted": encrypt
        }
        
        with open(file_path, "w") as f:
            json.dump(data, f)
            
        return True
        
    def load_state(self, name: str) -> Optional[str]:
        """Load auth state from disk."""
        file_path = SESSION_DIR / f"{name}.json"
        if not file_path.exists():
            return None
            
        with open(file_path, "r") as f:
            data = json.load(f)
            
        return data.get("state")
        
    def list_sessions(self) -> List[str]:
        """List all saved sessions."""
        return [f.stem for f in SESSION_DIR.glob("*.json")]
        
    def delete_session(self, name: str) -> bool:
        file_path = SESSION_DIR / f"{name}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

session_manager = SessionManager()
