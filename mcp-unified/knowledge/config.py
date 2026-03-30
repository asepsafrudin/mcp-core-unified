"""
Knowledge Layer Configuration

Configuration management untuk RAG infrastructure.
Supports environment variables dan default values.
"""

import os
from dataclasses import dataclass
from typing import Optional

from core.secrets import load_runtime_secrets


@dataclass
class KnowledgeConfig:
    """Configuration untuk Knowledge Layer dan RAG."""
    
    # Database Configuration
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "mcp_knowledge"
    pg_user: str = "mcp_user"
    pg_password: str = ""
    
    # Embedding Configuration
    embedding_model: str = "nomic-embed-text"  # Ollama default model
    embedding_dimension: int = 768
    ollama_url: str = "http://localhost:11434"
    
    # RAG Configuration
    default_top_k: int = 5
    similarity_threshold: float = 0.7
    max_context_length: int = 4000
    
    # Namespace Configuration
    default_namespace: str = "default"
    enable_namespace_isolation: bool = True
    
    @property
    def database_url(self) -> str:
        """Generate database URL dari config."""
        if self.pg_password:
            return f"postgresql://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"
        return f"postgresql://{self.pg_user}@{self.pg_host}:{self.pg_port}/{self.pg_database}"
    
    @classmethod
    def from_env(cls) -> "KnowledgeConfig":
        """Load configuration dari environment variables."""
        load_runtime_secrets()

        # Support both PG_* and POSTGRES_* environment variables
        pg_host = os.environ.get("POSTGRES_HOST") or os.environ.get("PG_HOST", "localhost")
        pg_port = int(os.environ.get("POSTGRES_PORT") or os.environ.get("PG_PORT", "5432"))
        pg_database = os.environ.get("POSTGRES_DB") or os.environ.get("PG_DATABASE", "mcp")
        pg_user = os.environ.get("POSTGRES_USER") or os.environ.get("PG_USER", "aseps")
        pg_password = os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PG_PASSWORD", "")
        
        return cls(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
            embedding_model=os.environ.get("EMBEDDING_MODEL", "nomic-embed-text"),
            embedding_dimension=int(os.environ.get("EMBEDDING_DIMENSION", "768")),
            ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            default_top_k=int(os.environ.get("RAG_TOP_K", "5")),
            similarity_threshold=float(os.environ.get("RAG_SIMILARITY_THRESHOLD", "0.7")),
            max_context_length=int(os.environ.get("RAG_MAX_CONTEXT", "4000")),
            default_namespace=os.environ.get("RAG_NAMESPACE", "default"),
            enable_namespace_isolation=os.environ.get("RAG_NAMESPACE_ISOLATION", "true").lower() == "true",
        )


# Global config instance
_config: Optional[KnowledgeConfig] = None


def get_knowledge_config() -> KnowledgeConfig:
    """Get knowledge configuration (singleton)."""
    global _config
    if _config is None:
        _config = KnowledgeConfig.from_env()
    return _config


def set_knowledge_config(config: KnowledgeConfig) -> None:
    """Set global knowledge configuration."""
    global _config
    _config = config
