import pytest
import httpx
from core.config import settings
import os

BASE_URL = "http://localhost:8000"


def _headers():
    key = os.getenv("MCP_TEST_API_KEY")
    if not key:
        raise RuntimeError("MCP_TEST_API_KEY env var is required to run these tests")
    return {"X-API-Key": key}

@pytest.mark.asyncio
async def test_health_check():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_list_dir():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/tools/call",
            headers=_headers(),
            json={"name": "list_dir", "arguments": {"path": "."}}
        )
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "files" in str(data["content"])

@pytest.mark.asyncio
async def test_memory_crud():
    async with httpx.AsyncClient() as client:
        # Save
        await client.post(f"{BASE_URL}/tools/call", json={
            "name": "memory_save",
            "arguments": {"key": "pytest_mem", "content": "automated test content"}
        }, headers=_headers())
        
        # Search
        response = await client.post(f"{BASE_URL}/tools/call", json={
            "name": "memory_search",
            "arguments": {"query": "automated test"}
        }, headers=_headers())
        data = response.json()
        assert "automated test content" in str(data)

@pytest.mark.asyncio
async def test_unknown_tool():
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/tools/call", json={
            "name": "non_existent_tool",
            "arguments": {}
        }, headers=_headers())
        assert response.status_code == 200 # It returns 200 but content has error info usually?
        # Our server returns 200 even on error but logs logic might differ. 
        # Actually server code catches exception and returns isError: True
        data = response.json()
        assert data.get("isError") is True
