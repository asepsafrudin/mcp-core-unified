import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings

class BrowserOrchestratorConfig(BaseSettings):
    """Configuration for Browser Orchestrator MCP."""
    
    # Token Budgets
    TOKEN_BUDGET_SNAPSHOT: int = 2000
    TOKEN_BUDGET_EXTRACT: int = 8000
    TOKEN_BUDGET_TASK: int = 3000
    TOKEN_BUDGET_ERROR: int = 200
    
    # Playwright Settings
    PLAYWRIGHT_TIMEOUT_MS: int = 25000
    
    # AB Settings
    AGENT_BROWSER_TIMEOUT_MS: int = 30000
    AGENT_BROWSER_PATH: str = "agent-browser"
    
    # Fallback Settings
    MAX_RETRIES: int = 2
    
    class Config:
        env_prefix = "BROWSER_ORCH_"
        
config = BrowserOrchestratorConfig()
