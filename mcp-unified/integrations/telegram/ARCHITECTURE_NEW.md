# Telegram Architecture

Dokumen ini adalah source of truth ringkas untuk arsitektur Telegram yang aktif saat ini.

## Prinsip Utama

1. Bot chat Telegram utama difokuskan untuk percakapan, korespondensi, dan operasional ringan.
2. Memory agent, LTM file/server, dan knowledge database bukan konteks default bot chat.
3. Bridge ke agent tetap tersedia, tetapi harus eksplisit.
4. SQL bot dan service knowledge diperlakukan sebagai jalur terpisah/legacy.

## Domain yang Dipisahkan

### 1. Telegram Chat Runtime

Komponen utama:
- `run.py`
- `bot.py`
- `handlers/messages.py`
- `handlers/media.py`
- `handlers/commands.py`
- `services/telegram_context_service.py`

Karakteristik:
- konteks percakapan lokal per user
- tidak menarik LTM/knowledge agent sebagai default context
- agentic tools dibatasi ke tool operasional Telegram

### 2. Agent Bridge

Komponen utama:
- `services/agent_bridge_memory_service.py`
- `bridges/cline_bridge.py`
- command `/cline`

Karakteristik:
- dipakai hanya saat handoff atau eskalasi ke agent diperlukan
- tetap boleh memakai MCP/memory agent

### 3. Legacy / Separated Services

Komponen utama:
- `legacy/bot_server.py`
- `legacy/bot_server_sql_focused.py`
- `run_sql_bot.sh`

Karakteristik:
- dipertahankan untuk kompatibilitas
- bukan runtime utama
- boleh diarsipkan lebih lanjut jika sudah tidak dipakai

## Entry Points

- Bot utama: `python3 run.py`
- Runner utama: `./run.sh`
- SQL bot legacy: `python3 legacy/bot_server_sql_focused.py`

## Rules of Thumb

- Jika fitur itu untuk chat Telegram sehari-hari, tempatkan di runtime utama.
- Jika fitur itu butuh memory agent/knowledge DB, pertimbangkan bridge atau service terpisah.
- Jika perubahan baru membuat Telegram chat kembali tergantung ke LTM/knowledge agent, itu biasanya tanda arsitektur mulai tercampur lagi.
