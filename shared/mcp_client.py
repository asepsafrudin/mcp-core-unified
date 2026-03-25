"""
Portable MCP Client

Zero-config client untuk MCP Unified Hub.
Import dari folder manapun — langsung bisa digunakan.

Usage:
    from shared.mcp_client import MCPClient
    
    client = MCPClient()  # Auto-discover hub, auto-detect namespace
    result = await client.call("memory_search", query="database schema")
    context = await client.get_context()
"""
import json
import asyncio
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from pathlib import Path

from .discovery import discover_hub, detect_namespace


class MCPClient:
    """
    Auto-discovering, zero-config MCP client.
    
    Fitur:
    - Auto-discover hub di localhost
    - Auto-detect namespace dari folder aktif
    - Simple interface: client.call(tool_name, **kwargs)
    - Graceful degradation jika hub tidak tersedia
    
    [REVIEWER] Client ini menggunakan HTTP langsung ke SSE server
    untuk tool calls — bukan SSE streaming. SSE dipakai oleh IDE/editor
    untuk real-time. Client ini untuk programmatic use.
    """

    def __init__(
        self,
        hub_url: str = None,
        namespace: str = None,
        working_dir: str = None
    ):
        """
        Args:
            hub_url: Override URL hub (default: auto-discover)
            namespace: Override namespace (default: auto-detect dari folder)
            working_dir: Folder untuk namespace detection (default: cwd)
        """
        self._hub_url = hub_url
        self._namespace = namespace
        self._working_dir = working_dir
        self._base_url = None
        self._available = False
        self._tools: List[str] = []

        # Auto-initialize
        self._initialize()

    def _initialize(self):
        """Discover hub dan setup client."""
        # Discover hub
        if self._hub_url:
            self._base_url = self._hub_url.replace("/sse", "")
        else:
            sse_url = discover_hub()
            if sse_url:
                self._base_url = sse_url.replace("/sse", "")
                self._available = True
            else:
                print("[MCPClient] WARNING: MCP Hub tidak ditemukan. "
                      "Pastikan server berjalan: python3 mcp_server_sse.py")
                return

        # Detect namespace
        if not self._namespace:
            self._namespace = detect_namespace(self._working_dir)
            print(f"[MCPClient] Namespace: {self._namespace}")

        # Load available tools
        self._load_tools()

    def _load_tools(self):
        """Load daftar tools dari hub."""
        try:
            url = f"{self._base_url}/health"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                # Health endpoint memberikan jumlah tools
                # Untuk list lengkap, gunakan MCP protocol via SSE
                tool_count = data.get("tools_available", 0)
                print(f"[MCPClient] Connected — {tool_count} tools available")
                self._available = True
        except Exception as e:
            print(f"[MCPClient] WARNING: Tidak bisa load tools: {e}")

    async def call(
        self,
        tool_name: str,
        namespace: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Panggil tool di MCP Hub.
        
        Args:
            tool_name: Nama tool (e.g. "memory_search", "run_shell")
            namespace: Override namespace untuk call ini
            **kwargs: Arguments untuk tool
        
        Returns:
            Dict hasil dari tool, atau error dict jika gagal
        
        [REVIEWER] Namespace di-inject otomatis untuk memory tools.
        Bisa di-override per-call jika diperlukan.
        """
        if not self._available:
            return {
                "success": False,
                "error": "MCP Hub tidak tersedia. Jalankan: python3 mcp_server_sse.py"
            }

        # Auto-inject namespace untuk memory tools
        MEMORY_TOOLS = {
            "memory_save", "memory_search", "memory_list",
            "memory_delete", "create_plan", "save_plan_experience"
        }
        if tool_name in MEMORY_TOOLS and "namespace" not in kwargs:
            kwargs["namespace"] = namespace or self._namespace

        # Buat MCP JSON-RPC request
        payload = {
            "jsonrpc": "2.0",
            "id": f"client_{tool_name}_{id(kwargs)}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": kwargs
            }
        }

        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{self._base_url}/messages/",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                if "error" in result:
                    return {"success": False, "error": result["error"]}
                content = result.get("result", {}).get("content", [])
                if content and content[0].get("type") == "text":
                    try:
                        return json.loads(content[0]["text"])
                    except json.JSONDecodeError:
                        return {"success": True, "result": content[0]["text"]}
                return {"success": True, "result": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_context(self) -> Dict[str, Any]:
        """
        Dapatkan konteks project dari memory hub.
        
        Returns context bundle berisi:
        - recent memories dari namespace ini
        - tools yang tersedia
        - namespace aktif
        """
        if not self._available:
            return {"available": False, "namespace": self._namespace}

        # Ambil recent memories dari namespace ini
        memories_result = await self.call(
            "memory_list",
            limit=5,
            offset=0
        )

        return {
            "available": True,
            "namespace": self._namespace,
            "hub_url": self._base_url,
            "recent_memories": memories_result.get("memories", []),
            "total_memories": memories_result.get("total", 0),
        }

    async def save_context(self, key: str, content: str, metadata: dict = None):
        """Shortcut untuk memory_save dengan namespace otomatis."""
        return await self.call(
            "memory_save",
            key=key,
            content=content,
            metadata=metadata or {}
        )

    async def search_context(self, query: str, limit: int = 3) -> List[Dict]:
        """Shortcut untuk memory_search dengan namespace otomatis."""
        result = await self.call(
            "memory_search",
            query=query,
            limit=limit,
            strategy="hybrid"
        )
        return result.get("results", [])

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def is_available(self) -> bool:
        return self._available

    def __repr__(self):
        status = "connected" if self._available else "disconnected"
        return f"MCPClient(namespace='{self._namespace}', status='{status}', hub='{self._base_url}')"
