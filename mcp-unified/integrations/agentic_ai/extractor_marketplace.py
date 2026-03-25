"""
Extractor Marketplace

System untuk share, export, dan import extractors.

Features:
- Export extractor ke JSON/Python file
- Import extractor dari file
- Extractor repository (simple registry)
- Version control untuk extractors
"""

import json
import base64
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger('ExtractorMarketplace')


class ExtractorPackage:
    """Package untuk single extractor"""
    
    def __init__(
        self,
        name: str,
        code: str,
        metadata: Dict[str, Any],
        version: str = "1.0.0"
    ):
        self.name = name
        self.code = code  # Python code as string
        self.metadata = metadata
        self.version = version
        self.created_at = datetime.now().isoformat()
        self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate checksum untuk integrity"""
        data = f"{self.name}:{self.code}:{self.version}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ke dictionary"""
        return {
            "name": self.name,
            "code": base64.b64encode(self.code.encode()).decode(),
            "metadata": self.metadata,
            "version": self.version,
            "created_at": self.created_at,
            "checksum": self.checksum
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExtractorPackage':
        """Create dari dictionary"""
        code = base64.b64decode(data["code"]).decode()
        package = cls(
            name=data["name"],
            code=code,
            metadata=data["metadata"],
            version=data.get("version", "1.0.0")
        )
        package.created_at = data.get("created_at", datetime.now().isoformat())
        return package
    
    def save_to_file(self, path: str):
        """Save package ke file"""
        file_path = Path(path)
        file_path.write_text(json.dumps(self.to_dict(), indent=2))
        logger.info(f"💾 Saved package: {file_path}")
    
    @classmethod
    def load_from_file(cls, path: str) -> 'ExtractorPackage':
        """Load package dari file"""
        file_path = Path(path)
        data = json.loads(file_path.read_text())
        return cls.from_dict(data)


class ExtractorMarketplace:
    """
    Marketplace untuk extractors.
    
    Features:
    - Local repository
    - Export/Import extractors
    - Search dan browse
    - Version management
    """
    
    def __init__(self, repo_path: Optional[str] = None):
        """
        Initialize marketplace.
        
        Args:
            repo_path: Path ke local repository
        """
        if repo_path is None:
            # Default: ~/.mcp/extractors/
            repo_path = Path.home() / ".mcp" / "extractors"
        
        self.repo_path = Path(repo_path)
        self.repo_path.mkdir(parents=True, exist_ok=True)
        
        self._packages: Dict[str, ExtractorPackage] = {}
        self._load_repository()
    
    def _load_repository(self):
        """Load semua packages dari repository"""
        for file_path in self.repo_path.glob("*.json"):
            try:
                package = ExtractorPackage.load_from_file(str(file_path))
                self._packages[package.name] = package
                logger.debug(f"📦 Loaded: {package.name}")
            except Exception as e:
                logger.error(f"❌ Failed to load {file_path}: {e}")
        
        logger.info(f"📚 Repository loaded: {len(self._packages)} packages")
    
    def export_extractor(
        self,
        extractor_class,
        output_path: Optional[str] = None
    ) -> str:
        """
        Export extractor class ke package.
        
        Args:
            extractor_class: Extractor class untuk export
            output_path: Optional custom output path
            
        Returns:
            Path ke exported file
        """
        import inspect
        
        # Get source code
        try:
            source = inspect.getsource(extractor_class)
        except TypeError:
            logger.error(f"❌ Cannot get source for {extractor_class}")
            return None
        
        # Create instance untuk metadata
        instance = extractor_class()
        metadata = {
            "url_patterns": instance.url_patterns,
            "description": instance.description,
            "author": "user",
            "tags": ["extractor", instance.name]
        }
        
        # Create package
        package = ExtractorPackage(
            name=instance.name,
            code=source,
            metadata=metadata
        )
        
        # Save ke repository
        if output_path is None:
            output_path = self.repo_path / f"{package.name}.json"
        
        package.save_to_file(str(output_path))
        self._packages[package.name] = package
        
        return str(output_path)
    
    def import_extractor(
        self,
        package_path: str,
        install: bool = True
    ) -> Optional[Any]:
        """
        Import extractor dari package.
        
        Args:
            package_path: Path ke package file
            install: Install ke extractors folder
            
        Returns:
            Extractor class atau None
        """
        try:
            # Load package
            package = ExtractorPackage.load_from_file(package_path)
            
            # Verify checksum
            expected_checksum = package._calculate_checksum()
            if package.checksum != expected_checksum:
                logger.warning(f"⚠️ Checksum mismatch for {package.name}")
            
            # Install ke extractors folder jika diminta
            if install:
                extractors_path = Path(__file__).parent / "extractors"
                py_file = extractors_path / f"{package.name}_extractor.py"
                py_file.write_text(package.code)
                logger.info(f"📥 Installed: {py_file}")
            
            # Execute code untuk dapatkan class
            namespace = {}
            exec(package.code, namespace)
            
            # Find extractor class
            for name, obj in namespace.items():
                if (isinstance(obj, type) and 
                    name != "BaseExtractor" and
                    "Extractor" in name):
                    return obj
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Import failed: {e}")
            return None
    
    def list_packages(self) -> List[Dict[str, Any]]:
        """List semua available packages"""
        return [
            {
                "name": pkg.name,
                "version": pkg.version,
                "description": pkg.metadata.get("description", ""),
                "author": pkg.metadata.get("author", "unknown"),
                "tags": pkg.metadata.get("tags", []),
                "created_at": pkg.created_at,
                "checksum": pkg.checksum
            }
            for pkg in self._packages.values()
        ]
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search packages.
        
        Args:
            query: Search query
            
        Returns:
            Matching packages
        """
        query_lower = query.lower()
        results = []
        
        for pkg in self._packages.values():
            # Search di name
            if query_lower in pkg.name.lower():
                results.append(self._package_info(pkg))
                continue
            
            # Search di description
            description = pkg.metadata.get("description", "").lower()
            if query_lower in description:
                results.append(self._package_info(pkg))
                continue
            
            # Search di tags
            tags = pkg.metadata.get("tags", [])
            if any(query_lower in tag.lower() for tag in tags):
                results.append(self._package_info(pkg))
                continue
        
        return results
    
    def _package_info(self, package: ExtractorPackage) -> Dict[str, Any]:
        """Get package info dict"""
        return {
            "name": package.name,
            "version": package.version,
            "description": package.metadata.get("description", ""),
            "url_patterns": package.metadata.get("url_patterns", []),
            "author": package.metadata.get("author", "unknown"),
            "tags": package.metadata.get("tags", []),
            "created_at": package.created_at
        }
    
    def get_package(self, name: str) -> Optional[ExtractorPackage]:
        """Get package by name"""
        return self._packages.get(name)
    
    def delete_package(self, name: str) -> bool:
        """Delete package dari repository"""
        if name in self._packages:
            package = self._packages[name]
            file_path = self.repo_path / f"{package.name}.json"
            
            if file_path.exists():
                file_path.unlink()
            
            del self._packages[name]
            logger.info(f"🗑️ Deleted: {name}")
            return True
        
        return False
    
    def share_package(self, name: str) -> Optional[str]:
        """
        Generate shareable code untuk package.
        
        Returns:
            Base64 encoded package atau None
        """
        package = self._packages.get(name)
        if not package:
            return None
        
        # Convert ke compact JSON dan encode
        json_data