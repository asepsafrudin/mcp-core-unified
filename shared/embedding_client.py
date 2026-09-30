# shared/embedding_client.py
"""Thin wrapper around the Ollama HTTP API for text embeddings.

Usage example:
```python
from shared.embedding_client import get_embedding
vector = get_embedding('Hello world')
```
The client reads the Ollama endpoint from the shared config loader (see `config_loader.py`).
"""
from typing import List

import requests
from .config_loader import load_config

# Load Ollama settings (e.g., ``ollama_endpoint: http://localhost:11434``)
# If no specific config file, fallback to default.
try:
    _ollama_cfg = load_config('ollama.yaml')
except FileNotFoundError:
    _ollama_cfg = {}
OLLAMA_ENDPOINT = _ollama_cfg.get('ollama_endpoint', 'http://localhost:11434')

def get_embedding(text: str, model: str = 'all-minilm') -> List[float]:
    """Request an embedding vector from Ollama.

    Args:
        text: Input string to embed.
        model: Name of the Ollama model to use (default ``all-minilm``).
    Returns:
        List of floats representing the embedding.
    """
    payload = {
        'model': model,
        'prompt': text,
    }
    response = requests.post(f"{OLLAMA_ENDPOINT}/api/embeddings", json=payload)
    response.raise_for_status()
    data = response.json()
    return data.get('embedding', [])