# 📱 Cline Bridge - Panduan Penggunaan

## Alur Kerja Simpel (Versi Terbaru)

```
User Telegram → /cline <pesan> → Agent Bridge Memory → Cline Baca → Plan Mode → Respon ke User
```

## Cara Menggunakan

### 1. User Kirim Pesan di Telegram
```
/cline Tolong buatkan script Python untuk scraping data
```

### 2. Cline (Agent) Membaca Pesan

**Opsi A: Gunakan Script Reader**
```bash
cd /home/aseps/MCP/mcp-unified/integrations/telegram
python3 cline_reader.py
```

Output:
```
======================================================================
📨 PESAN BARU DARI TELEGRAM
======================================================================

[1] Dari: Asep (@asepsafrudin)
    Waktu: 2026-03-02T09:10:00
    Pesan: Tolong buatkan script Python untuk scraping data
    Key: telegram_cline_123456_20260302_091000
----------------------------------------------------------------------

💡 Total: 1 pesan menunggu respon
```

**Opsi B: MCP Memory Search**
```
Search MCP memory dengan query: "telegram_bridge_to_cline pending"
```

### 3. Cline Masuk Plan Mode
Setelah membaca pesan, Cline otomatis masuk **PLAN MODE** untuk:
- Analisis request user
- Buat rencana penyelesaian
- Presentasikan plan ke user (via Telegram)

### 4. Cline Kirim Respon

**Cara Kirim Balasan:**
```bash
cd /home/aseps/MCP/mcp-unified/integrations/telegram
python3 cline_bridge.py
```

Atau gunakan MCP tool untuk mengirim pesan langsung.

## Perbedaan Command

| Command | Fungsi | Output |
|---------|--------|--------|
| `Pesan biasa` | Chat dengan AI Groq | AI merespons langsung |
| `/cline <pesan>` | Kirim ke Cline Agent | Cline baca & proses manual |

## File Penting

| File | Fungsi |
|------|--------|
| `run.py` | Entry point bot Telegram utama |
| `cline_reader.py` | Script untuk Cline membaca pesan |
| `cline_bridge.py` | Script untuk Cline kirim balasan |
| `CLINE_BRIDGE_GUIDE.md` | Dokumentasi ini |

## Integrasi dengan VS Code

Untuk notifikasi otomatis di VS Code, Anda bisa:

1. **Buat Task di VS Code** (`.vscode/tasks.json`):
```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Check Telegram Messages",
            "type": "shell",
            "command": "cd /home/aseps/MCP/mcp-unified/integrations/telegram && python3 cline_reader.py",
            "problemMatcher": []
        }
    ]
}
```

2. **Jalankan secara berkala** dengan cron atau scheduler.

## Troubleshooting

**Pesan tidak muncul di reader:**
- Cek apakah MCP server berjalan
- Cek log bot: `tail -f telegram_bot.log`
- Pastikan `/cline` command berhasil (lihat respon di Telegram)

**Reader tidak bisa connect:**
- Pastikan `shared.mcp_client` tersedia
- Cek path Python: `sys.path` harus mencakup direktori MCP

## Tips

- Gunakan `/cline` untuk request yang kompleks atau butuh human judgment
- Gunakan pesan biasa untuk chat cepat dengan AI
- Cline akan melihat notifikasi "📨 PESAN BARU DARI TELEGRAM" saat ada pesan masuk

Catatan arsitektur:
- Chat Telegram biasa tidak lagi memakai memory agent sebagai konteks default.
- Hanya command bridge seperti `/cline` yang sengaja masuk ke domain agent/MCP.
