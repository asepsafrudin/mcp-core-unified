"""
Role-Based Access Control (RBAC) Module

Provides comprehensive access control untuk knowledge namespaces.
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Permission(Enum):
    """Available permissions."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


class Role(Enum):
    """User roles."""
    ADMIN = "admin"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


@dataclass
class RBACRule:
    """Single RBAC rule."""
    namespace: str
    role: Role
    permissions: Set[Permission]


class RBACManager:
    """
    Role-Based Access Control Manager.
    
    Features:
        - Role hierarchy (admin > reviewer > viewer)
        - Namespace-level permissions
        - Permission matrix
        - Audit logging
    """
    
    # Default permission matrix
    DEFAULT_PERMISSIONS: Dict[Role, Dict[str, Set[Permission]]] = {
        Role.ADMIN: {
            "shared_legal": {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
            "shared_admin": {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
            "shared_tech": {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
            "shared_general": {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
        },
        Role.REVIEWER: {
            "shared_legal": {Permission.READ, Permission.WRITE},
            "shared_admin": {Permission.READ, Permission.WRITE},
            "shared_tech": {Permission.READ},
            "shared_general": {Permission.READ, Permission.WRITE},
        },
        Role.VIEWER: {
            "shared_legal": {Permission.READ},
            "shared_admin": {Permission.READ},
            "shared_tech": {Permission.READ},
            "shared_general": {Permission.READ},
        }
    }
    
    def __init__(self):
        self._permissions: Dict[Role, Dict[str, Set[Permission]]] = {
            role: dict(perms) for role, perms in self.DEFAULT_PERMISSIONS.items()
        }
        self._audit_log: List[Dict] = []
    
    def can_access(
        self, 
        namespace: str, 
        role: str, 
        permission: str = "read"
    ) -> bool:
        """
        Check jika role punya permission untuk namespace.
        
        Args:
            namespace: Namespace name
            role: User role (admin, reviewer, viewer)
            permission: Permission to check (read, write, delete, admin)
        
        Returns:
            True if allowed, False otherwise
        """
        try:
            role_enum = Role(role.lower())
            perm_enum = Permission(permission.lower())
        except ValueError:
            return False
        
        role_perms = self._permissions.get(role_enum, {})
        ns_perms = role_perms.get(namespace, set())
        
        return perm_enum in ns_perms
    
    def check_permission(
        self,
        namespace: str,
        role: str,
        permission: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Check permission dengan audit logging.
        
        Returns:
            True if allowed
        """
        allowed = self.can_access(namespace, role, permission)
        
        self._audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": "permission_check",
            "namespace": namespace,
            "role": role,
            "permission": permission,
            "user_id": user_id,
            "result": "allowed" if allowed else "denied"
        })
        
        return allowed
    
    def can_create_namespace(self, role: str) -> bool:
        """Hanya admin yang bisa create namespace."""
        return role.lower() == "admin"
    
    def can_delete_namespace(self, role: str, namespace: str) -> bool:
        """Check delete namespace permission."""
        return self.can_access(namespace, role, "admin")
    
    def can_ingest_document(self, role: str, namespace: str) -> bool:
        """Check document ingestion permission."""
        return self.can_access(namespace, role, "write")
    
    def can_delete_document(self, role: str, namespace: str) -> bool:
        """Check document deletion permission."""
        return self.can_access(namespace, role, "delete")
    
    def get_permissions(self, role: str, namespace: Optional[str] = None) -> List[str]:
        """
        Get all permissions untuk role.
        
        Args:
            role: User role
            namespace: Optional namespace filter
        
        Returns:
            List of permission strings
        """
        try:
            role_enum = Role(role.lower())
        except ValueError:
            return []
        
        role_perms = self._permissions.get(role_enum, {})
        
        if namespace:
            perms = role_perms.get(namespace, set())
            return [p.value for p in perms]
        else:
            # Return all permissions across all namespaces
            all_perms = set()
            for perms in role_perms.values():
                all_perms.update(perms)
            return [p.value for p in all_perms]
    
    def list_accessible_namespaces(self, role: str) -> List[str]:
        """List semua namespaces yang accessible oleh role."""
        try:
            role_enum = Role(role.lower())
        except ValueError:
            return []
        
        role_perms = self._permissions.get(role_enum, {})
        return list(role_perms.keys())
    
    def add_permission(
        self, 
        role: str, 
        namespace: str, 
        permission: str,
        changed_by: Optional[str] = None
    ) -> bool:
        """
        Add permission untuk role.
        
        Returns:
            True if successful
        """
        try:
            role_enum = Role(role.lower())
            perm_enum = Permission(permission.lower())
        except ValueError:
            return False
        
        if role_enum not in self._permissions:
            self._permissions[role_enum] = {}
        
        if namespace not in self._permissions[role_enum]:
            self._permissions[role_enum][namespace] = set()
        
        self._permissions[role_enum][namespace].add(perm_enum)
        
        self._audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": "permission_added",
            "role": role,
            "namespace": namespace,
            "permission": permission,
            "changed_by": changed_by
        })
        
        return True
    
    def remove_permission(
        self, 
        role: str, 
        namespace: str, 
        permission: str,
        changed_by: Optional[str] = None
    ) -> bool:
        """Remove permission dari role."""
        try:
            role_enum = Role(role.lower())
            perm_enum = Permission(permission.lower())
        except ValueError:
            return False
        
        if role_enum in self._permissions and namespace in self._permissions[role_enum]:
            self._permissions[role_enum][namespace].discard(perm_enum)
            
            self._audit_log.append({
                "timestamp": datetime.now().isoformat(),
                "action": "permission_removed",
                "role": role,
                "namespace": namespace,
                "permission": permission,
                "changed_by": changed_by
            })
            
            return True
        
        return False
    
    def get_role_hierarchy(self) -> Dict[str, int]:
        """
        Get role hierarchy levels.
        
        Returns:
            Dict mapping role to level (higher = more privileges)
        """
        return {
            "admin": 3,
            "reviewer": 2,
            "viewer": 1
        }
    
    def compare_roles(self, role1: str, role2: str) -> int:
        """
        Compare two roles.
        
        Returns:
            1 if role1 > role2, -1 if role1 < role2, 0 if equal
        """
        hierarchy = self.get_role_hierarchy()
        level1 = hierarchy.get(role1.lower(), 0)
        level2 = hierarchy.get(role2.lower(), 0)
        
        if level1 > level2:
            return 1
        elif level1 < level2:
            return -1
        return 0
    
    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """Get RBAC audit log."""
        return self._audit_log[-limit:]


# Global instance
_rbac_manager: Optional[RBACManager] = None


def get_rbac_manager() -> RBACManager:
    """Get global RBAC manager."""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager
