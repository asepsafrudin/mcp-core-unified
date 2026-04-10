# 🚀 Quick Start - MCP Unified

## Masalah yang Sering Terjadi

### ❌ "Module 'mcp' not found"
**Penyebab:** MCP SDK belum terinstall  
**Solusi:**
```bash
cd /home/aseps/MCP/mcp-unified
./setup.sh
```

### ❌ "Connection refused" PostgreSQL/Redis
**Penyebab:** Database belum running (TAPI server tetap bisa jalan!)  
**Solusi:** Server akan auto-start tanpa fitur memory. Untuk full feature, jalankan:
```bash
# Terminal 1: Start PostgreSQL
sudo service postgresql start

# Terminal 2: Start Redis
redis-server

# Terminal 3: Jalankan MCP
./run.sh
```

---

## ✅ Cara Menjalankan (Minimal)

### Step 1: Install Dependencies
```bash
cd /home/aseps/MCP/mcp-unified
pip install mcp fastapi uvicorn pydantic httpx
```

### Step 2: Jalankan Server
Ada 2 mode:

#### Mode A: HTTP Server (untuk testing)
```bash
./run.sh
# Server jalan di http://localhost:8000
```

#### Mode B: MCP Protocol (untuk production)
```bash
python3 mcp_server.py
# Server berkomunikasi via stdio (MCP protocol)
```

---

## 🔧 Mode Tanpa Database (Lightweight)

Jika hanya ingin tools dasar tanpa memory:

```bash
# Set environment variable
export MEMORY_MODE=disabled

# Jalankan server
python3 mcp_server.py
```

Server akan jalan dengan tools:
- ✅ Shell execution (run_shell)
- ✅ Workspace management
- ❌ Memory save/search (butuh PostgreSQL)

---

## 🧩 Auto Discovery & Plugin System

Server kini mendukung pengenalan otomatis untuk tools, resources, dan prompts. Anda tidak perlu lagi mendaftarkan tool secara manual di `registry.py`.

### 1. Cara Menambah Tool (Python)
Cukup buat file `.py` di dalam folder `plugins/tools/` dan gunakan dekorator `@registry.register`:

```python
from execution import registry

@registry.register
async def my_new_tool(name: str):
    """Deskripsi tool yang akan dibaca oleh AI"""
    return {"message": f"Hello {name}!"}
```

### 2. Cara Menambah Tool (Bash/Shell)
Simpan script `.sh` Anda di dalam folder `plugins/tools/`. Server akan otomatis membungkusnya sebagai tool MCP:
- **Input:** Argumen dikirim via flag `--key value`.
- **Lokasi:** `plugins/tools/hello.sh` akan menjadi tool `hello`.

### 3. Cara Menambah Tool (JavaScript/Node.js)
Simpan file `.js` Anda di folder `plugins/tools/`.
- **Input:** Argumen dikirim sebagai JSON string di argumen pertama.

---

## 📦 Resources & Prompts

### Resources (Data Read-Only)
Gunakan `@resource_registry.register`:
```python
from execution import resource_registry

@resource_registry.register(uri="mcp://system/status", name="System Status")
async def get_status():
    return "System is healthy"

# Resource Dinamis (dengan prefix matching)
# mcp://openhands/task/logs?task_id=XYZ
```

### Prompts (Template Instruksi)
Gunakan `@prompt_registry.register`:
```python
from execution import prompt_registry

@prompt_registry.register(name="analyze-code", description="Analyze code quality")
async def analyze_prompt(code: str):
    return f"Please analyze this code: {code}"
```

---

## 📋 Checklist Sebelum Menjalankan

- [ ] MCP SDK terinstall: `python3 -c "import mcp"`
- [ ] Python 3.10+: `python3 --version`
- [ ] Port 8000 tersedia (untuk HTTP mode)

Optional:
- [ ] PostgreSQL running (untuk memory)
- [ ] Redis running (untuk working memory)
- [ ] RabbitMQ running (untuk distributed tasks)

---

## 🐛 Troubleshooting

### Error: "Address already in use"
```bash
# Cari process yang pakai port 8000
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Error: "Permission denied"
```bash
chmod +x run.sh setup.sh
```

### Error: "Module not found"
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

---

## 📚 Arsitektur

```
┌─────────────────────────────────────────┐
│           mcp-unified                   │
├─────────────────────────────────────────┤
│  mcp_server.py  │  core/server.py       │
│  (MCP Protocol) │  (HTTP API)           │
├─────────────────────────────────────────┤
│  execution/  │  memory/  │ intelligence/ │
│  Tools       │  Storage  │  Planner      │
├─────────────────────────────────────────┤
│  PostgreSQL (opsional)                  │
│  Redis (opsional)                       │
└─────────────────────────────────────────┘
```

---

## 🎯 Mode Rekomendasi

| Use Case | Command | Database |
|----------|---------|----------|
| Development/Test | `./run.sh` | Tidak wajib |
| Production MCP | `python3 mcp_server.py` | Tidak wajib |
| Full Features | `./run.sh` + PostgreSQL + Redis | Wajib |

---

**Catatan:** Server akan tetap berfungsi meskipun PostgreSQL/Redis tidak tersedia. Hanya fitur memory yang akan disabled.
