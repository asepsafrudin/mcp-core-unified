"""OCR Service Package — PaddleOCR + NLP + indonesian-embedding-small + LLM."""
from .tools import register_tools
from .service import OCREngine
from .nlp_processor import NLPProcessor, get_nlp_processor, normalize_ocr_text, extract_entities
from .text_embedding import (
    IndonesianEmbedding,
    get_embedding_model,
    encode_text,
    text_similarity,
)
from .context_refiner import (
    ContextRefiner,
    get_context_refiner,
)
from .learning_store import (
    LearningStore,
    get_learning_store,
)

__all__ = [
    "register_tools",
    "OCREngine",
    "NLPProcessor",
    "IndonesianEmbedding",
    "ContextRefiner",
    "LearningStore",
    "get_nlp_processor",
    "get_embedding_model",
    "get_context_refiner",
    "get_learning_store",
    "normalize_ocr_text",
    "extract_entities",
    "encode_text",
    "text_similarity",
]
