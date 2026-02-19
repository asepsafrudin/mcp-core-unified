import pytest
from memory.token_manager import token_manager

@pytest.mark.asyncio
async def test_token_counting():
    text = "Hello world"
    count = token_manager.count_tokens(text)
    assert count > 0

@pytest.mark.asyncio
async def test_ast_compression():
    # Create a dummy python file content
    py_code = """
class TestClass:
    def method_one(self):
        print("logic")
        
def global_func():
    return True

# Add a very long comment to exceed 500 tokens threshold
# """ + ("very long comment " * 200) + """
"""
    # We need to mock read_file because token_manager reads from disk
    # Ideally checking _summarize_file logic if it was isolated well or 
    # we can create a temp file.
    
    import os
    with open("temp_test.py", "w") as f:
        f.write(py_code)
        
    try:
        summary = await token_manager._summarize_file("temp_test.py")
        assert "TestClass" in summary["classes"]
        assert "global_func" in summary["functions"]
        assert summary["type"] == "python_ast_summary"
    finally:
        os.remove("temp_test.py")
