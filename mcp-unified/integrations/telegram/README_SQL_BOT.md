# 🤖 SQL Bot - Telegram Bot untuk Operasi Database

Status:
- Service ini diperlakukan sebagai bot terpisah/legacy.
- Bukan bagian dari runtime bot chat Telegram utama.
- Gunakan hanya jika memang ingin menjalankan antarmuka SQL yang dedicated.

Bot Telegram yang difokuskan khusus untuk operasi SQL database PostgreSQL. Bot ini dapat menerima pertanyaan dalam bahasa natural dan mengkonversinya ke SQL query, serta mendukung eksekusi SQL manual.

## ✨ Fitur Utama

### 1. 🔍 Text-to-SQL (Natural Language Query)
Konversi pertanyaan bahasa Indonesia/Inggris ke SQL query secara otomatis.

**Contoh:**
```
/query berapa dokumen PUU 2026?
/query list task yang pending
/query dokumen dengan confidence score tertinggi
```

### 2. 📊 SQL Query Manual
Eksekusi SQL query langsung ke database.

**Contoh:**
```
/sql SELECT * FROM vision_results LIMIT 5
/sql SELECT COUNT(*), namespace FROM knowledge_documents GROUP BY namespace
/sql SELECT * FROM tasks WHERE status = 'pending'
```

### 3. 📑 Database Introspection
- `/tables` - Lihat daftar semua tabel
- `/schema <nama_tabel>` - Lihat struktur kolom tabel

### 4. 📈 Status Monitoring
- `/status` - Cek status koneksi database dan statistik

## 🚀 Cara Menjalankan

### Prerequisites
1. Python 3.8+
2. PostgreSQL running
3. Telegram Bot Token
4. AI Provider API Key (Groq atau Gemini)

### Setup Environment

```bash
# Edit centralized secret file
cd /home/aseps/MCP
nano .env
```

**Konfigurasi centralized `.env`:**
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_MODE=polling

# AI Provider (pilih salah satu)
AI_PROVIDER=groq
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.3-70b-versatile

# Atau
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-1.5-flash

# PostgreSQL
PG_HOST=localhost
PG_PORT=5433
PG_DATABASE=mcp_knowledge
PG_USER=mcp_user
PG_PASSWORD=your_password

# User Access (opsional - kosongkan untuk allow all)
ALLOWED_USERS=123456789,987654321
```

Catatan:
- Root `/home/aseps/MCP/.env` adalah source of truth yang direkomendasikan.
- File lokal `mcp-unified/integrations/telegram/.env` sekarang hanya alias kompatibilitas ke root.

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Bot

```bash
# Cara 1: Direct run
python legacy/bot_server_sql_focused.py

# Cara 2: Using run script
./run_sql_bot.sh

# Cara 3: Production dengan nohup
nohup python legacy/bot_server_sql_focused.py > sql_bot.log 2>&1 &
echo $! > sql_bot.pid
```

## 📋 Command Reference

| Command | Deskripsi | Contoh |
|---------|-----------|--------|
| `/start` | Menu utama dan welcome | `/start` |
| `/help` | Panduan penggunaan | `/help` |
| `/status` | Status database | `/status` |
| `/tables` | List semua tabel | `/tables` |
| `/schema` | Struktur tabel | `/schema vision_results` |
| `/sql` | SQL manual | `/sql SELECT * FROM tasks` |
| `/query` | Natural language | `/query berapa dokumen?` |

## 🗄️ Skema Database

### Tabel Utama

#### 1. `vision_results` - Hasil OCR
```sql
SELECT * FROM vision_results WHERE file_name ILIKE '%PUU%2026%';
SELECT COUNT(*), document_type FROM vision_results GROUP BY document_type;
SELECT * FROM vision_results WHERE confidence_score > 0.9;
```

#### 2. `knowledge_documents` - Knowledge Base
```sql
SELECT namespace, COUNT(*) FROM knowledge_documents GROUP BY namespace;
SELECT * FROM knowledge_documents WHERE metadata->>'source_file' ILIKE '%perpres%';
```

#### 3. `tasks` - Manajemen Task
```sql
SELECT * FROM tasks WHERE status = 'pending' ORDER BY priority DESC;
SELECT * FROM tasks WHERE created_at >= CURRENT_DATE - INTERVAL '7 days';
```

#### 4. `telegram_messages` - Log Pesan
```sql
SELECT username, COUNT(*) FROM telegram_messages GROUP BY username;
SELECT * FROM telegram_messages WHERE DATE(created_at) = CURRENT_DATE;
```

#### 5. `agent_memories` - Long Term Memory
```sql
SELECT * FROM agent_memories WHERE importance > 0.8 ORDER BY last_accessed DESC;
```

## 🔒 Keamanan

### Validasi SQL
- ✅ Hanya query `SELECT` yang diizinkan
- 🚫 Diblokir: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `CREATE`
- 🚫 Tidak ada UNION-based injection
- 🚫 Comment injection diblokir

### Best Practices
1. Gunakan parameterized queries di backend
2. User authorization dengan ALLOWED_USERS
3. Rate limiting built-in
4. Query result limited to 50 rows max

## 📝 Contoh Penggunaan

### Contoh 1: Query Dokumen PUU
```
User: /query berapa total dokumen PUU tahun 2026?

Bot: 
📊 Hasil Query

❓ Pertanyaan: berapa total dokumen PUU tahun 2026?
💡 Penjelasan: Menghitung jumlah dokumen PUU tahun 2026

```sql
SELECT COUNT(*) FROM vision_results WHERE file_name ILIKE '%PUU%2026%'
```

📋 1 baris ditemukan

*count*
—
25
```

### Contoh 2: SQL Manual
```
User: /sql SELECT file_name, confidence_score FROM vision_results 
      WHERE document_type = 'pdf' ORDER BY confidence_score DESC LIMIT 5

Bot:
📊 Hasil Query

`file_name | confidence_score`
`——————————————————————————————`
`0161-UND-PUU-2026.pdf | 0.98`
`0165-UND-PRC-PUU-2026.pdf | 0.97`
`0168-UND-PRC-PUU-2026.pdf | 0.95`
...

📋 Total: 5 baris
```

### Contoh 3: Lihat Schema
```
User: /schema vision_results

Bot:
🔎 Struktur Tabel: vision_results

| Kolom | Tipe | Nullable | Default |
|-------|------|----------|---------|
| id | integer | ✗ | - |
| file_path | text | ✓ | - |
| file_name | text | ✓ | - |
| document_type | text | ✓ | - |
| extracted_text | text | ✓ | - |
| confidence_score | double | ✓ | - |
| processing_status | varchar | ✓ | - |
| created_at | timestamp | ✓ | - |

_Total: 8 kolom_
```

## 🐛 Troubleshooting

### Bot tidak merespons
```bash
# Cek log
tail -f sql_bot.log

# Cek process
ps aux | grep bot_server_sql_focused

# Restart bot
pkill -f bot_server_sql_focused
python legacy/bot_server_sql_focused.py
```

### Database tidak terhubung
```bash
# Test PostgreSQL connection
psql -h localhost -p 5433 -U mcp_user -d mcp_knowledge

# Cek service status
sudo systemctl status postgresql
```

### AI tidak merespons
- Pastikan API key valid
- Cek quota/limits di dashboard provider
- Ganti provider di .env (groq/gemini)

## 📁 Struktur File

```
telegram/
├── legacy/bot_server_sql_focused.py  # Main bot legacy (SQL-focused)
├── core/
│   ├── config.py              # Configuration
│   └── ai_providers.py        # AI integrations
├── services/
│   ├── knowledge_service.py   # Database operations
│   └── text_to_sql_service.py # Natural language to SQL
├── .env                       # Environment variables
└── README_SQL_BOT.md         # This file
```

## 🤝 Tips Penggunaan

1. **Gunakan Bahasa Natural**: Bot mengerti Bahasa Indonesia dan Inggris
2. **Spesifik**: "dokumen PUU 2026" lebih baik dari "dokumen"
3. **Filter**: Gunakan filter spesifik untuk hasil lebih cepat
4. **Preview**: Untuk data besar, tambahkan LIMIT di query manual
5. **Schema**: Gunakan `/tables` dan `/schema` untuk eksplorasi

## 📞 Support

Jika ada masalah atau pertanyaan:
1. Cek log di `sql_bot.log`
2. Gunakan `/status` untuk cek koneksi
3. Hubungi administrator sistem

---

*SQL Bot - Making database queries as easy as asking a question* 🤖📊
