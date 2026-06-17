import asyncio
import sys
from pathlib import Path

# Add mcp-unified path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.base import tool_registry

# Import all browser tools to register them
from tools.browser.navigate import BrowserNavigateTool
from tools.browser.snapshot import BrowserSnapshotTool
from tools.browser.extract import BrowserExtractTool
from tools.browser.action import BrowserActionTool
from tools.browser.task import BrowserTaskTool
from tools.browser.screenshot import BrowserScreenshotTool
from tools.browser.wait import BrowserWaitTool
from tools.browser.session import BrowserSessionTool
from tools.browser.script import BrowserScriptTool

async def main():
    print("Registered Browser Tools:")
    tools = tool_registry.list_tools()
    for t in tools:
        if t.startswith("browser_"):
            print(f" - {t}")
            
    # Quick instantiation check
    nav = tool_registry.get_tool("browser_navigate")
    assert nav is not None
    print(f"\\nTest passed: All {len([t for t in tools if t.startswith('browser_')])} browser tools registered successfully.")

if __name__ == "__main__":
    asyncio.run(main())
