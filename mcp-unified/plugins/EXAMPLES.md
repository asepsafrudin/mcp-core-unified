# 🧪 Plugin Examples - MCP Unified

Dokumen ini berisi contoh implementasi untuk memperluas kemampuan MCP Unified Server secara mandiri.

## 1. Python Tool Plugin
Buat file `plugins/tools/weather.py`:

```python
from execution import registry
import httpx

@registry.register
async def get_weather(city: str):
    """
    Get current weather for a specific city.
    Args:
        city: Name of the city (e.g., 'Jakarta')
    """
    # Contoh implementasi sederhana
    return {
        "city": city,
        "temperature": "32°C",
        "condition": "Partly Cloudy"
    }
```

## 2. Bash Tool Plugin
Buat file `plugins/tools/disk_usage.sh`:

```bash
#!/bin/bash
# Tool: disk_usage
# Description: Check disk usage of a path
# Usage: disk_usage --path /home

PATH_ARG="/"
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --path) PATH_ARG="$2"; shift ;;
    esac
    shift
done

df -h "$PATH_ARG"
```
*Jangan lupa jalankan `chmod +x plugins/tools/disk_usage.sh`*

## 3. Resource Plugin
Buat file `plugins/resources/logs.py`:

```python
from execution import resource_registry
import os

@resource_registry.register(uri="mcp://logs/app", name="Application Logs")
async def read_app_logs():
    log_path = "server.log"
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            return f.read()[-1000:] # Last 1000 chars
    return "Log file not found"
```

## 4. Prompt Plugin
Buat file `plugins/prompts/coding.py`:

```python
from execution import prompt_registry

@prompt_registry.register(name="review-security", description="Scan code for security vulnerabilities")
async def security_prompt(code: str):
    return (
        "As a security expert, please review the following code for vulnerabilities "
        "such as SQL injection, command injection, and hardcoded secrets:\n\n"
        f"CODE:\n{code}"
    )
```

---
**Tips:**
- Server akan mendeteksi file baru secara otomatis saat startup.
- Jika menggunakan mode API (`./run.sh` dengan `MCP_RELOAD=true`), server akan restart otomatis saat file plugin berubah.
- Pastikan docstring pada fungsi Python jelas, karena ini digunakan oleh AI untuk memahami cara memakai tool Anda.
