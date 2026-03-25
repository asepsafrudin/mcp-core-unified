# Self-Healing Agent

## Overview
Self-healing agent yang melakukan health check MCP server tiap hari jam `SELF_HEALING_DAILY_TIME`
dan menjalankan recovery script jika ada kegagalan. Notifikasi dikirim ke Telegram untuk setiap hasil.

## Konfigurasi (.env)
```
SELF_HEALING_ENABLED=true
SELF_HEALING_DAILY_TIME=00:05
SELF_HEALING_RECOVERY_SCRIPTS=/home/aseps/MCP/mcp-unified/core/monitoring/recovery.sh
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_CREDENTIALS_PATH=/home/aseps/MCP/credentials/telegram.env
SELF_HEALING_EXTRA_SERVICES=service_cmd1,service_cmd2
```

## Menjalankan Agent
```
python mcp-unified/core/monitoring/run_self_healing.py
```

## Cron (auto-run harian)
```
5 0 * * * /home/aseps/MCP/.venv/bin/python /home/aseps/MCP/mcp-unified/core/monitoring/run_self_healing.py >> /home/aseps/MCP/logs/self_healing.log 2>&1
```

## Systemd (opsional)
Contoh unit: `mcp-unified/core/monitoring/mcp-self-healing.service`
```
[Unit]
Description=MCP Self Healing Agent

[Service]
WorkingDirectory=/home/aseps/MCP
ExecStart=/home/aseps/MCP/.venv/bin/python /home/aseps/MCP/mcp-unified/core/monitoring/run_self_healing.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Manual Health Check (Tool)
Gunakan tool `mcp_health_check` lewat MCP server.