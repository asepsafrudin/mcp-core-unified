"""
Namespace Manager

Manage shared namespaces untuk knowledge sharing antar agent.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import sys
from pathlib import Path

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from knowledge.admin.rbac import get_rbac_manager, RBACManager


class NamespaceManager:
    """
    Manage shared knowledge namespaces.
    
    Shared namespaces:
        - shared_legal: Dokumen hukum dan regulasi
        - shared_admin: Prosedur administrasi
        - shared_tech: Dokumentasi teknis
        - shared_general: Dokumen umum
    """
    
    DEFAULT_NAMESPACES = {
        "shared_legal": {
            "description": "Dokumen hukum, regulasi, dan perundang-undangan",
            "access": "all_agents",
            "tags": ["hukum", "regulasi", "UU", "Perpres"]
        },
        "shared_admin": {
            "description": "Prosedur administrasi dan SOP",
            "access": "all_agents",
            "tags": ["admin", "SOP", "prosedur"]
        },
        "shared_tech": {
            "description": "Dokumentasi teknis dan teknologi",
            "access": "all_agents",
            "tags": ["tech", "dokumentasi", "manual"]
        },
        "shared_general": {
            "description": "Dokumen umum dan miscellaneous",
            "access": "all_agents",
            "tags": ["general", "misc"]
        }
    }
    
    def __init__(self, knowledge_engine=None):
        """
        Initialize namespace manager.
        
        Args:
            knowledge_engine: Instance RAGEngine untuk query
        """
        self.knowledge = knowledge_engine
        self._namespaces: Dict[str, Dict] = {}
        self._initialize_default_namespaces()
    
    def _initialize_default_namespaces(self):
        """Initialize default shared namespaces."""
        for ns_name, ns_config in self.DEFAULT_NAMESPACES.items():
            self._namespaces[ns_name] = {
                **ns_config,
                "created_at": datetime.now().isoformat(),
                "document_count": 0,
                "last_updated": None
            }
    
    async def list_namespaces(
        self,
        agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List semua available namespaces untuk agent.
        
        Args:
            agent_id: ID agent (untuk permission check)
            
        Returns:
            List of namespace info
        """
        result = []
        
        for ns_name, ns_info in self._namespaces.items():
            # Check access permission
            if self._can_access(ns_name, agent_id):
                # Get document count dari knowledge engine jika tersedia
                doc_count = await self._get_document_count(ns_name)
                
                result.append({
                    "name": ns_name,
                    "description": ns_info["description"],
                    "access": ns_info["access"],
                    "tags": ns_info["tags"],
                    "document_count": doc_count,
                    "created_at": ns_info["created_at"],
                    "last_updated": ns_info.get("last_updated")
                })
        
        return result
    
    async def get_namespace_info(
        self,
        namespace: str,
        agent_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed info tentang namespace.
        
        Args:
            namespace: Namespace name
            agent_id: ID agent
            
        Returns:
            Namespace info atau None jika tidak ada/tidak accessible
        """
        if namespace not in self._namespaces:
            return None
        
        if not self._can_access(namespace, agent_id):
            return None
        
        ns_info = self._namespaces[namespace]
        doc_count = await self._get_document_count(namespace)
        
        return {
            "name": namespace,
            "description": ns_info["description"],
            "access": ns_info["access"],
            "tags": ns_info["tags"],
            "document_count": doc_count,
            "created_at": ns_info["created_at"],
            "last_updated": ns_info.get("last_updated")
        }
    
    async def search_across_namespaces(
        self,
        query: str,
        namespaces: Optional[List[str]] = None,
        top_k: int = 5,
        agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search di multiple namespaces.
        
        Args:
            query: Query text
            namespaces: List namespaces untuk search (None = all accessible)
            top_k: Jumlah results per namespace
            agent_id: ID agent
            
        Returns:
            Combined results dari semua namespaces
        """
        if namespaces is None:
            # Get all accessible namespaces
            ns_list = await self.list_namespaces(agent_id)
            namespaces = [ns["name"] for ns in ns_list]
        
        all_results = []
        
        for ns in namespaces:
            if not self._can_access(ns, agent_id):
                continue
            
            # Query knowledge engine
            if self.knowledge:
                try:
                    results = await self.knowledge.query(
                        query_text=query,
                        namespace=ns,
                        top_k=top_k
                    )
                    
                    for r in results:
                        r["namespace"] = ns
                        r["source_agent"] = r.get("metadata", {}).get("source_agent")
                    
                    all_results.extend(results)
                except Exception as e:
                    # Log error tapi continue dengan namespace lain
                    print(f"Error querying {ns}: {e}")
        
        # Sort by relevance score
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return all_results[:top_k * len(namespaces)]
    
    def create_namespace(
        self,
        name: str,
        description: str,
        access: str = "all_agents",
        tags: Optional[List[str]] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create new shared namespace.
        
        Args:
            name: Namespace name (harus unik)
            description: Deskripsi namespace
            access: Access level ("all_agents" atau "restricted")
            tags: List tags
            created_by: ID creator
            
        Returns:
            Created namespace info
        """
        if name in self._namespaces:
            raise ValueError(f"Namespace {name} sudah ada")
        
        if not name.startswith("shared_"):
            name = f"shared_{name}"
        
        self._namespaces[name] = {
            "description": description,
            "access": access,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "created_by": created_by,
            "document_count": 0,
            "last_updated": datetime.now().isoformat()
        }
        
        return {
            "name": name,
            "description": description,
            "access": access,
            "tags": tags or [],
            "created_at": self._namespaces[name]["created_at"]
        }
    
    def _can_access(
        self, 
        namespace: str, 
        agent_id: Optional[str] = None,
        role: Optional[str] = None,
        permission: str = "read"
    ) -> bool:
        """
        Check jika agent bisa akses namespace dengan RBAC.
        
        Args:
            namespace: Namespace name
            agent_id: ID agent
            role: User role (admin, reviewer, viewer)
            permission: Permission type (read, write, delete, admin)
        """
        if namespace not in self._namespaces:
            return False
        
        # Get RBAC manager
        rbac = get_rbac_manager()
        
        # If role provided, use RBAC
        if role:
            return rbac.can_access(namespace, role, permission)
        
        # Default: check if namespace allows all agents
        ns_info = self._namespaces[namespace]
        if ns_info["access"] == "all_agents":
            return True
        
        return False
    
    async def list_namespaces_with_auth(
        self,
        token: str,
        auth_manager=None
    ) -> List[Dict[str, Any]]:
        """
        List namespaces dengan RBAC authentication.
        
        Args:
            token: Auth token
            auth_manager: Auth manager instance
        
        Returns:
            List of accessible namespaces
        """
        if auth_manager is None:
            from knowledge.admin.auth import get_auth_manager
            auth_manager = get_auth_manager()
        
        # Verify token
        auth = auth_manager.verify_token(token)
        if not auth:
            raise PermissionError("Invalid or expired token")
        
        # Get RBAC manager
        rbac = get_rbac_manager()
        
        # Get accessible namespaces for role
        accessible_ns = rbac.list_accessible_namespaces(auth.role)
        
        result = []
        for ns_name in accessible_ns:
            if ns_name not in self._namespaces:
                continue
            
            ns_info = self._namespaces[ns_name]
            doc_count = await self._get_document_count(ns_name)
            
            # Get permissions for this namespace
            permissions = rbac.get_permissions(auth.role, ns_name)
            
            result.append({
                "name": ns_name,
                "description": ns_info["description"],
                "access": ns_info["access"],
                "tags": ns_info["tags"],
                "document_count": doc_count,
                "created_at": ns_info["created_at"],
                "last_updated": ns_info.get("last_updated"),
                "permissions": permissions
            })
        
        return result
    
    async def _get_document_count(self, namespace: str) -> int:
        """
        Get document count untuk namespace.
        
        Note: Implementasi sebenarnya akan query knowledge engine.
        """
        if self.knowledge:
            try:
                # Query count dari knowledge base
                # Ini placeholder - implementasi sebenarnya tergantung
                # pada interface knowledge engine
                return self._namespaces[namespace].get("document_count", 0)
            except:
                pass
        
        return self._namespaces[namespace].get("document_count", 0)
    
    def update_document_count(self, namespace: str, delta: int = 1):
        """
        Update document count untuk namespace.
        
        Args:
            namespace: Namespace name
            delta: Perubahan count (+1 untuk add, -1 untuk remove)
        """
        if namespace in self._namespaces:
            current = self._namespaces[namespace].get("document_count", 0)
            self._namespaces[namespace]["document_count"] = max(0, current + delta)
            self._namespaces[namespace]["last_updated"] = datetime.now().isoformat()
    
    def suggest_namespace(self, filename: str, content_preview: str = "") -> str:
        """
        Suggest namespace berdasarkan filename dan content.
        
        Args:
            filename: Nama file
            content_preview: Preview konten
            
        Returns:
            Suggested namespace name
        """
        filename_lower = filename.lower()
        content_lower = content_preview.lower()
        
        # Legal keywords
        legal_keywords = ['uu', 'undang-undang', 'perpres', 'permen', 
                         'regulasi', 'hukum', 'legal', 'sk']
        if any(kw in filename_lower or kw in content_lower for kw in legal_keywords):
            return "shared_legal"
        
        # Admin keywords
        admin_keywords = ['sop', 'prosedur', 'administrasi', 'form', 
                         'surat', 'memo']
        if any(kw in filename_lower or kw in content_lower for kw in admin_keywords):
            return "shared_admin"
        
        # Tech keywords
        tech_keywords = ['tech', 'technical', 'manual', 'guide', 
                        'documentation', 'api']
        if any(kw in filename_lower or kw in content_lower for kw in tech_keywords):
            return "shared_tech"
        
        # Default
        return "shared_general"