# OpenHands Admin Server - RUNBOOK

## 📋 Deskripsi
OpenHands Admin Server adalah layanan kontrol operasional untuk mengelola AI Agent OpenHands dan layanan pendukung lainnya dalam ekosistem MCP Unified. Berjalan pada port **8095**.

## 🚀 Startup Guide

### Manual Start
```bash
export OPENHANDS_ADMIN_PORT=8095
cd /home/aseps/MCP/mcp-unified
python3 -m plugins.openhands.admin_server
```

### Background Start (via Service Controller)
Layanan ini dapat dikontrol melalui Dashboard Utama atau script `run_mcp_with_services.sh`.

## 🔌 API Endpoints

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/health` | Health check layanan admin |
| `GET` | `/services` | Status semua layanan (WhatsApp, Telegram, dll) |
| `POST` | `/services/{name}/start` | Menjalankan layanan tertentu |
| `POST | `/services/{name}/stop` | Menghentikan layanan tertentu |
| `GET` | `/services/{name}/logs` | Mengambil log layanan tertentu |

## 🛠️ Troubleshooting

### Port Conflict (8095)
Jika port 8095 sudah digunakan, Anda bisa mengubahnya melalui environment variable:
```bash
export OPENHANDS_ADMIN_PORT=8096
```

### Log File
Seluruh log aktivitas admin server tersimpan di:
`/tmp/openhands_admin.log`

---
*Status: Operasional*
