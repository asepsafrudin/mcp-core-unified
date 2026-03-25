"""
Extractors Package

Modular extractors untuk berbagai jenis website.
Setiap extractor adalah plugin yang bisa diregister secara dinamis.
"""

from .base_extractor import BaseExtractor
from .hukumonline_extractor import HukumonlineExtractor
from .jdih_extractor import JDIHExtractor
from .detik_extractor import DetikExtractor
from .generic_extractor import GenericExtractor
from .peraturan_bpk_extractor import PeraturanBPKExtractor
from .kemenkeu_extractor import KemenkeuExtractor
from .setneg_extractor import SetnegExtractor
from .kominfo_extractor import KominfoExtractor
from .kemenkumham_extractor import KemenkumhamExtractor
from .kemenpan_extractor import KemenpanExtractor
from .ojk_extractor import OJKExtractor

__all__ = [
    'BaseExtractor',
    'HukumonlineExtractor',
    'JDIHExtractor',
    'DetikExtractor',
    'GenericExtractor',
    'PeraturanBPKExtractor',
    'KemenkeuExtractor',
    'SetnegExtractor',
    'KominfoExtractor',
    'KemenkumhamExtractor',
    'KemenpanExtractor',
    'OJKExtractor',
]
