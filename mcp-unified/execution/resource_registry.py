from typing import Dict, List, Any, Callable, Optional, Union
from pydantic import BaseModel
import inspect
import asyncio
from observability.logger import logger

class Resource(BaseModel):
    uri: str
    name: str
    description: Optional[str] = None
    mimeType: Optional[str] = None

class ResourceRegistry:
    def __init__(self):
        self._resources: Dict[str, Resource] = {}
        self._handlers: Dict[str, Callable] = {}

    def register(self, uri: str, name: str, description: Optional[str] = None, mime_type: Optional[str] = None):
        """
        Decorator or function to register a resource handler.
        
        Example:
            @resource_registry.register("file:///logs/server.log", "Server Logs", "Recent server logs")
            async def get_logs(uri: str):
                with open("server.log", "r") as f:
                    return f.read()
        """
        def decorator(handler: Callable):
            resource = Resource(
                uri=uri,
                name=name,
                description=description,
                mimeType=mime_type
            )
            self._resources[uri] = resource
            self._handlers[uri] = handler
            return handler
        
        # If used as a normal function call (not decorator)
        if callable(uri):
             raise ValueError("Resource URI must be a string. Usage: @register(uri, name, ...)")
             
        return decorator

    def list_resources(self) -> List[Resource]:
        """List all registered resources."""
        return list(self._resources.values())

    async def read_resource(self, uri: str) -> str:
        """Execute the handler for a specific resource URI."""
        handler = self._handlers.get(uri)
        
        # If no exact match, try prefix matching for dynamic resources (e.g. with query params)
        if not handler:
            for registered_uri, registered_handler in self._handlers.items():
                if uri.startswith(registered_uri):
                    handler = registered_handler
                    break
                    
        if not handler:
            raise ValueError(f"Resource URI '{uri}' not found in registry.")
        
        try:
            if inspect.iscoroutinefunction(handler):
                return await handler(uri)
            else:
                return handler(uri)
        except Exception as e:
            logger.error("resource_read_error", uri=uri, error=str(e))
            raise

resource_registry = ResourceRegistry()
