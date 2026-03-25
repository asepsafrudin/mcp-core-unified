"""
Web Scraping Knowledge Bridge untuk MCP-Unified

Modul ini menyediakan kemampuan web scraping dari berbagai sumber
untuk mengisi knowledge base agent legal.
"""

from .core.browser_bridge import GenericBrowserBridge
from .core.extractors.base_extractor import BaseExtractor, ExtractedContent
from .core.extractors.perplexity_extractor import PerplexityExtractor
from .core.extractors.jdih_extractor import JDIHExtractor
from .core.extractors.news_extractor import NewsExtractor
from .core.extractors.generic_extractor import GenericExtractor
from .core.validators.four_level_validator import FourLevelValidator, ValidationResult
from .ingestors.knowledge_ingestor import WebScrapingIngestor

__version__ = "1.0.0"
__all__ = [
    "GenericBrowserBridge",
    "BaseExtractor",
    "ExtractedContent",
    "PerplexityExtractor",
    "JDIHExtractor",
    "NewsExtractor",
    "GenericExtractor",
    "FourLevelValidator",
    "ValidationResult",
    "WebScrapingIngestor",
]