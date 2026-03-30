import os
import importlib.util
import sys
import asyncio
from pathlib import Path
from observability.logger import logger

def discover_plugins(plugin_dir: str):
    """
    Search plug-in folder and import .py files to trigger @registry.register decorators.
    
    This enables 'hot-plugging' tools, resources, and prompts by simply 
    placing new python files into the specified directory.
    """
    plugin_path = Path(plugin_dir).resolve()
    if not plugin_path.exists():
        logger.warning(f"Plugin directory not found: {plugin_dir}")
        return

    # Add plugin folder to sys.path if not there
    if str(plugin_path) not in sys.path:
        sys.path.insert(0, str(plugin_path))

    logger.info(f"Scanning for plugins in {plugin_path}")
    
    plugin_count = 0
    # Walk through the directory
    for root, dirs, files in os.walk(plugin_path):
        for file in files:
            file_path = Path(root) / file
            
            # 1. Python Plugin (.py)
            if file.endswith(".py") and not file.startswith("__"):
                plugin_count += self_register_python(file_path, plugin_path)
            
            # 2. Shell Script (.sh) -> Auto Tool
            elif file.endswith(".sh"):
                plugin_count += self_register_shell(file_path, plugin_path)

            # 3. JavaScript (.js) -> Auto Tool (if node is available)
            elif file.endswith(".js"):
                plugin_count += self_register_js(file_path, plugin_path)
                    
    logger.info(f"Discovery completed: {plugin_count} plugins loaded from {plugin_dir}")
    return plugin_count

def self_register_python(file_path: Path, plugin_path: Path):
    """Import a python file to trigger its decorators."""
    rel_path = file_path.relative_to(plugin_path)
    module_name = ".".join(rel_path.with_suffix("").parts)
    try:
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return 1
    except Exception as e:
        logger.error(f"Error loading python plugin {file_path}: {str(e)}")
    return 0

def self_register_shell(file_path: Path, plugin_path: Path):
    """Register a .sh file as a tool."""
    from execution import registry
    tool_name = file_path.stem
    
    async def shell_tool_wrapper(**kwargs):
        import subprocess
        # Convert kwargs to --key value arguments for shell
        args = [str(file_path)]
        for k, v in kwargs.items():
            args.extend([f"--{k}", str(v)])
        
        logger.info(f"Executing discovered shell tool: {tool_name}")
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            return f"Error: {stderr.decode()}"
        return stdout.decode()

    shell_tool_wrapper.__doc__ = f"Shell tool discovered at {file_path.name}. Arguments passed as --key value."
    registry.register(shell_tool_wrapper, name=tool_name)
    return 1

def self_register_js(file_path: Path, plugin_path: Path):
    """Register a .js file as a tool (requires node)."""
    from execution import registry
    tool_name = file_path.stem
    
    async def js_tool_wrapper(**kwargs):
        import subprocess
        import json
        # Pass args as a single JSON string for JS
        args = ["node", str(file_path), json.dumps(kwargs)]
        
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            return f"Error: {stderr.decode()}"
        return stdout.decode()

    js_tool_wrapper.__doc__ = f"Node.js tool discovered at {file_path.name}. Arguments passed as JSON string."
    registry.register(js_tool_wrapper, name=tool_name)
    return 1

def discover_all_standard_locations():
    """Discover from standard locations for tools, resources, and prompts."""
    # Main plugin directory
    plugin_dir = os.path.join(os.path.dirname(__file__), "..", "plugins")
    discover_plugins(plugin_dir)
    
    # Internal tools directory
    tools_dir = os.path.join(os.path.dirname(__file__), "..", "execution", "tools")
    discover_plugins(tools_dir)
    
    # Core capability directories
    for subdir in ["memory", "intelligence", "messaging", "execution"]:
        path = os.path.join(os.path.dirname(__file__), "..", subdir)
        if os.path.exists(path):
            discover_plugins(path)
