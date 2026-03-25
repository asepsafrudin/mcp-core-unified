"""Extractors untuk berbagai jenis website."""

from .base_extractor import BaseExtractor, ExtractedContent
from .perplexity_extractor import PerplexityExtractor
from .jdih_extractor import JDIHExtractor
from .news_extractor import NewsExtractor
from .generic_extractor import GenericExtractor

__all__ = [
    "BaseExtractor",
    "ExtractedContent",
    "PerplexityExtractor",
    "JDIHExtractor",
    "NewsExtractor",
    "GenericExtractor",
]