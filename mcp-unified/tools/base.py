"""
BaseTool - Abstract base class untuk semua tools

Tools adalah execution layer yang melakukan operasi konkret
seperti file operations, shell execution, web requests, dll.

[REVIEWER] All tools MUST extend BaseTool and implement execute().
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass
import asyncio

from core.task import Task, TaskResult, TaskStatus, BaseTaskHandler


@dataclass
class ToolParameter:
    """Definition untuk tool parameter."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
            "default": self.default
        }


@dataclass
class ToolDefinition:
    """Definition untuk tool metadata."""
    name: str
    description: str
    parameters: List[ToolParameter]
    returns: str
    examples: List[str] = None
    
    def __post_init__(self):
        if self.examples is None:
            self.examples = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [p.to_dict() for p in self.parameters],
            "returns": self.returns,
            "examples": self.examples
        }


class BaseTool(BaseTaskHandler, ABC):
    """
    Abstract base class untuk semua tools.
    
    Tools adalah execution layer yang melakukan operasi konkret.
    Mereka tidak memiliki "intelligence" - hanya melakukan apa yang
    diperintahkan dengan parameter yang diberikan.
    
    Examples:
        - FileTool: read, write, delete files
        - ShellTool: execute shell commands
        - WebTool: HTTP requests
        - BrowserTool: web automation
    
    [REVIEWER] Implementers MUST:
    1. Override tool_definition property
    2. Override execute() method
    3. Handle errors gracefully dengan TaskResult
    """
    
    def __init__(self):
        self._execution_count = 0
        self._error_count = 0
    
    @property
    @abstractmethod
    def tool_definition(self) -> ToolDefinition:
        """
        Get tool definition dengan metadata.
        
        Returns:
            ToolDefinition dengan tool metadata
        """
        pass
    
    @property
    def name(self) -> str:
        """Get tool name dari definition."""
        return self.tool_definition.name
    
    @property
    def description(self) -> str:
        """Get tool description dari definition."""
        return self.tool_definition.description
    
    def can_handle(self, task: Task) -> bool:
        """
        Check if this tool can handle the given task.
        
        Tool dapat handle task jika task.type sama dengan tool name.
        """
        return task.type == self.name
    
    @abstractmethod
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute tool dengan task payload.
        
        Args:
            task: Task dengan tool parameters di payload
            
        Returns:
            TaskResult dengan execution outcome
        """
        pass
    
    def get_capabilities(self) -> List[str]:
        """Get tool capabilities."""
        return [f"tool:{self.name}"]
    
    def get_handler_info(self) -> Dict[str, Any]:
        """Get tool handler info dengan definition."""
        info = super().get_handler_info()
        info["tool_definition"] = self.tool_definition.to_dict()
        info["execution_count"] = self._execution_count
        info["error_count"] = self._error_count
        return info
    
    def validate_payload(self, task: Task) -> Optional[str]:
        """
        Validate task payload terhadap tool definition.
        
        Args:
            task: Task untuk divalidasi
            
        Returns:
            Error message jika invalid, None jika valid
        """
        definition = self.tool_definition
        payload = task.payload
        
        for param in definition.parameters:
            if param.required and param.name not in payload:
                return f"Missing required parameter: {param.name}"
            
            if param.name in payload:
                value = payload[param.name]
                # Type checking (simplified)
                if param.type == "string" and not isinstance(value, str):
                    return f"Parameter {param.name} must be string"
                elif param.type == "integer" and not isinstance(value, int):
                    return f"Parameter {param.name} must be integer"
                elif param.type == "boolean" and not isinstance(value, bool):
                    return f"Parameter {param.name} must be boolean"
                elif param.type == "array" and not isinstance(value, list):
                    return f"Parameter {param.name} must be array"
                elif param.type == "object" and not isinstance(value, dict):
                    return f"Parameter {param.name} must be object"
        
        return None
    
    async def run_with_timeout(
        self, 
        task: Task, 
        timeout_seconds: float = 30.0
    ) -> TaskResult:
        """
        Execute tool dengan timeout protection.
        
        Args:
            task: Task untuk dieksekusi
            timeout_seconds: Maximum execution time
            
        Returns:
            TaskResult (success atau timeout error)
        """
        try:
            return await asyncio.wait_for(
                self.execute(task), 
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            return TaskResult.failure_result(
                task_id=task.id,
                error=f"Tool execution timed out after {timeout_seconds}s",
                error_code="TIMEOUT"
            )
    
    def _record_execution(self, success: bool):
        """Record execution untuk metrics."""
        self._execution_count += 1
        if not success:
            self._error_count += 1


class ToolRegistry:
    """
    Registry untuk managing dan discovering tools.
    
    ToolRegistry menyimpan semua registered tools dan menyediakan
    discovery mechanism untuk agents.
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """
        Register a tool ke registry.
        
        Args:
            tool: Tool instance untuk diregister
            
        Raises:
            ValueError: Jika tool dengan nama sama sudah diregister
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        
        self._tools[tool.name] = tool
    
    def unregister(self, tool_name: str) -> None:
        """
        Unregister a tool dari registry.
        
        Args:
            tool_name: Name of tool to unregister
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        Get tool by name.
        
        Args:
            tool_name: Name of tool to retrieve
            
        Returns:
            Tool instance atau None jika tidak ditemukan
        """
        return self._tools.get(tool_name)
    
    def list_tools(self) -> List[str]:
        """
        List all registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())
    
    def get_all_definitions(self) -> List[Dict[str, Any]]:
        """
        Get definitions untuk semua registered tools.
        
        Returns:
            List of tool definitions
        """
        return [
            tool.tool_definition.to_dict() 
            for tool in self._tools.values()
        ]
    
    def find_tool_for_task(self, task: Task) -> Optional[BaseTool]:
        """
        Find tool yang bisa handle given task.
        
        Args:
            task: Task untuk dicari handler
            
        Returns:
            Tool instance atau None
        """
        for tool in self._tools.values():
            if tool.can_handle(task):
                return tool
        return None
    
    def get_registry_info(self) -> Dict[str, Any]:
        """
        Get registry metadata.
        
        Returns:
            Dictionary dengan registry info
        """
        return {
            "registered_tools": len(self._tools),
            "tool_names": self.list_tools(),
            "tools": {
                name: tool.get_handler_info()
                for name, tool in self._tools.items()
            }
        }


# Global registry instance
tool_registry = ToolRegistry()

# Registry untuk function-based tools
function_tools: Dict[str, callable] = {}


def register_tool(tool):
    """
    Decorator untuk register tool ke global registry.
    
    Supports both class-based tools (extends BaseTool) dan function-based tools.
    
    Usage (Class):
        @register_tool
        class MyTool(BaseTool):
            ...
    
    Usage (Function):
        @register_tool
        def my_tool(file_path: str) -> Dict:
            ...
    """
    # Check if it's a class or function
    if isinstance(tool, type):
        # Class-based tool
        if issubclass(tool, BaseTool):
            tool_instance = tool()
            tool_registry.register(tool_instance)
        return tool
    elif callable(tool):
        # Function-based tool
        function_tools[tool.__name__] = tool
        return tool
    else:
        raise TypeError(f"Tool must be a class extending BaseTool or a callable, got {type(tool)}")


def get_function_tool(name: str) -> Optional[callable]:
    """Get function-based tool by name."""
    return function_tools.get(name)


def list_function_tools() -> List[str]:
    """List all registered function-based tool names."""
    return list(function_tools.keys())
