"""
Base Extractor

Abstract base class untuk semua extractors.
Setiap website-specific extractor harus inherit dari class ini.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class ExtractionConfig:
    """Configuration untuk extraction"""
    timeout: int = 30
    wait_for: str = "domcontentloaded"
    scroll_count: int = 3
    js_render_wait: int = 3
    min_title_length: int = 5
    required_fields: List[str] = None
    optional_fields: List[str] = None
    
    def __post_init__(self):
        if self.required_fields is None:
            self.required_fields = ["title"]
        if self.optional_fields is None:
            self.optional_fields = ["content", "url", "author", "date"]


class BaseExtractor(ABC):
    """
    Abstract base class untuk web extractors.
    
    Usage:
        class MyExtractor(BaseExtractor):
            @property
            def name(self) -> str:
                return "my_extractor"
            
            @property
            def url_patterns(self) -> List[str]:
                return ["mywebsite.com"]
            
            async def extract(self, page) -> List[Dict[str, Any]]:
                # Implementation
                pass
    """
    
    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nama unik extractor"""
        pass
    
    @property
    @abstractmethod
    def url_patterns(self) -> List[str]:
        """List URL patterns yang bisa dihandle oleh extractor ini"""
        pass
    
    @property
    def description(self) -> str:
        """Deskripsi extractor (opsional)"""
        return f"{self.name} extractor"
    
    def can_handle(self, url: str) -> bool:
        """Check apakah extractor ini bisa handle URL tertentu"""
        url_lower = url.lower()
        return any(pattern.lower() in url_lower for pattern in self.url_patterns)
    
    @abstractmethod
    async def extract(self, page) -> List[Dict[str, Any]]:
        """
        Extract data dari page.
        
        Args:
            page: Playwright page object
            
        Returns:
            List of extracted items
        """
        pass
    
    async def pre_process(self, page):
        """
        Pre-processing sebelum extraction (opsional).
        Contoh: scroll, wait for elements, etc.
        """
        # Default: wait untuk JS render
        import asyncio
        await asyncio.sleep(self.config.js_render_wait)
        
        # Default: scroll untuk trigger lazy load
        for i in range(self.config.scroll_count):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(1.5)
    
    async def post_process(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Post-processing hasil extraction (opsional).
        Contoh: clean data, filter, etc.
        """
        return items
    
    def validate_item(self, item: Dict[str, Any]) -> bool:
        """
        Validate single item.
        
        Returns:
            True jika item valid
        """
        # Check required fields
        for field in self.config.required_fields:
            value = item.get(field, "")
            if not value or len(str(value).strip()) < self.config.min_title_length:
                return False
        return True
    
    def get_strategy(self) -> Dict[str, Any]:
        """Get strategy configuration untuk extractor ini"""
        return {
            "extractor": self.name,
            "timeout": self.config.timeout,
            "wait_for": self.config.wait_for,
            "extraction_mode": self.name,
            "validation_rules": {
                "required_fields": self.config.required_fields,
                "optional_fields": self.config.optional_fields,
                "min_content_length": 1
            }
        }
