"""
Base Extractor - Abstract base class untuk semua extractors.

Mendefinisikan interface standar untuk ekstraksi konten dari website.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


@dataclass
class ExtractedContent:
    """
    Hasil ekstraksi konten dari website.
    
    Attributes:
        url: URL sumber
        title: Judul konten
        content: Konten utama (text)
        html: HTML mentah (optional)
        author: Penulis (optional)
        published_date: Tanggal publikasi (optional)
        metadata: Metadata tambahan
        extracted_at: Waktu ekstraksi
        content_hash: Hash untuk deduplication
    """
    url: str
    title: str
    content: str
    html: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=datetime.now)
    content_hash: Optional[str] = None
    
    def __post_init__(self):
        """Generate content hash jika belum ada."""
        if not self.content_hash:
            import hashlib
            self.content_hash = hashlib.sha256(
                f"{self.url}:{self.content}".encode()
            ).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ke dictionary."""
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "author": self.author,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "metadata": self.metadata,
            "extracted_at": self.extracted_at.isoformat(),
            "content_hash": self.content_hash,
        }


class BaseExtractor(ABC):
    """
    Abstract base class untuk semua content extractors.
    
    Setiap extractor harus mengimplementasikan:
    - can_handle(url): Cek apakah extractor bisa handle URL ini
    - extract(page): Ekstrak konten dari Playwright page
    """
    
    # URL patterns yang didukung (override di subclass)
    URL_PATTERNS: List[str] = []
    
    # Domain yang didukung (override di subclass)
    DOMAINS: List[str] = []
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize extractor.
        
        Args:
            config: Konfigurasi opsional untuk extractor
        """
        self.config = config or {}
        self.name = self.__class__.__name__
    
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """
        Cek apakah extractor ini bisa menangani URL tersebut.
        
        Args:
            url: URL yang akan dicek
            
        Returns:
            True jika extractor bisa handle URL ini
        """
        pass
    
    @abstractmethod
    async def extract(self, page) -> ExtractedContent:
        """
        Ekstrak konten dari Playwright page.
        
        Args:
            page: Playwright page object
            
        Returns:
            ExtractedContent object
        """
        pass
    
    def validate(self, content: ExtractedContent) -> bool:
        """
        Validasi hasil ekstraksi.
        
        Args:
            content: Hasil ekstraksi
            
        Returns:
            True jika valid
        """
        # Basic validation
        if not content.url or not content.title or not content.content:
            return False
        
        # Content length check
        if len(content.content) < 100:  # Minimal 100 karakter
            return False
        
        return True
    
    def _get_domain(self, url: str) -> str:
        """Extract domain dari URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()
    
    def _match_url_pattern(self, url: str) -> bool:
        """
        Cek apakah URL match dengan pattern yang didukung.
        
        Args:
            url: URL yang akan dicek
            
        Returns:
            True jika match
        """
        import fnmatch
        
        for pattern in self.URL_PATTERNS:
            if fnmatch.fnmatch(url, pattern):
                return True
        
        # Check domain
        domain = self._get_domain(url)
        for supported_domain in self.DOMAINS:
            if supported_domain in domain:
                return True
        
        return False
    
    async def _safe_evaluate(self, page, script: str, default: Any = None) -> Any:
        """
        Safely evaluate JavaScript di page.
        
        Args:
            page: Playwright page
            script: JavaScript code
            default: Default value jika error
            
        Returns:
            Hasil evaluasi atau default
        """
        try:
            return await page.evaluate(script)
        except Exception as e:
            print(f"[WARNING] Script evaluation failed: {e}")
            return default
    
    async def _wait_for_selector(
        self, 
        page, 
        selector: str, 
        timeout: int = 10000,
        state: str = "visible"
    ) -> bool:
        """
        Wait untuk selector dengan error handling.
        
        Args:
            page: Playwright page
            selector: CSS selector
            timeout: Timeout dalam ms
            state: State yang ditunggu (visible, hidden, attached, detached)
            
        Returns:
            True jika element ditemukan
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout, state=state)
            return True
        except Exception:
            return False
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text.
        
        Args:
            text: Text mentah
            
        Returns:
            Text yang sudah diclean
        """
        if not text:
            return ""
        
        # Remove extra whitespace
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _extract_date(self, date_str: str) -> Optional[datetime]:
        """
        Extract datetime dari string.
        
        Args:
            date_str: String tanggal
            
        Returns:
            datetime object atau None
        """
        from dateutil import parser
        
        try:
            return parser.parse(date_str)
        except Exception:
            return None