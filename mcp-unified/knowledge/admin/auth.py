"""
Authentication & Authorization Module - SECURE VERSION

Role-based access control untuk admin dashboard.

Roles:
    - admin: Full access (review, manage users, delete)
    - reviewer: Can review pending documents, view knowledge base
    - viewer: Read-only access to knowledge base

Security Features:
    - PBKDF2 password hashing (SHA256)
    - Environment variable credentials
    - Secure token generation
    - Session management
    - Rate limiting support
"""

from functools import wraps
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import secrets
import hashlib
import os
import hmac
import time


@dataclass
class User:
    """User dengan role dan password hash."""
    id: str
    username: str
    email: str
    role: str  # admin, reviewer, viewer
    password_hash: str
    salt: str
    created_at: str
    last_login: Optional[str] = None
    is_active: bool = True
    must_change_password: bool = False
    failed_login_attempts: int = 0
    locked_until: Optional[float] = None


@dataclass
class AuthToken:
    """Auth token untuk session."""
    token: str
    user_id: str
    role: str
    created_at: str
    expires_at: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class SecureAuthManager:
    """
    Secure authentication manager dengan PBKDF2 hashing.
    
    Features:
        - Secure password hashing
        - Environment variable credentials
        - Account lockout after failed attempts
        - Session management
        - Audit logging
    """
    
    # Constants
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    SESSION_DURATION_HOURS = 24
    HASH_ITERATIONS = 100000  # PBKDF2 iterations
    
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._tokens: Dict[str, AuthToken] = {}
        self._audit_log: List[Dict] = []
        self._load_users_from_env()
    
    def _hash_password(self, password: str, salt: Optional[str] = None) -> tuple:
        """
        Hash password menggunakan PBKDF2-HMAC-SHA256.
        
        Returns:
            (hash, salt) tuple
        """
        if salt is None:
            salt = secrets.token_hex(32)
        
        # Use environment pepper if available
        pepper = os.getenv('MCP_PASSWORD_PEPPER', 'default-pepper-change-in-production')
        
        # PBKDF2 hashing
        pwdhash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            (salt + pepper).encode('utf-8'),
            self.HASH_ITERATIONS
        ).hex()
        
        return pwdhash, salt
    
    def _verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """Verify password against hash."""
        computed_hash, _ = self._hash_password(password, salt)
        return hmac.compare_digest(computed_hash, password_hash)
    
    def _load_users_from_env(self):
        """Load users dari environment variables dengan secure defaults."""
        # Generate random secure passwords if not set
        import secrets as sec
        
        for role in ["admin", "reviewer", "viewer"]:
            username = os.getenv(f"MCP_{role.upper()}_USER", role)
            password_env = os.getenv(f"MCP_{role.upper()}_PASSWORD")
            
            if password_env:
                # Use provided password
                password = password_env
            else:
                # Generate secure random password and log warning
                password = sec.token_urlsafe(16)
                print(f"⚠️  WARNING: Using generated password for {role}: {password}")
                print(f"   Set MCP_{role.upper()}_PASSWORD to customize.")
            
            # Hash the password
            pwd_hash, salt = self._hash_password(password)
            
            self._users[username] = User(
                id=f"{role}_001",
                username=username,
                email=f"{username}@mcp.local",
                role=role,
                password_hash=pwd_hash,
                salt=salt,
                created_at=datetime.now().isoformat(),
                must_change_password=password_env is None  # Force change if using default
            )
    
    def authenticate(
        self, 
        username: str, 
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[AuthToken]:
        """
        Secure authenticate user dengan rate limiting dan account lockout.
        
        Returns:
            AuthToken jika berhasil, None jika gagal
        """
        now = time.time()
        
        # Check if user exists
        user = self._users.get(username)
        
        if user is None:
            # Timing attack protection: tetap hash walaupun user tidak ada
            self._hash_password(password, secrets.token_hex(32))
            self._audit_log.append({
                "timestamp": datetime.now().isoformat(),
                "action": "login_failed",
                "username": username,
                "reason": "user_not_found",
                "ip": ip_address
            })
            return None
        
        # Check account lockout
        if user.locked_until and now < user.locked_until:
            self._audit_log.append({
                "timestamp": datetime.now().isoformat(),
                "action": "login_denied",
                "username": username,
                "reason": "account_locked",
                "ip": ip_address
            })
            return None
        
        if not user.is_active:
            self._audit_log.append({
                "timestamp": datetime.now().isoformat(),
                "action": "login_denied",
                "username": username,
                "reason": "account_inactive",
                "ip": ip_address
            })
            return None
        
        # Verify password
        if not self._verify_password(password, user.password_hash, user.salt):
            # Increment failed attempts
            user.failed_login_attempts += 1
            
            # Lock account if max attempts reached
            if user.failed_login_attempts >= self.MAX_LOGIN_ATTEMPTS:
                user.locked_until = now + (self.LOCKOUT_DURATION_MINUTES * 60)
                print(f"🔒 Account locked: {username} for {self.LOCKOUT_DURATION_MINUTES} minutes")
            
            self._audit_log.append({
                "timestamp": datetime.now().isoformat(),
                "action": "login_failed",
                "username": username,
                "reason": "invalid_password",
                "attempt": user.failed_login_attempts,
                "ip": ip_address
            })
            return None
        
        # Check if password change required
        if user.must_change_password:
            return AuthToken(
                token="FORCE_PASSWORD_CHANGE",
                user_id=user.id,
                role=user.role,
                created_at=datetime.now().isoformat(),
                expires_at=(datetime.now() + timedelta(minutes=5)).isoformat()
            )
        
        # Success - reset failed attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now().isoformat()
        
        # Generate secure token
        token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(hours=self.SESSION_DURATION_HOURS)
        
        auth_token = AuthToken(
            token=token,
            user_id=user.id,
            role=user.role,
            created_at=datetime.now().isoformat(),
            expires_at=expires.isoformat(),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self._tokens[token] = auth_token
        
        self._audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": "login_success",
            "username": username,
            "role": user.role,
            "ip": ip_address
        })
        
        return auth_token
    
    def change_password(
        self, 
        username: str, 
        old_password: str, 
        new_password: str
    ) -> bool:
        """
        Change user password dengan validation.
        
        Returns:
            True jika berhasil, False jika gagal
        """
        user = self._users.get(username)
        if not user:
            return False
        
        # Verify old password
        if not self._verify_password(old_password, user.password_hash, user.salt):
            return False
        
        # Validate new password strength
        if not self._validate_password_strength(new_password):
            return False
        
        # Hash new password
        new_hash, new_salt = self._hash_password(new_password)
        user.password_hash = new_hash
        user.salt = new_salt
        user.must_change_password = False
        
        # Invalidate all existing tokens
        self._tokens = {
            k: v for k, v in self._tokens.items() 
            if v.user_id != user.id
        }
        
        self._audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": "password_changed",
            "username": username
        })
        
        return True
    
    def _validate_password_strength(self, password: str) -> bool:
        """
        Validate password strength.
        
        Requirements:
            - Min 8 characters
            - At least 1 uppercase
            - At least 1 lowercase
            - At least 1 digit
            - At least 1 special character
        """
        if len(password) < 8:
            return False
        if not any(c.isupper() for c in password):
            return False
        if not any(c.islower() for c in password):
            return False
        if not any(c.isdigit() for c in password):
            return False
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
            return False
        return True
    
    def verify_token(self, token: str, ip_address: Optional[str] = None) -> Optional[AuthToken]:
        """
        Verifikasi token dengan optional IP binding.
        
        Returns:
            AuthToken jika valid, None jika invalid/expired
        """
        if token not in self._tokens:
            return None
        
        auth_token = self._tokens[token]
        
        # Check expiration
        expires = datetime.fromisoformat(auth_token.expires_at)
        if datetime.now() > expires:
            del self._tokens[token]
            return None
        
        # Optional IP binding check
        if ip_address and auth_token.ip_address and auth_token.ip_address != ip_address:
            # IP mismatch - potential session hijacking
            del self._tokens[token]
            self._audit_log.append({
                "timestamp": datetime.now().isoformat(),
                "action": "token_invalidated",
                "reason": "ip_mismatch",
                "user_id": auth_token.user_id
            })
            return None
        
        return auth_token
    
    def logout(self, token: str) -> bool:
        """Logout dan invalidate token."""
        if token in self._tokens:
            auth_token = self._tokens[token]
            del self._tokens[token]
            
            self._audit_log.append({
                "timestamp": datetime.now().isoformat(),
                "action": "logout",
                "user_id": auth_token.user_id
            })
            return True
        return False
    
    def logout_all_sessions(self, user_id: str) -> int:
        """Logout all sessions untuk user."""
        tokens_to_remove = [
            k for k, v in self._tokens.items() 
            if v.user_id == user_id
        ]
        for token in tokens_to_remove:
            del self._tokens[token]
        
        self._audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": "logout_all_sessions",
            "user_id": user_id,
            "count": len(tokens_to_remove)
        })
        
        return len(tokens_to_remove)
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        for user in self._users.values():
            if user.id == user_id:
                return user
        return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return self._users.get(username)
    
    def list_users(self) -> List[User]:
        """List semua users."""
        return list(self._users.values())
    
    def has_permission(self, token: str, required_role: str) -> bool:
        """
        Check jika user dengan token punya permission.
        
        Role hierarchy:
            admin > reviewer > viewer
        """
        auth = self.verify_token(token)
        if not auth:
            return False
        
        user_role = auth.role
        
        # Role hierarchy check
        if required_role == "viewer":
            return user_role in ["admin", "reviewer", "viewer"]
        elif required_role == "reviewer":
            return user_role in ["admin", "reviewer"]
        elif required_role == "admin":
            return user_role == "admin"
        
        return False
    
    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """Get audit log entries."""
        return self._audit_log[-limit:]
    
    def get_active_sessions(self, user_id: Optional[str] = None) -> List[AuthToken]:
        """Get active sessions."""
        sessions = list(self._tokens.values())
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        return sessions


# Global auth manager instance
_auth_manager: Optional[SecureAuthManager] = None


def get_auth_manager() -> SecureAuthManager:
    """Get global auth manager."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = SecureAuthManager()
    return _auth_manager


def require_auth(func: Callable) -> Callable:
    """Decorator untuk require authentication."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        token = kwargs.get('token') or (args[0] if args else None)
        
        if not token:
            return {"error": "Token required"}, 401
        
        auth = get_auth_manager().verify_token(token)
        if not auth:
            return {"error": "Invalid or expired token"}, 401
        
        kwargs['auth'] = auth
        return await func(*args, **kwargs)
    
    return wrapper


def require_role(required_role: str):
    """Decorator factory untuk require specific role."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            token = kwargs.get('token') or (args[0] if args else None)
            
            if not token:
                return {"error": "Token required"}, 401
            
            auth_manager = get_auth_manager()
            
            if not auth_manager.has_permission(token, required_role):
                return {"error": f"Requires {required_role} role"}, 403
            
            auth = auth_manager.verify_token(token)
            kwargs['auth'] = auth
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Backward compatibility - alias untuk AuthManager
AuthManager = SecureAuthManager
