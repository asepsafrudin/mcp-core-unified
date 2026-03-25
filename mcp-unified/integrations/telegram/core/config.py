"""Configuration for Telegram Bot."""
import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TelegramConfig:
    """Configuration for Telegram Bot."""
    bot_token: str
    allowed_users: List[int]
    mode: str = "polling"
    webhook_url: Optional[str] = None
    webhook_port: int = 8443
    mcp_server_url: str = "http://localhost:8000"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.1-8b-instant"
    ai_provider: str = "groq"
    
    @classmethod
    def from_env(cls) -> "TelegramConfig":
        """Load configuration from environment variables."""
        from dotenv import load_dotenv
        
        # Load .env file
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path)
        
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise ValueError(" ***REMOVED_TOKEN***environment variable is required")
        
        # Parse allowed users
        allowed_users_str = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        allowed_users = []
        if allowed_users_str:
            try:
                allowed_users = [int(uid.strip()) for uid in allowed_users_str.split(",") if uid.strip()]
            except ValueError:
                pass
        
        return cls(
            bot_token=bot_token,
            allowed_users=allowed_users,
            mode=os.getenv("TELEGRAM_MODE", "polling"),
            webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL"),
            webhook_port=int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8443")),
            mcp_server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8000"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            groq_api_key=os.getenv("GROQ_API_KEY"),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            ai_provider=os.getenv("AI_PROVIDER", "groq"),
        )
