import sys
import os

# Add local directory to path
sys.path.append("/home/aseps/MCP/mcp-unified")

try:
    from core.server import app
    print("Successfully imported FastAPI app")
except Exception as e:
    print(f"Failed to import app: {e}")
    sys.exit(1)
