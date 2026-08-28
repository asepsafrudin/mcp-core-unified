import logging
import os
import re
import urllib.parse
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional

from core.secrets import load_runtime_secrets


load_runtime_secrets()

logger = logging.getLogger(__name__)


# Hosts considered "local" where plaintext redis:// without password is acceptable.
_LOCAL_REDIS_HOSTS = {"localhost", "127.0.0.1", "::1"}


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

    @field_validator("REDIS_URL", mode="after")
    @classmethod
    def _validate_redis_url(cls, value: str) -> str:
        """
        Validate Redis URL format and emit a security warning when plaintext
        redis:// is used without a password against a non-local host.
        """
        if not value:
            raise ValueError("REDIS_URL cannot be empty")

        parsed = urllib.parse.urlparse(value)

        if parsed.scheme not in {"redis", "rediss"}:
            raise ValueError(
                f"REDIS_URL must use scheme 'redis://' or 'rediss://', got '{parsed.scheme}://'"
            )

        host = parsed.hostname
        if not host:
            raise ValueError("REDIS_URL must include a host")

        port = parsed.port
        if port is not None and (port < 1 or port > 65535):
            raise ValueError(f"REDIS_URL port must be between 1 and 65535, got {port}")

        # Security warning: plaintext redis without password on non-local host.
        has_password = parsed.password is not None and parsed.password != ""
        if parsed.scheme == "redis" and not has_password and host not in _LOCAL_REDIS_HOSTS:
            logger.warning(
                "redis_url_security_warning: redis:// without password against non-localhost is insecure; "
                "use REDIS_URL with password or rediss://",
                extra={
                    "redis_url": re.sub(r"://[^@]+@", "://***@", value),
                    "host": host,
                }
            )

        return value


settings = Settings()
