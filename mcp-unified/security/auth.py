"""
Authentication module for MCP Unified System.

Provides API Key authentication with bcrypt hashing and JWT session management.
"""

import os
import logging
import uuid
import bcrypt
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from functools import wraps
import jwt
from mcp.server.fastmcp import Context


# Module-level logger
logger = logging.getLogger(__name__)


@dataclass
class APIKey:
    """Represents an API key with metadata."""
    key_id: str
    key_hash: str  # bcrypt hashed key (includes salt)
    name: str
    owner: str
    role: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True
    permissions: list = field(default_factory=list)
    rate_limit: int = 1000  # requests per hour
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """Represents a user session."""
    session_id: str
    user_id: str
    role: str
    permissions: list
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True


class AuthManager:
    """
    Manages authentication for MCP Unified System.
    
    Security Features:
    - API Key hashing with bcrypt (adaptive cost, built-in salt)
    - JWT session management
    - Rate limiting per key
    - Key expiration support
    """
    
    def __init__(self, jwt_secret: Optional[str] = None):
        # JWT secret MUST come from environment in production
        self.jwt_secret = jwt_secret or os.getenv("JWT_SECRET")
        if not self.jwt_secret:
            if os.getenv("MCP_ENV") == "development":
                self.jwt_secret = secrets.token_hex(32)
                logger.warning("JWT_SECRET not set, using generated secret for development only!")
            else:
                raise ValueError(
                    "JWT_SECRET environment variable is required in production. "
                    "Generate one with: openssl rand -hex 32"
                )
        
        self._api_keys: Dict[str, APIKey] = {}  # key_id -> APIKey
        self._sessions: Dict[str, Session] = {}  # session_id -> Session
        self._rate_limits: Dict[str, list] = {}  # key_id -> [timestamps]
        
        # Initialize default admin key if in dev mode
        if os.getenv("MCP_ENV") == "development":
            self._init_dev_keys()
    
    def _init_dev_keys(self):
        """Initialize development keys."""
        dev_key = "mcp-dev-key-" + secrets.token_hex(16)
        key_id, _ = self.create_api_key(
            name="Development Key",
            owner="developer",
            role="admin",
            raw_key=dev_key
        )
        # Persist latest dev key for local tooling (dev only)
        try:
            dev_key_path = "/tmp/mcp_dev_api_key.txt"
            with open(dev_key_path, "w", encoding="utf-8") as f:
                f.write(dev_key)
            try:
                os.chmod(dev_key_path, 0o600)
            except Exception:
                pass
        except Exception:
            pass

        # Print to stdout so it's visible in nohup logs even if logging config is not initialized yet
        print(f"[DEV] API Key created: {dev_key}")
        print(f"[DEV] Key ID: {key_id}")
        logger.info("[DEV] API Key created: %s", dev_key)
        logger.info("[DEV] Key ID: %s", key_id)
    
    def _hash_key(self, raw_key: str) -> str:
        """
        Hash API key using bcrypt with salt.
        
        bcrypt is preferred over SHA-256 because:
        - Built-in salt prevents rainbow table attacks
        - Configurable work factor (adaptive)
        - Industry standard for credential hashing
        """
        # bcrypt has maximum input length of 72 bytes
        # For longer keys, we pre-hash with SHA-256 then bcrypt
        key_bytes = raw_key.encode('utf-8')
        if len(key_bytes) > 72:
            import hashlib
            key_bytes = hashlib.sha256(key_bytes).digest()
        
        # bcrypt automatically generates and embeds salt
        hashed = bcrypt.hashpw(key_bytes, bcrypt.gensalt(rounds=12))
        return hashed.decode('utf-8')
    
    def _verify_key(self, raw_key: str, stored_hash: str) -> bool:
        """Verify API key against stored bcrypt hash."""
        key_bytes = raw_key.encode('utf-8')
        if len(key_bytes) > 72:
            import hashlib
            key_bytes = hashlib.sha256(key_bytes).digest()
        
        stored_hash_bytes = stored_hash.encode('utf-8')
        return bcrypt.checkpw(key_bytes, stored_hash_bytes)
    
    def create_api_key(
        self,
        name: str,
        owner: str,
        role: str = "developer",
        permissions: Optional[list] = None,
        expires_days: Optional[int] = None,
        raw_key: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Create a new API key.
        
        Args:
            name: Human-readable name for the key
            owner: User/entity that owns this key
            role: Role assigned to this key
            permissions: List of specific permissions
            expires_days: Optional expiration in days
            raw_key: Optional raw key (auto-generated if not provided)
        
        Returns:
            tuple: (key_id, raw_key) - raw_key is shown only once!
        """
        key_id = f"key_{uuid.uuid4().hex[:16]}"
        raw_key = raw_key or f"mcp_{secrets.token_urlsafe(32)}"
        key_hash = self._hash_key(raw_key)
        
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            owner=owner,
            role=role,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            permissions=permissions or []
        )
        
        self._api_keys[key_id] = api_key
        
        return key_id, raw_key
    
    def authenticate_api_key(self, raw_key: str) -> Optional[APIKey]:
        """
        Authenticate using API key.
        
        Uses bcrypt for secure key verification with timing-safe comparison.
        
        Returns:
            APIKey if valid, None otherwise
        """
        # Iterate through stored keys and verify using bcrypt
        for key_id, api_key in self._api_keys.items():
            if not api_key.is_active:
                continue
            
            # Verify key using bcrypt (timing-safe comparison)
            if self._verify_key(raw_key, api_key.key_hash):
                # Check expiration
                if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
                    return None
                
                # Check rate limit
                if not self._check_rate_limit(key_id, api_key.rate_limit):
                    return None
                
                # Update last used
                api_key.last_used = datetime.utcnow()
                return api_key
        
        return None
    
    def _check_rate_limit(self, key_id: str, limit: int) -> bool:
        """Check if request is within rate limit."""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        
        # Get requests in last hour
        requests = self._rate_limits.get(key_id, [])
        requests = [t for t in requests if t > hour_ago]
        
        if len(requests) >= limit:
            return False
        
        requests.append(now)
        self._rate_limits[key_id] = requests
        return True
    
    def create_session(
        self,
        user_id: str,
        role: str,
        permissions: list,
        expires_hours: int = 24,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Create JWT session token."""
        session_id = f"sess_{uuid.uuid4().hex}"
        
        session = Session(
            session_id=session_id,
            user_id=user_id,
            role=role,
            permissions=permissions,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self._sessions[session_id] = session
        
        # Create JWT
        payload = {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "permissions": permissions,
            "exp": session.expires_at,
            "iat": session.created_at
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
        return token
    
    def verify_session(self, token: str) -> Optional[Session]:
        """Verify JWT session token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            session_id = payload.get("session_id")
            session = self._sessions.get(session_id)
            
            if not session or not session.is_active:
                return None
            
            if datetime.utcnow() > session.expires_at:
                return None
            
            return session
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        if key_id in self._api_keys:
            self._api_keys[key_id].is_active = False
            return True
        return False
    
    def revoke_session(self, session_id: str) -> bool:
        """Revoke a session."""
        if session_id in self._sessions:
            self._sessions[session_id].is_active = False
            return True
        return False
    
    def get_api_key_info(self, key_id: str) -> Optional[Dict]:
        """Get API key info (without sensitive data)."""
        key = self._api_keys.get(key_id)
        if not key:
            return None
        
        return {
            "key_id": key.key_id,
            "name": key.name,
            "owner": key.owner,
            "role": key.role,
            "created_at": key.created_at.isoformat(),
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "last_used": key.last_used.isoformat() if key.last_used else None,
            "is_active": key.is_active,
            "permissions": key.permissions,
            "rate_limit": key.rate_limit
        }
    
    def list_api_keys(self, owner: Optional[str] = None) -> list:
        """List API keys (filtered by owner if specified)."""
        keys = []
        for key in self._api_keys.values():
            if owner and key.owner != owner:
                continue
            keys.append(self.get_api_key_info(key.key_id))
        return keys


# Global auth manager instance
auth_manager = AuthManager()


def require_auth(func: Callable) -> Callable:
    """
    Decorator to require authentication.
    
    Usage:
        @require_auth
        async def my_tool(ctx: Context, ...):
            # ctx.auth contains authenticated user info
            pass
    """
    @wraps(func)
    async def wrapper(ctx: Context, *args, **kwargs):
        # Check for API key in headers
        api_key = getattr(ctx, "api_key", None) or ctx.request.headers.get("X-API-Key")
        auth_header = ctx.request.headers.get("Authorization", "")
        
        authenticated_key = None
        
        # Try API key
        if api_key:
            authenticated_key = auth_manager.authenticate_api_key(api_key)
        
        # Try Bearer token
        elif auth_header.startswith("Bearer "):
            token = auth_header[7:]
            session = auth_manager.verify_session(token)
            if session:
                ctx.session = session
                ctx.user_id = session.user_id
                ctx.role = session.role
                ctx.permissions = session.permissions
        
        if not authenticated_key and not hasattr(ctx, "session"):
            from mcp.types import ErrorData, INTERNAL_ERROR
            return ErrorData(
                code=INTERNAL_ERROR,
                message="Authentication required. Provide X-API-Key header or Authorization Bearer token."
            )
        
        if authenticated_key:
            ctx.api_key_id = authenticated_key.key_id
            ctx.user_id = authenticated_key.owner
            ctx.role = authenticated_key.role
            ctx.permissions = authenticated_key.permissions
        
        return await func(ctx, *args, **kwargs)
    
    return wrapper


def require_permission(permission: str):
    """
    Decorator to require specific permission.
    
    Usage:
        @require_permission("tools:execute:shell")
        async def shell_tool(ctx: Context, ...):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(ctx: Context, *args, **kwargs):
            permissions = getattr(ctx, "permissions", [])
            
            # Check for wildcard permission
            if "*" in permissions:
                return await func(ctx, *args, **kwargs)
            
            # Check for specific permission
            if permission not in permissions:
                # Check for pattern matching (e.g., "tools:execute:*")
                parts = permission.split(":")
                for perm in permissions:
                    perm_parts = perm.split(":")
                    if len(perm_parts) == len(parts):
                        match = all(p == "*" or p == parts[i] for i, p in enumerate(perm_parts))
                        if match:
                            break
                else:
                    from mcp.types import ErrorData, INTERNAL_ERROR
                    return ErrorData(
                        code=INTERNAL_ERROR,
                        message=f"Permission denied. Required: {permission}"
                    )
            
            return await func(ctx, *args, **kwargs)
        
        return wrapper
    return decorator
