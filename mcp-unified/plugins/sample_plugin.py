from execution import registry, resource_registry, prompt_registry

@registry.register(name="auto_discovered_tool")
def example_tool(arg: str):
    """An auto-discovered tool example."""
    return f"Auto-discovered result for: {arg}"

@resource_registry.register(
    uri="plugin:///info",
    name="Plugin Information",
    description="Shows that discovery is working",
    mime_type="text/plain"
)
def get_plugin_info(uri: str):
    return "This resource was auto-discovered from the plugins directory!"

prompt_registry.register(
    name="auto_prompt",
    template="This is an auto-discovered prompt with arg: {arg}",
    description="Auto-discovered prompt example"
)
