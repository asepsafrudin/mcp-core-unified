# MCP Unified Server

Server terpadu untuk Agentic IDE, menyediakan platform hosting untuk tool-tool yang dapat diakses oleh berbagai agen.

## Deskripsi

MCP Unified Server adalah server berbasis FastAPI yang dirancang untuk menjadi tulang punggung dari arsitektur agen terdistribusi. Server ini memungkinkan registrasi, penemuan, dan eksekusi "tool" (alat) secara terpusat. Agen-agen dapat terhubung ke server ini untuk mengakses fungsionalitas yang disediakan oleh tool-tool tersebut.

Server ini dibangun dengan mempertimbangkan skalabilitas, ketahanan, dan observabilitas, dengan fitur-fitur seperti circuit breaker, rate limiting, logging terstruktur, dan metrik.

## Fitur Utama

- **Tool Registry (Auto Discovery)**: Mekanisme otomatis untuk mendeteksi dan mendaftarkan tool baru menggunakan dekorator `@registry.register`.
- **Resource Support**: Mengekspos data read-only (seperti log sistem, status, atau dokumen statis) via `@resource_registry.register`.
- **Prompts Management**: Template instruksi siap pakai yang dapat dipanggil oleh agen via `@prompt_registry.register`.
- **Eksekusi Tool Multi-Bahasa**: Dukungan eksekusi tool berbasis Python, Bash (.sh), dan JavaScript (.js).
- **Penemuan Tool Jarak Jauh**: Kemampuan untuk menemukan dan mengintegrasikan tool dari server MCP lain secara transparan.
- **Arsitektur Berbasis FastAPI**: Performa tinggi dan pengembangan API yang cepat.
- **Ketahanan Sistem**:
    - **Circuit Breaker**: Mencegah kegagalan beruntun saat tool mengalami masalah.
    - **Rate Limiter**: Mengontrol tingkat penggunaan tool untuk mencegah penyalahgunaan.
- **Observabilitas**:
    - **Logging Terstruktur**: Log dalam format JSON untuk memudahkan analisis.
    - **Metrik**: Endpoint untuk memantau kesehatan dan performa server.
- **Manajemen Konfigurasi**: Konfigurasi berbasis environment variable untuk fleksibilitas.
- **Penyimpanan**: Menggunakan PostgreSQL untuk penyimpanan jangka panjang dan Redis untuk memori kerja.
- **Mode Terdistribusi**: Dukungan untuk worker node dengan RabbitMQ untuk pemrosesan tugas terdistribusi.

## 🔧 Agent Database Access

Untuk agent, IDE, atau OpenHands task yang perlu mengakses knowledge base / PostgreSQL:

- [../docs/06-database/agent-startup-matrix.md](../docs/06-database/agent-startup-matrix.md)
- [../docs/06-database/agent-db-access-notes.md](../docs/06-database/agent-db-access-notes.md)
- [../docs/06-database/agent-db-debug-checklist.md](../docs/06-database/agent-db-debug-checklist.md)

Petunjuk cepat:
- selalu verifikasi `DATABASE_URL` dan `PG_*` di runtime
- jangan berasumsi `localhost` sandbox sama dengan host machine
- untuk task OpenHands, cek resource:
  - `mcp://openhands/task/env-context` (Snapshot environment)
  - `mcp://openhands/task/logs?task_id=XYZ` (Log eksekusi agent)
  - `mcp://openhands/task/status?task_id=XYZ` (Status lengkap JSON)

## Struktur Direktori

```
mcp-unified/
├── agents/           # Logika agen (App Developer, Code Agent, Research, dll)
├── core/             # Core logic (FastAPI server, auth, middleware)
├── domains/          # Definisi domain talent (development, legal, communications)
├── execution/        # Logika eksekusi tool, registry, workspace, dan discovery engine
├── plugins/          # Custom tools, resources, dan prompts (Hot-reloadable)
├── intelligence/     # Komponen cerdas (planner, self-healing)
├── integrations/     # Integrasi eksternal (Telegram, WhatsApp, GDrive, OpenHands)
├── memory/           # Manajemen memori (PostgreSQL + pgvector)
├── messaging/        # Message queue (RabbitMQ)
├── monitoring/       # Health checks dan dashboard background services
├── observability/    # Logging terstruktur dan metrik
├── scheduler/        # Sistem penjadwalan tugas (daemon)
├── simulation/       # Simulasi dan testing
├── scripts/          # Runner scripts (run_api.sh, run_sse.sh, run_mcp_with_services.sh)
├── tests/            # Tes unit dan integrasi
├── mcp_server.py     # Entry point untuk MCP SDK (stdio protocol)
├── worker_node.py    # Worker node untuk mode terdistribusi
├── requirements.txt  # Dependensi Python
└── README.md         # Dokumentasi ini
```

## Instalasi

1.  **Buat dan aktifkan virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # Linux/Mac
    # atau
    .venv\Scripts\activate  # Windows
    ```

2.  **Install dependensi:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup Environment Variables:**
    Salin file `.env.example` dari root project menjadi `.env` dan sesuaikan nilainya:
    ```bash
    cp ../.env.example .env
    ```

## Menjalankan Server

Server dapat dijalankan dalam dua mode:

### Mode 1: FastAPI HTTP Server

Cocok untuk akses API langsung dan integrasi dengan aplikasi lain.

```bash
chmod +x scripts/run_api.sh
./scripts/run_api.sh
```

Server akan berjalan di `http://0.0.0.0:8000`.

### Mode 2: MCP SDK Server (stdio)

Cocok untuk integrasi dengan IDE yang mendukung protokol MCP.

```bash
python mcp_server.py
```

### Mode 3: MCP SDK Server + Auto Services (Postgres/Redis + Bots + Scheduler)

Gunakan skrip ini untuk menjalankan MCP stdio server **sekaligus** memastikan
service pendukung (Postgres/Redis) berjalan via `setup_database.sh`,
menjalankan **WhatsApp gateway + Telegram bot** via `restart_bots.sh`,
serta **scheduler daemon** (`mcp-scheduler.service` bila systemd tersedia).

Untuk menonaktifkan auto-start scheduler, set env berikut sebelum menjalankan:
```bash
export ENABLE_SCHEDULER=false
```

Untuk mengontrol auto-start bots, gunakan env berikut:
```bash
export ENABLE_BOTS=false         # disable semua bots
export ENABLE_WHATSAPP=false     # disable WhatsApp bot saja
export ENABLE_TELEGRAM=false     # disable Telegram bot saja
```

Untuk mengontrol auto-start Admin UI (FastAPI):
```bash
export ENABLE_ADMIN_UI=false
```

```bash
chmod +x run_mcp_with_services.sh
./run_mcp_with_services.sh
```

Subcommand operasional yang tersedia:

```bash
./run_mcp_with_services.sh status
./run_mcp_with_services.sh start-admin
./run_mcp_with_services.sh start-bots
./run_mcp_with_services.sh start-sse
./run_mcp_with_services.sh start-stdio
./run_mcp_with_services.sh start-llm-api
./run_mcp_with_services.sh start-scheduler
./run_mcp_with_services.sh start-all
```

Ringkasannya:
- `status`: cek health runtime tanpa expose secret
- `start-admin`: start FastAPI admin/API saja
- `start-bots`: restart WhatsApp dan Telegram bot
- `start-sse`: jalankan SSE server di foreground bila port `8000` belum dipakai
- `start-stdio`: jalankan MCP stdio server saja
- `start-llm-api`: start standalone LLM API di port `8088`
- `start-scheduler`: start scheduler via `systemd` atau daemon background
- `start-all`: jalur lengkap, kompatibel dengan perilaku lama `./run_mcp_with_services.sh`

### Mode 4: MCP SSE Server (Starlette)

Jika kamu butuh mode SSE (mis. integrasi streaming), jalankan:

```bash
chmod +x scripts/run_sse.sh
./scripts/run_sse.sh
```

> Catatan: `run.sh` / `run_api.sh` / `run_sse.sh` masih ada untuk kompatibilitas, dan menjadi wrapper ke `scripts/run_api.sh` dan `scripts/run_sse.sh`.

### Makefile shortcuts

Alternatif lebih singkat:

```bash
make run-api
make run-sse
make run-stdio
```

### Web UI: Service Controller (Admin)

Saat menjalankan **FastAPI server** (`./run.sh`), kamu bisa membuka UI kontrol layanan:

```
http://localhost:8000/admin/services
```

UI ini membutuhkan **API Key admin** (gunakan header `X-API-Key` atau login via endpoint `/auth/login`).
Endpoint API terkait:
- `GET /admin/services/status`
- `POST /admin/services/{service}/start`
- `POST /admin/services/{service}/stop`
- `POST /admin/services/{service}/restart`
- `GET /admin/services/{service}/logs?lines=200`
- `GET /admin/services/status` (kini mengembalikan `error_summary`)

Service yang tersedia di UI:
- `mcp_sse` (MCP SSE Server)
- `knowledge_admin` (Knowledge Admin Dashboard)
- `whatsapp` (WhatsApp Bot)
- `telegram` (Telegram Bot)
- `telegram_sql_bot` (Telegram SQL Bot, service terpisah/legacy)
- `telegram_watcher` (Telegram Watcher)
- `gdrive_mount` (GDrive Mount - systemd user)
- `self_healing` (Self-Healing Agent - one-off)
- `scheduler` (MCP Scheduler)
- `legal_agent_timers` (Legal Agent timers)

### 🤖 Telegram Bot (Aria)

Bot Telegram **Aria** telah ditingkatkan menjadi asisten cerdas yang mendukung operasional korespondensi:

- **Integrasi OCR (Optical Character Recognition)**:
    - Ekstraksi teks otomatis dari PDF (max 5 hal) dan gambar (JPG/PNG).
    - Teks disimpan ke memori percakapan untuk referensi AI.
- **Interactive Dashboard**:
    - Perintah `/dashboard` kini interaktif dengan tombol inline untuk akses cepat ke data Masuk, Keluar, dan Anomali.
    - Tombol `🔄 Sync` dengan mekanisme anti-spam (lock-file).
- **Hardening & Audit**:
    - **Default-Deny Authentication**: Hanya pengguna dalam whitelist `.env` yang dapat mengakses.
    - **Audit Logging**: Setiap pemanggilan tool LLM dicatat dengan durasi dan ringkasan hasil (`[AUDIT]`).
    - **Think Tag Removal**: Respon AI bersih dari tag teknis `<think>`.

## Menjalankan Worker Node (Mode Terdistribusi)

Untuk mode terdistribusi dengan RabbitMQ:

```bash
# Set environment variables
export RABBITMQ_URL="amqp://mcp_user:password@localhost/"
export WORKER_ID="worker-node-1"

# Jalankan worker
python worker_node.py
```

## Konfigurasi

Konfigurasi server diatur melalui environment variable. Salin file `.env.example` menjadi `.env` dan sesuaikan nilainya.

### Variabel Wajib

| Variable | Deskripsi | Default |
|----------|-----------|---------|
| `POSTGRES_USER` | Username database PostgreSQL | - |
| `POSTGRES_PASSWORD` | Password database PostgreSQL | - |
| `POSTGRES_SERVER` | Hostname database PostgreSQL | `localhost` |
| `POSTGRES_DB` | Nama database PostgreSQL | `mcp` |
| `REDIS_URL` | URL koneksi ke Redis | `redis://localhost:6379/0` |

### Variabel Opsional

| Variable | Deskripsi | Default |
|----------|-----------|---------|
| `LOG_LEVEL` | Level logging (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `RABBITMQ_DEFAULT_USER` | Username RabbitMQ (untuk distributed mode) | `mcp_user` |
| `RABBITMQ_DEFAULT_PASS` | Password RabbitMQ (untuk distributed mode) | - |
| `MAX_WORKERS` | Jumlah maksimum worker | `4` |
| `REQUEST_TIMEOUT` | Timeout request dalam detik | `30` |
| `ENABLE_METRICS` | Aktifkan metrik | `true` |

## Endpoints API

### Health & Monitoring

- `GET /health` - Memeriksa status kesehatan server
  ```json
  {"status": "ok", "version": "1.0.0"}
  ```

- `GET /metrics/summary` - Mendapatkan ringkasan metrik performa

### Tool Management

- `POST /tools/list` - Menampilkan daftar semua tool yang terdaftar
  ```json
  {
    "tools": [
      {"name": "read_file", "description": "Read a file from the filesystem"},
      {"name": "write_file", "description": "Write content to a file"}
    ]
  }
  ```

- `POST /tools/call` - Mengeksekusi tool tertentu
  - **Request Body**:
    ```json
    {"name": "nama_tool", "arguments": { "arg1": "value1" }}
    ```
  - **Response Sukses**:
    ```json
    {"content": [{"type": "text", "text": "result"}]}
    ```
  - **Response Error**:
    ```json
    {"isError": true, "content": [{"type": "text", "text": "error message"}]}
    ```

## 🤖 Agen Cerdas (Intelligence Layer)

`mcp-unified` bukan sekadar server tool, tetapi juga mengelola agen cerdas yang memiliki spesialisasi domain.

### Daftar Agen yang Tersedia:

1.  **App Developer Agent** (`app_developer_agent`): 
    *   **Peran**: Spesialis pengembangan aplikasi ujung-ke-ujung.
    *   **Kapasitas**: Scaffolding, CRUD generation, DB migrations, Full-stack development.
    *   **Integrasi**: Menggunakan **OpenHands SDK** untuk eksekusi tugas coding di lingkungan terisolasi (sandbox).

2.  **Code Agent** (`code_agent`):
    *   **Peran**: Analisis dan review kode.
    *   **Kapasitas**: Security audit, refactoring, quality checks, bug finding.

3.  **Research Agent** (`research_agent`):
    *   **Peran**: Pengumpulan dan sintesis informasi.
    *   **Kapasitas**: Web browsing, documentation analysis, summarization.

4.  **Legal Agent** (`legal_agent`):
    *   **Peran**: Analisis dokumen hukum dan regulasi.
    *   **Kapasitas**: Pencarian UU, cek kepatuhan regulasi, ekstraksi klausa dokumen.

### Cara Kerja Agen:
Agen menerima tugas → Melakukan penalaran (*Reasoning*) → Membuat rencana (*Planning*) → Menggunakan tool yang relevan (via MCP Registry) → Mengembalikan hasil.

---

## Testing

```bash
# Jalankan semua test
pytest tests/

# Jalankan test spesifik
pytest tests/test_capabilities.py
pytest tests/test_self_healing.py
pytest tests/test_tokens.py
```

## Tool & Registry (Dynamic)

Sistem kini menggunakan **Auto Discovery**. Tool tidak lagi didaftarkan secara manual di core code, melainkan dideteksi dari folder `plugins/`, `execution/tools/`, `memory/`, `intelligence/`, dan `messaging/`.

### Cara Menambah Tool Baru
Cukup gunakan dekorator `@registry.register` pada fungsi Python Anda, atau letakkan script `.sh` / `.js` di folder `plugins/`.

### Tool Core yang Tersedia:

### File Tools
- `list_dir(path)` - List direktori
- `read_file(path)` - Baca file
- `write_file(path, content)` - Tulis file

### Shell Tools
- `run_shell(command, timeout)` - Jalankan perintah shell

### Memory Tools
- `memory_save(key, content, metadata, namespace)` - Simpan memori
- `memory_search(query, namespace, limit, strategy)` - Cari memori
- `memory_list(namespace, limit, offset)` - List memori

### Workspace Tools
- `create_workspace(name)` - Buat workspace
- `cleanup_workspace(name)` - Bersihkan workspace

### Intelligence Tools
- `create_plan(objective, steps)` - Buat rencana
- `save_plan_experience(plan_id, outcome)` - Simpan pengalaman plan

### Distributed Tools
- `publish_remote_task(task_type, payload)` - Publish tugas ke worker

## Dependensi Utama

- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **Structlog** - Logging terstruktur
- **Pydantic** - Validasi data
- **Asyncpg/Psycopg** - PostgreSQL driver
- **Redis** - Cache dan working memory
- **Aio-pika** - RabbitMQ client (untuk distributed mode)

## Catatan Keamanan

- Selalu gunakan environment variables untuk kredensial
- Jangan pernah commit file `.env` ke version control
- Gunakan namespace isolation untuk memori antar project
- Circuit breaker dan rate limiter aktif secara default

## Lisensi

[License Information]
