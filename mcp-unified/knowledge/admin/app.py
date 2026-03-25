"""
Admin Dashboard FastAPI Application

Web-based admin dashboard untuk Knowledge Sharing System.

Features:
    - Review Queue Management
    - Knowledge Base Browser
    - User Management (admin only)
    - System Stats

Run: python -m knowledge.admin.app
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, Request, Form, Cookie, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from knowledge.integrated_processor import IntegratedDocumentProcessor
from knowledge.ingestion import DocumentProcessor
from knowledge.admin.auth import get_auth_manager, require_role, AuthToken

# Create FastAPI app
app = FastAPI(
    title="MCP Knowledge Admin",
    description="Admin Dashboard untuk Knowledge Sharing System",
    version="1.0.0"
)

# Templates (simple inline HTML untuk MVP)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Global processor instance
_processor: Optional[IntegratedDocumentProcessor] = None
_doc_processor: Optional[DocumentProcessor] = None


async def get_processor() -> IntegratedDocumentProcessor:
    """Get atau initialize processor."""
    global _processor
    if _processor is None:
        _processor = IntegratedDocumentProcessor()
        await _processor.initialize()
    return _processor


def get_doc_processor() -> DocumentProcessor:
    """Get document processor untuk review queue."""
    global _doc_processor
    if _doc_processor is None:
        _doc_processor = DocumentProcessor()
    return _doc_processor


# ==================== HTML PAGES ====================

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>MCP Knowledge Admin - Login</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f5f5f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-box { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 300px; }
        h1 { color: #333; margin-bottom: 30px; text-align: center; font-size: 24px; }
        input { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background: #0056b3; }
        .error { color: #dc3545; margin-top: 10px; text-align: center; }
        .info { color: #666; font-size: 12px; margin-top: 20px; text-align: center; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>🔐 MCP Admin</h1>
        <form method="POST" action="/login">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <div class="info">
            Login dengan credentials yang telah dikonfigurasi. Hubungi administrator untuk akses.
        </div>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>MCP Knowledge Admin - Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; }
        .navbar { background: #333; color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
        .navbar h1 { font-size: 20px; }
        .navbar .user { font-size: 14px; }
        .navbar a { color: #ccc; text-decoration: none; margin-left: 20px; }
        .navbar a:hover { color: white; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 20px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .stat-card h3 { color: #666; font-size: 14px; margin-bottom: 10px; }
        .stat-card .value { font-size: 32px; font-weight: bold; color: #333; }
        .section { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .section h2 { margin-bottom: 15px; color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; }
        .btn { padding: 6px 12px; border-radius: 4px; text-decoration: none; font-size: 12px; }
        .btn-primary { background: #007bff; color: white; }
        .btn-success { background: #28a745; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; }
        .badge-warning { background: #ffc107; color: #333; }
        .badge-success { background: #28a745; color: white; }
        .badge-info { background: #17a2b8; color: white; }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>📚 MCP Knowledge Admin</h1>
        <div class="user">
            {{ role }} | {{ username }} | <a href="/logout">Logout</a>
        </div>
    </div>
    
    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <h3>⏳ Pending Review</h3>
                <div class="value">{{ pending_count }}</div>
            </div>
            <div class="stat-card">
                <h3>📄 Total Documents</h3>
                <div class="value">{{ total_docs }}</div>
            </div>
            <div class="stat-card">
                <h3>📁 Namespaces</h3>
                <div class="value">{{ namespace_count }}</div>
            </div>
        </div>
        
        {% if pending_reviews %}
        <div class="section">
            <h2>⏳ Review Queue</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>File</th>
                        <th>Quality Score</th>
                        <th>Namespace</th>
                        <th>Submitted</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for review in pending_reviews %}
                    <tr>
                        <td>{{ review.id }}</td>
                        <td>{{ review.file_path }}</td>
                        <td><span class="badge badge-warning">{{ "%.2f"|format(review.quality_score) }}</span></td>
                        <td>{{ review.suggested_namespace }}</td>
                        <td>{{ review.submitted_at }}</td>
                        <td>
                            <a href="/review/{{ review.id }}" class="btn btn-primary">Review</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
        
        <div class="section">
            <h2>📁 Namespaces</h2>
            <table>
                <thead>
                    <tr>
                        <th>Namespace</th>
                        <th>Description</th>
                        <th>Documents</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for ns in namespaces %}
                    <tr>
                        <td><span class="badge badge-info">{{ ns.name }}</span></td>
                        <td>{{ ns.description }}</td>
                        <td>{{ ns.document_count }}</td>
                        <td>
                            <a href="/namespace/{{ ns.name }}" class="btn btn-primary">Browse</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""


# ==================== ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect ke login atau dashboard."""
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    """Show login page."""
    from jinja2 import Template
    template = Template(LOGIN_HTML)
    return template.render(error=error)


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle login."""
    auth_manager = get_auth_manager()
    token = auth_manager.authenticate(username, password)
    
    if token is None:
        from jinja2 import Template
        template = Template(LOGIN_HTML)
        return HTMLResponse(template.render(error="Invalid credentials"), status_code=401)
    
    # Set cookie dan redirect
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="session_token", value=token.token, httponly=True, max_age=86400)
    return response


@app.get("/logout")
async def logout(request: Request, session_token: Optional[str] = Cookie(None)):
    """Handle logout."""
    if session_token:
        get_auth_manager().logout(session_token)
    
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session_token: Optional[str] = Cookie(None)
):
    """Main dashboard."""
    # Check auth
    auth = get_auth_manager().verify_token(session_token) if session_token else None
    if not auth:
        return RedirectResponse(url="/login", status_code=303)
    
    # Get data
    doc_processor = get_doc_processor()
    pending_reviews = doc_processor.get_pending_reviews()
    
    # Get namespace info
    from knowledge.sharing import NamespaceManager
    ns_manager = NamespaceManager()
    namespaces = await ns_manager.list_namespaces()
    
    # Render
    from jinja2 import Template
    template = Template(DASHBOARD_HTML)
    return template.render(
        username=auth.user_id,
        role=auth.role,
        pending_count=len(pending_reviews),
        pending_reviews=pending_reviews,
        total_docs=sum(ns.get("document_count", 0) for ns in namespaces),
        namespace_count=len(namespaces),
        namespaces=namespaces
    )


@app.get("/api/stats", response_class=JSONResponse)
async def api_stats(session_token: Optional[str] = Cookie(None)):
    """API endpoint untuk stats."""
    auth = get_auth_manager().verify_token(session_token) if session_token else None
    if not auth:
        return {"error": "Unauthorized"}, 401
    
    doc_processor = get_doc_processor()
    pending = doc_processor.get_pending_reviews()
    
    return {
        "pending_review": len(pending),
        "user_role": auth.role,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/review/{review_id}/approve")
async def api_approve_review(
    review_id: str,
    namespace: Optional[str] = None,
    session_token: Optional[str] = Cookie(None)
):
    """Approve document dari review queue."""
    # Check auth (minimal reviewer role)
    auth_manager = get_auth_manager()
    if not auth_manager.has_permission(session_token, "reviewer"):
        return {"error": "Forbidden"}, 403
    
    processor = await get_processor()
    result = await processor.approve_review_and_ingest(review_id, namespace)
    
    if result.status == "approved":
        return {"success": True, "message": result.message, "chunks": result.chunks_count}
    else:
        return {"error": result.message}, 400


@app.post("/api/review/{review_id}/reject")
async def api_reject_review(
    review_id: str,
    reason: str = Form(""),
    session_token: Optional[str] = Cookie(None)
):
    """Reject document dari review queue."""
    auth_manager = get_auth_manager()
    if not auth_manager.has_permission(session_token, "reviewer"):
        return {"error": "Forbidden"}, 403
    
    doc_processor = get_doc_processor()
    result = await doc_processor.reject_review(review_id, reason)
    
    return {"success": result.status == "rejected", "message": result.message}


# ==================== MAIN ====================

def create_admin_app() -> FastAPI:
    """Create admin app instance."""
    return app


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting MCP Knowledge Admin Dashboard...")
    print("📍 URL: http://localhost:8080")
    print("👤 Secure Authentication Active")
    print("   - Passwords are hashed with PBKDF2")
    print("   - Set MCP_ADMIN_PASSWORD, MCP_REVIEWER_PASSWORD, MCP_VIEWER_PASSWORD env vars")
    print("   - Check generated passwords above if not set")
    uvicorn.run(app, host="0.0.0.0", port=8080)
