# 🔔 Opsi Trigger untuk Cline Bridge

Berbagai cara agar Cline (Anda) tahu ada pesan baru dari Telegram.

## Opsi 1: Polling (Paling Simpel)

Cline secara berkala mengecek file `telegram_messages.json`.

### Menggunakan Script Polling

```bash
# Buat script polling
while true; do
    cd /home/aseps/MCP/mcp-unified/integrations/telegram
    python3 cline_reader.py
    sleep 60  # Cek setiap 60 detik
done
```

### Menggunakan Cron (Linux)

```bash
# Edit crontab
crontab -e

# Tambahkan (cek setiap 5 menit)
*/5 * * * * cd /home/aseps/MCP/mcp-unified/integrations/telegram && python3 cline_reader.py --check && echo "Ada pesan baru dari Telegram!" >> /tmp/telegram_notify.log
```

---

## Opsi 2: File Watcher (Realtime)

Deteksi perubahan file secara realtime.

### Script watcher.py

```python
#!/usr/bin/env python3
"""File watcher untuk telegram_messages.json"""

import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class TelegramHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('telegram_messages.json'):
            print("📨 File telegram_messages.json berubah!")
            os.system('python3 cline_reader.py')

if __name__ == "__main__":
    path = "/home/aseps/MCP/mcp-unified/integrations/telegram"
    event_handler = TelegramHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

**Install watchdog:**
```bash
pip3 install watchdog
```

**Jalankan:**
```bash
python3 watcher.py
```

---

## Opsi 3: VS Code Task (Recommended)

Task di VS Code yang berjalan di background.

### .vscode/tasks.json

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Telegram Watcher",
            "type": "shell",
            "command": "while true; do cd ${workspaceFolder}/mcp-unified/integrations/telegram && python3 cline_reader.py; sleep 30; done",
            "problemMatcher": [],
            "isBackground": true,
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": false,
                "panel": "shared"
            }
        }
    ]
}
```

**Jalankan di VS Code:**
- `Ctrl+Shift+P` → "Tasks: Run Task" → "Telegram Watcher"

---

## Opsi 4: Systemd Service (Auto-start)

Service Linux yang berjalan otomatis.

### /etc/systemd/system/telegram-watcher.service

```ini
[Unit]
Description=Telegram Message Watcher for Cline
After=network.target

[Service]
Type=simple
User=aseps
WorkingDirectory=/home/aseps/MCP/mcp-unified/integrations/telegram
ExecStart=/usr/bin/python3 /home/aseps/MCP/mcp-unified/integrations/telegram/cline_reader.py
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

**Aktifkan:**
```bash
sudo systemctl enable telegram-watcher
sudo systemctl start telegram-watcher
```

---

## Opsi 5: Notifikasi Desktop

Notifikasi popup saat ada pesan baru.

```python
#!/usr/bin/env python3
import subprocess
import time
from file_storage import storage

def notify(title, message):
    subprocess.run(['notify-send', title, message])

last_count = 0
while True:
    messages = storage.get_pending_messages()
    if len(messages) > last_count:
        notify("📨 Pesan Telegram Baru", f"Ada {len(messages)} pesan menunggu respon")
        last_count = len(messages)
    time.sleep(30)
```

---

## Opsi 6: Webhook (Advanced)

Bot mengirim HTTP request ke endpoint lokal.

### Modifikasi bot_server.py

```python
async def cmd_cline(self, update, context):
    # ... simpan pesan ...
    
    # Trigger webhook ke Cline
    import aiohttp
    async with aiohttp.ClientSession() as session:
        await session.post('http://localhost:5000/telegram-webhook', 
                          json={'message': message_text})
```

### Webhook server di Cline

```python
from flask import Flask, request
app = Flask(__name__)

@app.route('/telegram-webhook', methods=['POST'])
def webhook():
    data = request.json
    print(f"📨 Pesan baru: {data['message']}")
    # Tampilkan notifikasi atau masukkan ke queue
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(port=5000)
```

---

## Rekomendasi

| Opsi | Kelebihan | Kekurangan | Use Case |
|------|-----------|------------|----------|
| **1. Polling** | Simpel, no deps | Delay 30-60s | Development |
| **2. File Watcher** | Realtime | Perlu install watchdog | Production |
| **3. VS Code Task** | Integrated | Hanya saat VS Code aktif | Development |
| **4. Systemd** | Auto-start, reliable | Setup lebih kompleks | Production |
| **5. Notifikasi** | Visual alert | Perlu desktop env | Desktop user |
| **6. Webhook** | Instant | Setup kompleks | Advanced |

## Setup Cepat (Opsi 1 - Paling Simpel)

```bash
# Jalankan di terminal terpisah
cd /home/aseps/MCP/mcp-unified/integrations/telegram
watch -n 30 python3 cline_reader.py
```

Atau buat alias di `.bashrc`:

```bash
alias telegram-watch='cd /home/aseps/MCP/mcp-unified/integrations/telegram && watch -n 30 python3 cline_reader.py'
```

---

## Flow Lengkap dengan Trigger

```
1. User kirim /cline <pesan>
        ↓
2. Bot simpan ke telegram_messages.json
        ↓
3. TRIGGER aktif (polling/watcher/webhook)
        ↓
4. Cline melihat notifikasi/pesan
        ↓
5. Cline masuk Plan Mode (opsional)
        ↓
6. Cline kirim respon ke user
        ↓
7. Cline tandai sebagai responded
```

**Silakan pilih opsi yang paling sesuai dengan workflow Anda!**
