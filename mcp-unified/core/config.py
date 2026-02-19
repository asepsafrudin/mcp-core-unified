import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    [REVIEWER] Credentials harus selalu dari environment variables
    Jangan pernah hardcode nilai aktual di sini
    Lihat .env.example untuk referensi variabel yang dibutuhkan
    """
    PROJECT_NAME: str = "Agentic IDE Unified Server"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database - [REVIEWER] Never hardcode credentials
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "mcp")
    
    # Redis - [REVIEWER] Use environment variable for connection URL
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    JSON_LOGS: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
