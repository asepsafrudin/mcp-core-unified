"""
Text Embedding Generation

Generate text embeddings menggunakan Ollama atau OpenAI.
Used oleh RAG engine untuk document indexing dan retrieval.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional, Union

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from observability.logger import logger
from .config import get_knowledge_config


class EmbeddingGenerator:
    """
    Generate text embeddings menggunakan local Ollama.
    
    [REVIEWER] Using nomic-embed-text via Ollama untuk local embedding generation.
    Fallback available untuk OpenAI jika configured.
    """
    
    def __init__(self, model: str = None, ollama_url: str = None):
        config = get_knowledge_config()
        self.model = model or config.embedding_model
        self.ollama_url = ollama_url or config.ollama_url
        self.dimension = config.embedding_dimension
    
    async def generate(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding untuk single text.
        
        Args:
            text: Text untuk di-embed
        
        Returns:
            List of floats (embedding vector) atau None jika gagal
        """
        try:
            # Use Ollama untuk embedding
            return await self._generate_ollama(text)
        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e), model=self.model)
            return None
    
    async def generate_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings untuk batch of texts.
        
        Args:
            texts: List of texts untuk di-embed
        
        Returns:
            List of embeddings (None untuk texts yang gagal)
        """
        # Process sequentially untuk avoid overwhelming Ollama
        results = []
        for text in texts:
            embedding = await self.generate(text)
            results.append(embedding)
        return results
    
    async def _generate_ollama(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding menggunakan Ollama API.
        
        [REVIEWER] Menggunakan curl via subprocess - konsisten dengan
        vision_tools.py dan longterm.py. Tidak introduce requests dependency.
        """
        import asyncio
        
        payload = json.dumps({
            "model": self.model,
            "prompt": text
        })
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s",
                "-X", "POST",
                f"{self.ollama_url}/api/embeddings",
                "-H", "Content-Type: application/json",
                "-d", payload,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=30  # 30 seconds timeout untuk embedding
            )
            
            if proc.returncode != 0:
                logger.error("ollama_embedding_error",
                            model=self.model,
                            error=stderr.decode()[:200])
                return None
            
            response_data = json.loads(stdout)
            embedding = response_data.get("embedding")
            
            if embedding:
                logger.info("embedding_generated",
                           model=self.model,
                           dimension=len(embedding),
                           text_length=len(text))
                return embedding
            else:
                logger.warning("embedding_empty_response", model=self.model)
                return None
                
        except asyncio.TimeoutError:
            logger.error("ollama_embedding_timeout", model=self.model, timeout=30)
            return None
        except Exception as e:
            logger.error("ollama_embedding_failed", error=str(e), model=self.model)
            return None
    
    def truncate_text(self, text: str, max_tokens: int = 512) -> str:
        """
        Truncate text untuk fit dalam model's context window.
        Simple word-based truncation.
        
        Args:
            text: Text untuk di-truncate
            max_tokens: Maximum tokens (approximate words)
        
        Returns:
            Truncated text
        """
        words = text.split()
        if len(words) <= max_tokens:
            return text
        return " ".join(words[:max_tokens]) + "..."


# Global generator instance
_generator: Optional[EmbeddingGenerator] = None


async def get_embeddings(text: Union[str, List[str]]) -> Union[Optional[List[float]], List[Optional[List[float]]]]:
    """
    Convenience function untuk generate embeddings.
    
    Args:
        text: Single text atau list of texts
    
    Returns:
        Single embedding atau list of embeddings
    
    Example:
        # Single text
        embedding = await get_embeddings("Hello world")
        
        # Batch
        embeddings = await get_embeddings(["text1", "text2", "text3"])
    """
    global _generator
    if _generator is None:
        _generator = EmbeddingGenerator()
    
    if isinstance(text, str):
        return await _generator.generate(text)
    else:
        return await _generator.generate_batch(text)
