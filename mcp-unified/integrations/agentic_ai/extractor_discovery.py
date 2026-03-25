"""
Extractor Discovery

Auto-discovery system untuk extractors.
Scan folder extractors dan auto-register tanpa manual import.
"""

import os
import sys
import importlib
import inspect
import logging
from pathlib import Path
from typing import List, Type, Optional

# Import base extractor
from .extractors.base_extractor import BaseExtractor

logger = logging.getLogger('ExtractorDiscovery')


class ExtractorDiscovery:
    """
    Auto-discovery untuk extractors.
    
    Features:
    - Scan folder untuk extractor classes
    - Auto-import dan register
    - Support dynamic reload
    - Validate extractor integrity
    """
    
    def __init__(self, extractors_path: Optional[str] = None):
        """
        Initialize discovery.
        
        Args:
            extractors_path: Path ke folder extractors (default: extractors/)
        """
        if extractors_path is None:
            # Default: extractors/ folder di package ini
            current_file = Path(__file__).parent
            extractors_path = current_file / "extractors"
        
        self.extractors_path = Path(extractors_path)
        self._discovered: List[Type[BaseExtractor]] = []
    
    def discover(self) -> List[Type[BaseExtractor]]:
        """
        Discover semua extractors di folder.
        
        Returns:
            List of extractor classes
        """
        logger.info(f"🔍 Discovering extractors in: {self.extractors_path}")
        
        discovered = []
        
        # Ensure path exists
        if not self.extractors_path.exists():
            logger.error(f"❌ Extractors path not found: {self.extractors_path}")
            return discovered
        
        # Scan untuk Python files
        for file_path in self.extractors_path.glob("*_extractor.py"):
            try:
                extractor_class = self._load_extractor(file_path)
                if extractor_class:
                    discovered.append(extractor_class)
                    logger.info(f"✅ Discovered: {extractor_class.__name__}")
            except Exception as e:
                logger.error(f"❌ Failed to load {file_path}: {e}")
        
        self._discovered = discovered
        logger.info(f"📊 Total extractors discovered: {len(discovered)}")
        
        return discovered
    
    def _load_extractor(self, file_path: Path) -> Optional[Type[BaseExtractor]]:
        """
        Load single extractor dari file.
        
        Args:
            file_path: Path ke extractor file
            
        Returns:
            Extractor class atau None
        """
        # Get module name (e.g., "hukumonline_extractor")
        module_name = file_path.stem
        
        # Skip base extractor
        if module_name == "base_extractor":
            return None
        
        # Add parent to path untuk import
        parent_path = str(self.extractors_path.parent)
        if parent_path not in sys.path:
            sys.path.insert(0, parent_path)
        
        # Import module
        full_module_name = f"extractors.{module_name}"
        try:
            module = importlib.import_module(full_module_name)
        except ImportError:
            # Try alternative import path
            full_module_name = f"mcp_unified.integrations.agentic_ai.extractors.{module_name}"
            module = importlib.import_module(full_module_name)
        
        # Find extractor class dalam module
        for name, obj in inspect.getmembers(module):
            # Check if class (not imported)
            if inspect.isclass(obj) and obj.__module__ == module.__name__:
                # Check if subclass of BaseExtractor
                if issubclass(obj, BaseExtractor) and obj is not BaseExtractor:
                    return obj
        
        return None
    
    def get_extractor_info(self, extractor_class: Type[BaseExtractor]) -> dict:
        """
        Get info tentang extractor.
        
        Args:
            extractor_class: Extractor class
            
        Returns:
            Dict dengan metadata
        """
        try:
            # Create instance untuk dapatkan properties
            instance = extractor_class()
            
            return {
                "name": instance.name,
                "description": instance.description,
                "url_patterns": instance.url_patterns,
                "class_name": extractor_class.__name__,
                "module": extractor_class.__module__,
                "file": inspect.getfile(extractor_class)
            }
        except Exception as e:
            return {
                "class_name": extractor_class.__name__,
                "error": str(e)
            }
    
    def list_extractors(self) -> List[dict]:
        """List semua discovered extractors dengan info"""
        if not self._discovered:
            self.discover()
        
        return [self.get_extractor_info(ext) for ext in self._discovered]
    
    def register_to_registry(self, registry) -> int:
        """
        Register discovered extractors ke registry.
        
        Args:
            registry: ExtractorRegistry instance
            
        Returns:
            Number of extractors registered
        """
        if not self._discovered:
            self.discover()
        
        count = 0
        for extractor_class in self._discovered:
            try:
                registry.register(extractor_class)
                count += 1
            except Exception as e:
                logger.error(f"❌ Failed to register {extractor_class.__name__}: {e}")
        
        return count


# Convenience function
def discover_extractors(extractors_path: Optional[str] = None) -> List[Type[BaseExtractor]]:
    """
    Discover extractors dengan default settings.
    
    Args:
        extractors_path: Optional custom path
        
    Returns:
        List of extractor classes
    """
    discovery = ExtractorDiscovery(extractors_path)
    return discovery.discover()
