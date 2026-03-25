"""
Role-Based Access Control (RBAC) module for MCP Unified System.

Provides role and permission management.
"""

from enum import Enum
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field


class Permission(str, Enum):
    """Standard permissions in the system."""
    # Tool permissions
    TOOLS_EXECUTE_ALL = "tools:execute:*"
    TOOLS_EXECUTE_FILE = "tools:execute:file"
    TOOLS_EXECUTE_SHELL = "tools:execute:shell"
    TOOLS_EXECUTE_CODE = "tools:execute:code"
    TOOLS_EXECUTE_MEDIA = "tools:execute:media"
    TOOLS_EXECUTE_ADMIN = "tools:execute:admin"
    
    # Agent permissions
    AGENTS_CREATE = "agents:create"
    AGENTS_EXECUTE = "agents:execute"
    AGENTS_DELETE = "agents:delete"
    AGENTS_MANAGE = "agents:manage"
    
    # Knowledge permissions
    KNOWLEDGE_READ = "knowledge:read"
    KNOWLEDGE_WRITE = "knowledge:write"
    KNOWLEDGE_DELETE = "knowledge:delete"
    
    # Memory permissions
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    MEMORY_DELETE = "memory:delete"
    
    # System permissions
    SYSTEM_CONFIG_READ = "system:config:read"
    SYSTEM_CONFIG_WRITE = "system:config:write"
    SYSTEM_LOGS_READ = "system:logs:read"
    SYSTEM_ADMIN = "system:admin"
    
    # User management
    USERS_CREATE = "users:create"
    USERS_READ = "users:read"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"
    
    # API Key management
    APIKEYS_CREATE = "apikeys:create"
    APIKEYS_READ = "apikeys:read"
    APIKEYS_REVOKE = "apikeys:revoke"


@dataclass
class Role:
    """Defines a role with its permissions."""
    name: str
    description: str
    permissions: Set[str] = field(default_factory=set)
    inherits: Optional[str] = None  # Inherit from another role
    
    def has_permission(self, permission: str) -> bool:
        """Check if role has specific permission."""
        # Direct match
        if permission in self.permissions:
            return True
        
        # Wildcard match
        parts = permission.split(":")
        for perm in self.permissions:
            if perm == "*":
                return True
            perm_parts = perm.split(":")
            if len(perm_parts) == len(parts):
                match = all(p == "*" or p == parts[i] for i, p in enumerate(perm_parts))
                if match:
                    return True
        return False
    
    def add_permission(self, permission: str):
        """Add permission to role."""
        self.permissions.add(permission)
    
    def remove_permission(self, permission: str):
        """Remove permission from role."""
        self.permissions.discard(permission)


class RBACManager:
    """
    Manages roles and permissions.
    
    Predefined roles:
    - admin: Full system access
    - developer: Can use tools and agents, limited system access
    - viewer: Read-only access
    - service: For automated services, limited permissions
    """
    
    def __init__(self):
        self._roles: Dict[str, Role] = {}
        self._user_roles: Dict[str, str] = {}  # user_id -> role_name
        self._init_default_roles()
    
    def _init_default_roles(self):
        """Initialize default system roles."""
        
        # Admin role - full access
        self._roles["admin"] = Role(
            name="admin",
            description="Full system access",
            permissions={"*"}
        )
        
        # Developer role - can use tools and agents
        self._roles["developer"] = Role(
            name="developer",
            description="Can use tools and agents",
            permissions={
                Permission.TOOLS_EXECUTE_FILE,
                Permission.TOOLS_EXECUTE_CODE,
                Permission.TOOLS_EXECUTE_MEDIA,
                Permission.AGENTS_CREATE,
                Permission.AGENTS_EXECUTE,
                Permission.AGENTS_DELETE,
                Permission.KNOWLEDGE_READ,
                Permission.KNOWLEDGE_WRITE,
                Permission.MEMORY_READ,
                Permission.MEMORY_WRITE,
                Permission.SYSTEM_CONFIG_READ,
                Permission.APIKEYS_CREATE,
                Permission.APIKEYS_READ,
                Permission.APIKEYS_REVOKE,
            }
        )
        
        # Viewer role - read-only
        self._roles["viewer"] = Role(
            name="viewer",
            description="Read-only access",
            permissions={
                Permission.KNOWLEDGE_READ,
                Permission.MEMORY_READ,
                Permission.SYSTEM_CONFIG_READ,
                Permission.SYSTEM_LOGS_READ,
            }
        )
        
        # Service role - for automated services
        self._roles["service"] = Role(
            name="service",
            description="For automated services",
            permissions={
                Permission.TOOLS_EXECUTE_FILE,
                Permission.TOOLS_EXECUTE_CODE,
                Permission.AGENTS_EXECUTE,
                Permission.KNOWLEDGE_READ,
                Permission.MEMORY_READ,
            }
        )
        
        # Restricted role - limited access
        self._roles["restricted"] = Role(
            name="restricted",
            description="Limited access, no shell or admin tools",
            permissions={
                Permission.TOOLS_EXECUTE_FILE,
                Permission.TOOLS_EXECUTE_CODE,
                Permission.KNOWLEDGE_READ,
            }
        )
    
    def create_role(
        self,
        name: str,
        description: str,
        permissions: List[str],
        inherits: Optional[str] = None
    ) -> Role:
        """Create a new custom role."""
        if name in self._roles:
            raise ValueError(f"Role '{name}' already exists")
        
        role = Role(
            name=name,
            description=description,
            permissions=set(permissions),
            inherits=inherits
        )
        
        # Inherit permissions
        if inherits and inherits in self._roles:
            parent = self._roles[inherits]
            role.permissions.update(parent.permissions)
        
        self._roles[name] = role
        return role
    
    def get_role(self, name: str) -> Optional[Role]:
        """Get role by name."""
        return self._roles.get(name)
    
    def list_roles(self) -> List[Dict]:
        """List all roles."""
        return [
            {
                "name": role.name,
                "description": role.description,
                "permissions": list(role.permissions),
                "inherits": role.inherits
            }
            for role in self._roles.values()
        ]
    
    def update_role(self, name: str, **kwargs) -> Optional[Role]:
        """Update role properties."""
        if name not in self._roles:
            return None
        
        role = self._roles[name]
        
        if "description" in kwargs:
            role.description = kwargs["description"]
        
        if "permissions" in kwargs:
            role.permissions = set(kwargs["permissions"])
        
        return role
    
    def delete_role(self, name: str) -> bool:
        """Delete a custom role. Cannot delete default roles."""
        if name in ["admin", "developer", "viewer", "service", "restricted"]:
            raise ValueError(f"Cannot delete default role '{name}'")
        
        if name in self._roles:
            del self._roles[name]
            return True
        return False
    
    def assign_role(self, user_id: str, role_name: str) -> bool:
        """Assign role to user."""
        if role_name not in self._roles:
            return False
        
        self._user_roles[user_id] = role_name
        return True
    
    def get_user_role(self, user_id: str) -> Optional[str]:
        """Get role assigned to user."""
        return self._user_roles.get(user_id)
    
    def check_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has specific permission."""
        role_name = self._user_roles.get(user_id)
        if not role_name:
            return False
        
        role = self._roles.get(role_name)
        if not role:
            return False
        
        return role.has_permission(permission)
    
    def get_user_permissions(self, user_id: str) -> Set[str]:
        """Get all permissions for a user."""
        role_name = self._user_roles.get(user_id)
        if not role_name:
            return set()
        
        role = self._roles.get(role_name)
        if not role:
            return set()
        
        return role.permissions.copy()
    
    def can_execute_tool(self, user_id: str, tool_category: str) -> bool:
        """Check if user can execute tool in category."""
        permission = f"tools:execute:{tool_category}"
        return self.check_permission(user_id, permission) or \
               self.check_permission(user_id, Permission.TOOLS_EXECUTE_ALL)


# Global RBAC manager instance
rbac_manager = RBACManager()


# Permission matrix for tools
TOOL_PERMISSIONS = {
    "write_file": Permission.TOOLS_EXECUTE_FILE,
    "read_file": Permission.TOOLS_EXECUTE_FILE,
    "list_dir": Permission.TOOLS_EXECUTE_FILE,
    "run_shell": Permission.TOOLS_EXECUTE_SHELL,
    "analyze_code": Permission.TOOLS_EXECUTE_CODE,
    "self_review": Permission.TOOLS_EXECUTE_CODE,
    "analyze_image": Permission.TOOLS_EXECUTE_MEDIA,
    "process_pdf": Permission.TOOLS_EXECUTE_MEDIA,
    "admin_shell": Permission.TOOLS_EXECUTE_ADMIN,
}