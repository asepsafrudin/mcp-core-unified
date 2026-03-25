"""
Admin Dashboard Module

Web-based admin dashboard untuk:
    - Review Queue Management
    - Knowledge Base Management
    - User Role Management
    - System Monitoring

Usage:
    from knowledge.admin import create_admin_app
    
    app = create_admin_app()
    app.run(host="0.0.0.0", port=8080)
"""

from .app import create_admin_app
from .auth import require_auth, require_role

__all__ = ["create_admin_app", "require_auth", "require_role"]
