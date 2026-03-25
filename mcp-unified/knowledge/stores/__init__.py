"""
Knowledge Stores - Vector storage backends

Stores:
    - pgvector: PostgreSQL dengan pgvector extension
    - (future) zvec: Zero-shot vector similarity
"""

from .pgvector import PGVectorStore

__all__ = [
    "PGVectorStore",
]
