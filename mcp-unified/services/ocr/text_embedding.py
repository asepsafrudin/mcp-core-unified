"""
Indonesian Embedding (indonesian-embedding-small) untuk NLP pipeline.

Modul ini menggunakan model embedding untuk:
1. Semantic similarity untuk koreksi OCR
2. Text classification untuk identifikasi field
3. Named Entity Recognition berbasis embedding
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_NAME=os.getenv("MODEL_NAME", "indonesian-embedding-small" if not os.getenv("CI") else "DUMMY")
DEFAULT_MODEL_PATH = os.getenv(
    "INDONESIAN_EMBEDDING_PATH",
    str(Path.home() / ".cache" / "huggingface" / "hub" / "indonesian-embedding-small")
)


class IndonesianEmbedding:
    """
    Wrapper untuk Indonesian Embedding Small model.
    
    Contoh penggunaan:
        emb = IndonesianEmbedding()
        vectors = emb.encode(["teks 1", "teks 2"])
        similarity = emb.similarity("teks 1", "teks 2")
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self._model = None
        self._tokenizer = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization untuk model embedding."""
        if self._initialized:
            return

        try:
            # Coba load dari sentence-transformers
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_path)
            self._tokenizer = self._model.tokenizer
            self._initialized = True
            logger.info(f"Indonesian Embedding loaded from {self.model_path}")
        except ImportError:
            logger.warning(
                "sentence-transformers tidak terinstal. "
                "Install dengan: pip install sentence-transformers"
            )
            self._initialized = False
        except Exception as e:
            logger.warning(
                f"Gagal load model embedding: {e}. "
                "Fallback ke NLP tanpa embedding."
            )
            self._initialized = False

    def encode(self, texts: list, **kwargs) -> list:
        """
        Encode teks menjadi embedding vector.
        
        Args:
            texts: List of strings to encode
            **kwargs: Additional arguments for model.encode()
            
        Returns:
            List of embedding vectors (numpy arrays)
            
        Example:
            >>> emb = IndonesianEmbedding()
            >>> vectors = emb.encode(["Saya suka makan", "Saya suki minum"])
            >>> print(vectors[0].shape)
            (384,)  # typical embedding dimension
        """
        self._ensure_initialized()
        if not self._initialized or self._model is None:
            return [None] * len(texts)
        return self._model.encode(texts, **kwargs).tolist()

    def similarity(self, text1: str, text2: str) -> float:
        """
        Hitung cosine similarity antara dua teks.
        
        Args:
            text1: First text string
            text2: Second text string
            
        Returns:
            Similarity score between 0 and 1 (1 means identical)
            
        Example:
            >>> emb = IndonesianEmbedding()
            >>> emb.similarity("Saya suka makan nasi", "Saya suka makan")
            0.85
        """
        self._ensure_initialized()
        if not self._initialized or self._model is None:
            return 0.0
        from sklearn.metrics.pairwise import cosine_similarity
        vectors = self._model.encode([text1, text2])
        return float(cosine_similarity([vectors[0]], [vectors[1]])[0][0])

    def find_best_match(self, query: str, candidates: list) -> Optional[tuple]:
        """
        Cari kandidat yang paling mirip dengan query.
        
        Args:
            query: Query text string
            candidates: List of candidate text strings
            
        Returns:
            Tuple (index, similarity, candidate) atau None jika tidak ada kandidat
            
        Example:
            >>> emb = IndonesianEmbedding()
            >>> candidates = ["Kelas I", "Kelas II", "Kelas III"]
            >>> emb.find_best_match("Kelas I1", candidates)
            (0, 0.92, "Kelas I")
        """
        self._ensure_initialized()
        if not self._initialized or not candidates:
            return None

        from sklearn.metrics.pairwise import cosine_similarity
        
        query_vec = self._model.encode([query])
        candidate_vecs = self._model.encode(candidates)
        
        similarities = cosine_similarity(query_vec, candidate_vecs)[0]
        best_idx = int(similarities.argmax())
        best_score = float(similarities[best_idx])
        
        return best_idx, best_score, candidates[best_idx]

    def classify_field(self, text: str, field_templates: dict) -> Optional[str]:
        """
        Klasifikasi field berdasarkan semantic similarity.
        
        Args:
            text: Input text to classify
            field_templates: Dict {field_name: template_text}
            
        Returns:
            Field name yang paling mirip
            
        Example:
            >>> templates = {
            ...     "nomor_surat": "Nomor Surat",
            ...     "tanggal": "Tanggal",
            ... }
            >>> emb = IndonesianEmbedding()
            >>> emb.classify_field("Nomor : 002/F.2/LS/III/2025", templates)
            'nomor_surat'
        """
        self._ensure_initialized()
        if not self._initialized or not field_templates:
            return None

        best_field = None
        best_score = 0

        for field_name, template in field_templates.items():
            score = self.similarity(text, template)
            if score > best_score and score > 0.7:  # threshold
                best_score = score
                best_field = field_name

        return best_field

    def extract_names(self, text: str, name_samples: list) -> list:
        """
        Ekstrak nama orang dari teks berdasarkan similarity dengan sample nama.
        
        Args:
            text: Input document text
            name_samples: List of known/suspected name patterns
            
        Returns:
            List of extracted names with their positions
            
        Example:
            >>> samples = ["Yonatan Maryon Sisco, SH", "Fannia, A.Md"]
            >>> emb = IndonesianEmbedding()
            >>> emb.extract_names(document_text, samples)
            [{'name': 'Yonatan Maryon Sisco, SH', 'confidence': 0.91}]
        """
        self._ensure_initialized()
        if not self._initialized:
            return []

        results = []
        for sample in name_samples:
            # Find best substring match
            best_match = self.find_best_match(sample, [text])
            if best_match and best_match[1] > 0.75:  # threshold
                results.append({
                    "name": sample,
                    "confidence": best_match[1],
                    "corrected": best_match[2],
                })
        
        return results


# ============================================================
# Module Singleton
# ============================================================

_embedding: Optional[IndonesianEmbedding] = None


def get_embedding_model() -> IndonesianEmbedding:
    """Get singleton IndonesianEmbedding instance."""
    global _embedding
    if _embedding is None:
        _embedding = IndonesianEmbedding()
    return _embedding


def encode_text(texts: list) -> list:
    """Convenience function to encode texts."""
    return get_embedding_model().encode(texts)


def text_similarity(text1: str, text2: str) -> float:
    """Convenience function to compute similarity."""
    return get_embedding_model().similarity(text1, text2)


if __name__ == "__main__":
    # Test
    emb = IndonesianEmbedding()
    
    # Test encode
    texts = ["Saya suka makan nasi goreng", "Saya suka minum teh manis"]
    vectors = emb.encode(texts)
    print(f"Vectors shape: {len(vectors)} x {len(vectors[0]) if vectors[0] else 0}")
    
    # Test similarity
    sim = emb.similarity(texts[0], texts[1])
    print(f"Similarity: {sim:.4f}")
    
    # Test find best match
    query = "Kelas I11"
    candidates = ["Kelas I", "Kelas II", "Kelas III"]
    result = emb.find_best_match(query, candidates)
    print(f"Best match for '{query}': {result}")