import pytest
import httpx
from core.config import settings

BASE_URL = "http://localhost:8000"

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
        })
        
        # Search
        response = await client.post(f"{BASE_URL}/tools/call", json={
            "name": "memory_search",
            "arguments": {"query": "automated test"}
        })
        data = response.json()
        assert "automated test content" in str(data)

@pytest.mark.asyncio
async def test_unknown_tool():
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/tools/call", json={
            "name": "non_existent_tool",
            "arguments": {}
        })
        assert response.status_code == 200 # It returns 200 but content has error info usually?
        # Our server returns 200 even on error but logs logic might differ. 
        # Actually server code catches exception and returns isError: True
        data = response.json()
        assert data.get("isError") is True
