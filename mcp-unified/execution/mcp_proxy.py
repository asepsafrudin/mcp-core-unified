import json
import asyncio
import os
from typing import Dict, Any, List, Optional
from observability.logger import logger

class MCPProxy:
    def __init__(self, config_path: str = "/home/aseps/MCP/antigravity-mcp-config.json"):
        self.config_path = config_path
        self.external_servers: Dict[str, Dict[str, Any]] = {}
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                mcp_servers = config.get("mcpServers", {})
                # Filter out the unified server itself to avoid recursion
                self.external_servers = {
                    name: cfg for name, cfg in mcp_servers.items() 
                    if name != "mcp-unified"
                }
            logger.info("mcp_proxy_config_loaded", servers=list(self.external_servers.keys()))
        except Exception as e:
            logger.error("mcp_proxy_config_error", error=str(e))

    async def list_remote_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Queries an external MCP server for its tools via tools/list method."""
        server_cfg = self.external_servers.get(server_name)
        if not server_cfg:
            return []

        command = server_cfg["command"]
        args = server_cfg["args"]
        
        # Prepare JSON-RPC requests
        # 1. Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": "init_1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-unified-proxy", "version": "1.0"}
            }
        }
        # 2. Initialized Notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        # 3. List Tools
        tool_request = {
            "jsonrpc": "2.0",
            "id": "list_tools_2",
            "method": "tools/list",
            "params": {}
        }

        # Combine into newline-delimited JSON
        input_data = f"{json.dumps(init_request)}\n{json.dumps(initialized_notification)}\n{json.dumps(tool_request)}\n"

        try:
            proc = await asyncio.create_subprocess_exec(
                command, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=input_data.encode()),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                logger.error("mcp_remote_list_timeout", server=server_name)
                return []
            
            if proc.returncode != 0 and not stdout:
                logger.error("mcp_remote_list_failed", server=server_name, error=stderr.decode())
                return []

            # Debug logging
            output = stdout.decode()
            error_out = stderr.decode()
            logger.info("mcp_remote_list_raw", server=server_name, length=len(output), snippet=output[:500], stderr_snippet=error_out[:500])
            
            # Find the response for tools/list (id: list_tools_2)
            # Output might contain multiple JSON lines
            for line in output.splitlines():
                if "list_tools_2" in line:
                    try:
                        response = json.loads(line)
                        tools = response.get("result", {}).get("tools", [])
                        return tools
                    except json.JSONDecodeError:
                        continue
            
            return []
        except Exception as e:
            logger.error("mcp_remote_list_error", server=server_name, error=str(e))
            return []

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Executes a tool on an external MCP server."""
        server_cfg = self.external_servers.get(server_name)
        if not server_cfg:
            raise ValueError(f"Server {server_name} not found in config")

        command = server_cfg["command"]
        args = server_cfg["args"]

        # Prepare JSON-RPC requests
        # 1. Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": "init_1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-unified-proxy", "version": "1.0"}
            }
        }
        # 2. Initialized Notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        # 3. Call Tool
        call_request = {
            "jsonrpc": "2.0",
            "id": f"call_{tool_name}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        input_data = f"{json.dumps(init_request)}\n{json.dumps(initialized_notification)}\n{json.dumps(call_request)}\n"

        try:
            proc = await asyncio.create_subprocess_exec(
                command, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=input_data.encode()),
                    timeout=30.0 # generous timeout for execution
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                raise Exception("MCP tool execution timed out")

            output = stdout.decode()
            
            # Find the response for the specific call ID
            target_id = f"call_{tool_name}"
            for line in output.splitlines():
                if target_id in line:
                    try:
                        response = json.loads(line)
                        if "error" in response:
                            raise Exception(response["error"].get("message", "Unknown MCP error"))
                        return response.get("result", {}).get("content", [])
                    except json.JSONDecodeError:
                        continue
            
            error_msg = stderr.decode() or "No JSON response from remote MCP server"
            raise Exception(error_msg)

        except Exception as e:
            logger.error("mcp_remote_call_error", server=server_name, tool=tool_name, error=str(e))
            raise e

mcp_proxy = MCPProxy()
