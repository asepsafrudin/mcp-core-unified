"""
Knowledge Versioning Module

Version control untuk knowledge base documents.

Features:
    - Create version snapshots
    - Compare versions (diff)
    - Rollback ke previous version
    - Version history tracking

Usage:
    from knowledge.versioning import VersionManager
    
    vm = VersionManager(pg_vector_store)
    await vm.initialize()
    
    # Create version
    version = await vm.create_version(
        namespace="shared_legal",
        description="Updated UU 23/2024"
    )
    
    # Compare versions
    diff = await vm.compare_versions("v1", "v2")
"""

from .manager import VersionManager, VersionInfo

__all__ = ["VersionManager", "VersionInfo"]
