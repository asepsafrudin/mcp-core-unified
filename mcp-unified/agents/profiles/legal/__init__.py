"""
Legal Agent Module - UU 23/2014 & SPM Processing
"""

from .connectors.llm_connector import LLMConnector
from .connectors.kb_connector import KBConnector
from .processors.spm_processor import SPMProcessor

__all__ = ['LLMConnector', 'KBConnector', 'SPMProcessor']
