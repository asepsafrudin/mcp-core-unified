"""
OpenHands Admin Control Server
Port: 8095 (Default)
"""
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from typing import Dict, Any, List

# Tambahkan PROJECT_ROOT ke sys.path agar bisa import services
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from services.service_controller import (
    get_all_service_status, 
    start_service, 
    stop_service, 
    restart_service,
    get_service_log
)

app = FastAPI(title="OpenHands Admin Control Server")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "online", 
        "service": "openhands-admin",
        "port": int(os.getenv("OPENHANDS_ADMIN_PORT", "8095"))
    }

@app.get("/services")
async def list_services():
    """Get status of all registered services."""
    return get_all_service_status()

@app.get("/services/{name}")
async def get_service_status(name: str):
    """Get status of a specific service."""
    status = get_all_service_status()
    if name not in status:
        raise HTTPException(status_code=404, detail=f"Service {name} not found")
    return status[name]

@app.post("/services/{name}/start")
async def start_svc(name: str):
    """Start a specific service."""
    return start_service(name)

@app.post("/services/{name}/stop")
async def stop_svc(name: str):
    """Stop a specific service."""
    return stop_service(name)

@app.post("/services/{name}/restart")
async def restart_svc(name: str):
    """Restart a specific service."""
    return restart_service(name)

@app.get("/services/{name}/logs")
async def get_logs(name: str, lines: int = 100):
    """Get logs for a specific service."""
    return get_service_log(name, lines=lines)

if __name__ == "__main__":
    port = int(os.getenv("OPENHANDS_ADMIN_PORT", "8095"))
    print(f"🚀 Starting OpenHands Admin Server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
