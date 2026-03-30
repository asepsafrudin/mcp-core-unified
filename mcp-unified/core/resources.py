from execution import resource_registry
import os

async def register_default_resources():
    """Register some default resources for the MCP server."""
    
    @resource_registry.register(
        uri="file:///system/status",
        name="System Status",
        description="Current status of the MCP unified server and its components",
        mime_type="application/json"
    )
    async def get_system_status(uri: str):
        import json
        status = {
            "server": "mcp-unified",
            "version": "1.0.0",
            "uptime": "Calculating...", # Could be implemented
            "environment": os.environ.get("ENV", "development")
        }
        return json.dumps(status, indent=2)

    @resource_registry.register(
        uri="file:///system/config",
        name="Server Configuration",
        description="Public configuration information for the server",
        mime_type="application/json"
    )
    def get_config(uri: str):
        import json
        # Filter sensitive info from env
        safe_keys = ["LOG_LEVEL", "MAX_WORKERS", "REQUEST_TIMEOUT"]
        config = {k: os.environ.get(k) for k in safe_keys if k in os.environ}
        return json.dumps(config, indent=2)

    @resource_registry.register(
        uri="file:///logs/mcp.log",
        name="Recent Server Logs",
        description="Last 50 lines of the server log file",
        mime_type="text/plain"
    )
    async def get_recent_logs(uri: str):
        log_path = "server.log"
        if not os.path.exists(log_path):
            return "Log file not found."
        
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
                return "".join(lines[-50:])
        except Exception as e:
            return f"Error reading logs: {str(e)}"
