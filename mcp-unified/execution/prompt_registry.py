from typing import Dict, List, Any, Optional, Union, Callable
from pydantic import BaseModel
from observability.logger import logger

class PromptArgument(BaseModel):
    name: str
    description: Optional[str] = None
    required: bool = True

class Prompt(BaseModel):
    name: str
    description: Optional[str] = None
    arguments: List[PromptArgument] = []

class PromptRegistry:
    def __init__(self):
        self._prompts: Dict[str, Prompt] = {}
        self._templates: Dict[str, str] = {}

    def register(self, name: str, template: str, description: str = None, arguments: List[PromptArgument] = None):
        """
        Register a prompt template for agents to use.
        Can be used as a function or a decorator.
        
        Example:
            prompt_registry.register(
                "code_review",
                "Review the following code: {code}.",
                "Review code",
                [PromptArgument(name="code", description="The code to review")]
            )
            
            @prompt_registry.register("my_prompt", "Hello {name}")
            def my_prompt_placeholder(): 
                pass
        """
        prompt = Prompt(
            name=name,
            description=description,
            arguments=arguments or []
        )
        self._prompts[name] = prompt
        self._templates[name] = template
        
        # Return a decorator that returns the function unchanged
        return lambda func: func

    def list_prompts(self) -> List[Prompt]:
        """List all registered prompt templates."""
        return list(self._prompts.values())

    def get_prompt(self, name: str, arguments: Dict[str, str] = None) -> str:
        """Render a prompt template with provided arguments."""
        if name not in self._templates:
            raise ValueError(f"Prompt '{name}' not found in registry.")
        
        template = self._templates[name]
        try:
            # Add defaults for optional arguments if needed
            args = arguments or {}
            
            # Simple str.format rendering
            return template.format(**args)
        except KeyError as e:
            raise ValueError(f"Missing mandatory argument for prompt '{name}': {str(e)}")
        except Exception as e:
            logger.error("prompt_render_error", name=name, error=str(e))
            raise

prompt_registry = PromptRegistry()
