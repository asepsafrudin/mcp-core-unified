# Shared Utilities untuk MCP Project

Direktori ini berisi utilities dan modules yang digunakan bersama oleh berbagai komponen dalam project MCP.

## Modules

### `mcp_client.py`
Client universal untuk komunikasi dengan MCP server. Digunakan oleh:
- CrewAI agents (`crew/`)
- MCP server tools
- External integrations

**Fungsi utama:**
- `call_mcp_tool(name, arguments, timeout)` - Panggil MCP tool via subprocess
- `mcp_list_dir(path)` - List directory contents
- `mcp_read_file(path)` - Read file contents
- `mcp_write_file(path, content)` - Write file
- `mcp_memory_save(key, content)` - Save to memory
- `mcp_memory_search(query)` - Search memory
- `mcp_run_shell(command)` - Execute shell command

## Usage

```python
# Import dari shared module
from shared.mcp_client import call_mcp_tool, mcp_list_dir

# Gunakan fungsi
result = mcp_list_dir("/workspace")
print(result)
```

## Maintenance

File-file di direktori ini digunakan oleh multiple komponen. Perubahan harus:
1. Backward compatible
2. Tested dengan semua komponen yang menggunakan
3. Documented dengan jelas
