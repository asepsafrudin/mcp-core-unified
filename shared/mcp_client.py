#!/usr/bin/env python3
"""
Universal MCP Client for Project MCP
Berkomunikasi dengan MCP Server (mcp-memory) melalui HTTP JSON-RPC.
"""

import json
import time
import os
import requests
import asyncio
from typing import Dict, Any, Optional

# Konfigurasi Default Server mcp-memory
DEFAULT_MCP_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8000/")

async def call_mcp_tool(name: str, arguments: dict = None, timeout: int = 30) -> dict:
    """
    Panggil MCP tools via HTTP POST ke FastAPI server.
    """
    if arguments is None:
        arguments = {}
    
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments
        }
    }
    
    try:
        # Gunakan asyncio.to_thread untuk menjalankan requests.post (blocking) secara asinkron
        response = await asyncio.to_thread(requests.post, DEFAULT_MCP_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            return {
                "status": "error",
                "error": data["error"],
                "tool": name,
                "arguments": arguments
            }
            
        if "result" in data:
            # MCP standard wrap results in content list
            result_data = data["result"]
            if isinstance(result_data, dict) and "content" in result_data:
                text_content = result_data["content"][0]["text"]
                try:
                    # Jika isi konten adalah string JSON, parse kembali
                    if text_content.strip().startswith(('{', '[')):
                        return {
                            "status": "success",
                            "data": json.loads(text_content),
                            "tool": name,
                            "arguments": arguments
                        }
                    return {
                        "status": "success",
                        "data": text_content,
                        "tool": name,
                        "arguments": arguments
                    }
                except (json.JSONDecodeError, IndexError, KeyError):
                    return {
                        "status": "success",
                        "data": text_content,
                        "tool": name,
                        "arguments": arguments
                    }
            return {
                "status": "success",
                "data": result_data,
                "tool": name,
                "arguments": arguments
            }
            
        return {"status": "success", "data": data, "tool": name}

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"HTTP Request failed: {str(e)}",
            "tool": name,
            "arguments": arguments
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Unexpected error: {str(e)}",
            "tool": name,
            "arguments": arguments
        }

# Wrapper functions
async def mcp_list_dir(path: str = ".") -> dict:
    return await call_mcp_tool("list_dir", {"path": path})

async def mcp_read_file(path: str) -> dict:
    return await call_mcp_tool("read_file", {"path": path})

async def mcp_write_file(path: str, content: str) -> dict:
    return await call_mcp_tool("write_file", {"path": path, "content": content})

async def mcp_memory_save(key: str, content: str, metadata: dict = None) -> dict:
    return await call_mcp_tool("memory_save", {"key": key, "content": content, "metadata": metadata or {}})

async def mcp_memory_search(query: str, strategy: str = "hybrid") -> dict:
    return await call_mcp_tool("memory_search", {"query": query, "strategy": strategy})

async def mcp_run_shell(command: str) -> dict:
    return await call_mcp_tool("run_shell", {"command": command})

def test_mcp_connection():
    """Test koneksi ke MCP server"""
    print(f"🧪 Testing connection to {DEFAULT_MCP_URL}...")
    result = mcp_list_dir(".")
    if result["status"] == "success":
        print("✅ Connection successful!")
        return True
    print(f"❌ Connection failed: {result.get('error')}")
    return False

if __name__ == "__main__":
    test_mcp_connection()
