# 🤖 Telegram Bot Integration

Bot Telegram utama untuk percakapan, korespondensi, dan operasional ringan.
Paradigma terbaru:
- Memory agent, LTM file/server, dan knowledge database bukan lagi konteks default bot chat.
- Bot chat Telegram memakai konteks percakapan lokal yang ringan.
- Bridge ke agent tetap tersedia secara eksplisit melalui fitur seperti `/cline`.

Lihat juga:
- `ARCHITECTURE_NEW.md` untuk ringkasan arsitektur aktif.

## 📋 Fitur

- ✅ **Two-Way Communication**: Kirim prompt dari Telegram, terima respon dari AI
- ✅ **Multi-Modal**: Dukung teks, gambar, dan dokumen
- ✅ **User Management**: Whitelist user untuk keamanan
- ✅ **Mode Polling & Webhook**: Fleksibel untuk development dan production
- ✅ **Bridge ke Agent**: Forward pesan tertentu ke agent/Cline saat memang dibutuhkan

## 🚀 Quick Start

### 1. Setup Bot Telegram

1. Buka [@BotFather](https://t.me/botfather) di Telegram
2. Kirim `/newbot` dan ikuti instruksi
3. Simpan **bot token** yang diberikan
4. (Opsional) Set bot name dan description

### 2. Konfigurasi Environment

```bash
cd /home/aseps/MCP
cp .env.example .env
nano .env
```

Isi file terpusat `.env`:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ALLOWED_USERS=123456789,987654321  # Optional
TELEGRAM_MODE=polling
```

Catatan:
- `.env` di root workspace adalah source of truth yang direkomendasikan.
- `mcp-unified/integrations/telegram/.env` hanya dipakai bila Anda sengaja mengisolasi runtime Telegram.
- Jika ingin file secret di luar repo, set `MCP_SECRETS_FILE=/absolute/path/to/secrets.env`.

### 3. Jalankan Bot

```bash
# Install dependencies
pip install python-telegram-bot aiohttp

# Jalankan bot
./run.sh

# Atau daemon mode
./run.sh --daemon
```

### 4. Test Bot

1. Buka bot Anda di Telegram
2. Kirim `/start`
3. Kirim pesan teks untuk testing

## 📁 Struktur File

```
integrations/telegram/
├── bot.py                         # Main bot class (modular)
├── run.py                         # Entry point bot utama
├── handlers/                      # Command, message, media handlers
├── services/telegram_context_service.py
├── services/agent_bridge_memory_service.py
├── telegram_tool.py               # MCP tool untuk kirim pesan
├── run.sh                         # Runner script
└── README.md                      # Dokumentasi ini
```

## 🔧 Konfigurasi

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | - | Token dari @BotFather |
| `TELEGRAM_ALLOWED_USERS` | ❌ | - | User ID whitelist (comma-separated) |
| `TELEGRAM_MODE` | ❌ | `polling` | `polling` atau `webhook` |
| `TELEGRAM_WEBHOOK_URL` | ⚠️ | - | Required untuk webhook mode |
| `TELEGRAM_WEBHOOK_PORT` | ❌ | `8443` | Port untuk webhook server |
| `MCP_SERVER_URL` | ❌ | `http://localhost:8000` | URL MCP server untuk bridge agent opsional |

### Mendapatkan User ID

Untuk mendapatkan User ID Anda:
1. Buka [@userinfobot](https://t.me/userinfobot)
2. Kirim pesan apa saja
3. Bot akan reply dengan ID Anda

## 🎯 Mode Operasi

### Polling Mode (Development)

```env
TELEGRAM_MODE=polling
```

- Bot polling Telegram API setiap detik
- Tidak butuh public URL
- Cocok untuk local/WSL

### Webhook Mode (Production)

```env
TELEGRAM_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook
TELEGRAM_WEBHOOK_PORT=8443
```

- Telegram push update ke server Anda
- Lebih real-time dan efisien
- Butuh HTTPS public endpoint

## Arsitektur

- Bot chat utama: fokus ke percakapan Telegram dan korespondensi.
- Conversation context: hanya session lokal bot, tidak mengambil LTM/knowledge agent.
- Agent bridge: tetap bisa dipakai untuk handoff/manual escalation.
- SQL/knowledge bot: bukan bagian dari runtime bot utama. Jika masih dipakai, perlakukan sebagai service terpisah/legacy.

## 🛠️ Telegram Tool (MCP Integration)

Gunakan `telegram` tool dari dalam MCP untuk mengirim notifikasi:

### Python API

```python
from tools.integrations.telegram import telegram_tool

# Kirim pesan
result = await telegram_tool.send_message(
    chat_id="123456789",
    message="Task completed! 🎉",
    parse_mode="HTML"
)

# Kirim foto
result = await telegram_tool.send_photo(
    chat_id="@mychannel",
    photo_path="/path/to/chart.png",
    caption="Daily Report"
)
```

### Via Task

```python
from core.task import Task

task = Task(
    type="telegram",
    payload={
        "action": "send_message",
        "chat_id": "123456789",
        "message": "Hello from MCP!",
        "parse_mode": "Markdown"
    }
)
```

## 📱 Commands

| Command | Description |
|---------|-------------|
| `/start` | Mulai percakapan |
| `/help` | Tampilkan bantuan |
| `/status` | Cek status bot |
| `/reset` | Reset sesi percakapan |
| `/cline` | Forward pesan ke bridge agent |

## 🔒 Keamanan

- **User Whitelist**: Hanya user ID yang terdaftar bisa akses
- **File Size Limit**: Maksimum 20MB untuk upload
- **Input Validation**: Sanitasi semua input user

## 🐛 Troubleshooting

### Bot tidak merespon

```bash
# Cek log
tail -f telegram_bot.log

# Cek status bot
ps aux | grep "python3 run.py"

# Restart bot
kill $(cat telegram_bot.pid)
./run.sh
```

### Module not found

```bash
# Install dependencies
pip install python-telegram-bot aiohttp --break-system-packages
```

### Invalid bot token

Pastikan token di secret source terpusat benar:
```bash
# Test token
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
```

## Catatan

- `bot_server.py` sekarang hanya wrapper kompatibilitas.
- Implementasi legacy diarsipkan di `legacy/bot_server.py`.
- `README_SQL_BOT.md` mendokumentasikan bot SQL terpisah, bukan bot chat utama ini.

## 📚 Referensi

- [python-telegram-bot docs](https://docs.python-telegram-bot.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [MCP Documentation](../../docs/)
