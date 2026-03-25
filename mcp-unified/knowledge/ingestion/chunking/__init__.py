"""
Text Chunking Module

Chunking strategies untuk memecah dokumen besar menjadi
chunks yang lebih kecil dan manageable.

Strategies:
    - SemanticChunker: Chunk berdasarkan semantic boundaries
    - FixedChunker: Fixed-size chunks dengan overlap
"""

from .text_chunker import SemanticChunker

__all__ = [
    "SemanticChunker",
]