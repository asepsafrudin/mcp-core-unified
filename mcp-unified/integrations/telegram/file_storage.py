"""
File-based storage for Telegram messages

Alternatif dari MCP memory yang bermasalah
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

STORAGE_FILE = os.path.join(os.path.dirname(__file__), 'telegram_messages.json')


class FileStorage:
    """Simple file-based storage for Telegram messages."""
    
    def __init__(self):
        self.file_path = STORAGE_FILE
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create storage file if not exists."""
        if not os.path.exists(self.file_path):
            self._save_data({"messages": []})
    
    def _load_data(self) -> Dict:
        """Load data from file."""
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"messages": []}
    
    def _save_data(self, data: Dict):
        """Save data to file."""
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def save_message(self, key: str, content: str, metadata: Dict) -> bool:
        """Save a message to storage."""
        try:
            data = self._load_data()
            
            # Check if message already exists
            for msg in data["messages"]:
                if msg.get("key") == key:
                    # Update existing
                    msg["content"] = content
                    msg["metadata"] = metadata
                    msg["updated_at"] = datetime.now().isoformat()
                    self._save_data(data)
                    return True
            
            # Add new message
            data["messages"].append({
                "key": key,
                "content": content,
                "metadata": metadata,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            })
            
            self._save_data(data)
            return True
        except Exception as e:
            print(f"❌ Error saving message: {e}")
            return False
    
    def get_pending_messages(self) -> List[Dict[str, Any]]:
        """Get all pending messages."""
        data = self._load_data()
        pending = []
        
        for msg in data["messages"]:
            metadata = msg.get("metadata", {})
            if metadata.get("status") == "pending" and metadata.get("type") == "telegram_bridge_to_cline":
                # Check if already responded
                if not self._is_responded(msg["key"]):
                    pending.append({
                        "key": msg["key"],
                        "content": msg["content"],
                        "user_id": metadata.get("user_id"),
                        "username": metadata.get("username"),
                        "first_name": metadata.get("first_name"),
                        "chat_id": metadata.get("chat_id"),
                        "message_id": metadata.get("message_id"),
                        "timestamp": metadata.get("timestamp") or msg.get("created_at"),
                    })
        
        return pending
    
    def _is_responded(self, key: str) -> bool:
        """Check if message has been responded."""
        data = self._load_data()
        response_key = f"{key}_response"
        
        for msg in data["messages"]:
            if msg.get("key") == response_key:
                return True
        
        return False
    
    def mark_as_responded(self, key: str, response: str) -> bool:
        """Mark message as responded."""
        try:
            data = self._load_data()
            
            # Add response entry
            data["messages"].append({
                "key": f"{key}_response",
                "content": response,
                "metadata": {
                    "type": "telegram_bridge_from_cline",
                    "original_key": key,
                    "status": "responded"
                },
                "created_at": datetime.now().isoformat()
            })
            
            self._save_data(data)
            return True
        except Exception as e:
            print(f"❌ Error marking as responded: {e}")
            return False
    
    def get_all_messages(self) -> List[Dict]:
        """Get all messages (for debugging)."""
        data = self._load_data()
        return data.get("messages", [])


# Global instance
storage = FileStorage()
