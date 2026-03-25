"""
Extractor Registry

Central registry untuk mengelola semua extractors.
Pattern: Plugin Architecture
"""

import logging
from typing import Dict, List, Type, Optional, Any

try:
    from .extractors.base_extractor import BaseExtractor
except ImportError:
    # Fallback for direct execution
    from extractors.base_extractor import BaseExtractor

logger = logging.getLogger('ExtractorRegistry')


class ExtractorRegistry:
    """
    Registry untuk extractors.
    
    Usage:
        registry = ExtractorRegistry()
        registry.register(HukumonlineExtractor)
        registry.register(JDIHExtractor)
        
        extractor = registry.get_extractor_for_url("https://www.hukumonline.com/berita")
        if extractor:
            data = await extractor.extract(page)
    """
    
    def __init__(self):
        self._extractors: Dict[str, BaseExtractor] = {}
        self._extractor_classes: Dict[str, Type[BaseExtractor]] = {}
    
    def register(self, extractor_class: Type[BaseExtractor]) -> 'ExtractorRegistry':
        """
        Register extractor class.
        
        Args:
            extractor_class: Class yang inherit dari BaseExtractor
            
        Returns:
            Self untuk chaining
        """
        try:
            # Create instance untuk dapatkan metadata
            instance = extractor_class()
            name = instance.name
            
            self._extractor_classes[name] = extractor_class
            self._extractors[name] = instance
            
            logger.info(f"✅ Registered extractor: {name} ({instance.description})")
            
        except Exception as e:
            logger.error(f"❌ Failed to register extractor {extractor_class}: {e}")
        
        return self
    
    def unregister(self, name: str) -> bool:
        """Unregister extractor by name"""
        if name in self._extractors:
            del self._extractors[name]
            del self._extractor_classes[name]
            logger.info(f"🗑️ Unregistered extractor: {name}")
            return True
        return False
    
    def get_extractor(self, name: str) -> Optional[BaseExtractor]:
        """Get extractor by name"""
        return self._extractors.get(name)
    
    def get_extractor_for_url(self, url: str) -> Optional[BaseExtractor]:
        """
        Find extractor yang bisa handle URL tertentu.
        
        Args:
            url: URL untuk dicheck
            
        Returns:
            Extractor instance atau None
        """
        for extractor in self._extractors.values():
            if extractor.can_handle(url):
                logger.info(f"🔍 Found extractor for URL: {extractor.name}")
                return extractor
        
        logger.warning(f"⚠️ No extractor found for URL: {url}")
        return None
    
    def list_extractors(self) -> List[Dict[str, Any]]:
        """List semua registered extractors"""
        return [
            {
                "name": ext.name,
                "description": ext.description,
                "url_patterns": ext.url_patterns
            }
            for ext in self._extractors.values()
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return {
            "total_extractors": len(self._extractors),
            "extractor_names": list(self._extractors.keys()),
            "all_url_patterns": [
                pattern 
                for ext in self._extractors.values() 
                for pattern in ext.url_patterns
            ]
        }


# Global registry instance
_registry: Optional[ExtractorRegistry] = None


def get_registry() -> ExtractorRegistry:
    """Get atau create global registry instance"""
    global _registry
    if _registry is None:
        _registry = ExtractorRegistry()
        _register_default_extractors()
    return _registry


def _register_default_extractors():
    """Register default extractors"""
    global _registry
    
    try:
        try:
            from .extractors import (
                HukumonlineExtractor,
                JDIHExtractor,
                DetikExtractor,
                GenericExtractor
            )
        except ImportError:
            from extractors import (
                HukumonlineExtractor,
                JDIHExtractor,
                DetikExtractor,
                GenericExtractor
            )
        
        _registry.register(HukumonlineExtractor)
        _registry.register(JDIHExtractor)
        _registry.register(DetikExtractor)
        _registry.register(GenericExtractor)
        
        logger.info(f"✅ Registered {_registry.get_stats()['total_extractors']} default extractors")
        
    except Exception as e:
        logger.error(f"❌ Failed to register default extractors: {e}")


def reset_registry():
    """Reset global registry (useful untuk testing)"""
    global _registry
    _registry = None
