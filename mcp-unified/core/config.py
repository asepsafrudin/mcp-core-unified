import os
from pydantic_settings import BaseSettings
from typing import Optional

from core.secrets import load_runtime_secrets


load_runtime_secrets()


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
    POSTGRES_USER: str = os.getenv("POSTGRES_USER") or os.getenv("PG_USER", "")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD") or os.getenv("PG_PASSWORD", "")
    POSTGRES_SERVER: str = (
        os.getenv("POSTGRES_SERVER")
        or os.getenv("POSTGRES_HOST")
        or os.getenv("PG_HOST", "localhost")
    )
    POSTGRES_PORT: int = int(
        os.getenv("POSTGRES_PORT")
        or os.getenv("PG_PORT", "5432")
    )
    POSTGRES_DB: str = os.getenv("POSTGRES_DB") or os.getenv("PG_DATABASE", "mcp")
    
    # Redis - [REVIEWER] Use environment variable for connection URL
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    JSON_LOGS: bool = True

    class Config:
        extra = "ignore"


settings = Settings()
