# AGENT_RULES.md
# MCP Unified Agent System Operation Rules
# Last Updated: 2026-04-21

---

## 🚀 REPOSITORY MANAGEMENT (HUB PROTOCOL)

✅ **MANDATORY**: Gunakan `./manage_repos.sh` di root Hub (`/home/aseps/MCP/`) untuk sinkronisasi antar repositori.
- **Update Repo**: `./manage_repos.sh pull`
- **Sync All**: `./manage_repos.sh sync`
- **Push Repo**: `./manage_repos.sh push`

> Jangan melakukan git push/pull manual di dalam folder submodule tanpa koordinasi dengan Hub Manager.

---

## 🛡️ ATURAN GLOBAL AGENT

✅ **Rule #1: Namespace Isolasi**
WAJIB menggunakan parameter `namespace` untuk semua operasi Memory (LTM) & Planning.
> Contoh: `namespace="korespondensi-server"` (gunakan nama folder project)
✅ **Rule #3: Token Efficiency (Quantization)**
Jika pengguna menanyakan status memori, distilasi, atau quantization, **WAJIB** langsung menjalankan script pelaporan untuk menghemat token konteks.
> Script: `/home/aseps/MCP/scripts/report_memory_status.py`

✅ **Rule #4: Workspace Hygiene (Clean-up)**
Setiap pembuatan script baru **WAJIB** menggunakan penamaan versi yang konsisten (misal: `_v2`, `_v3`) jika memodifikasi script yang sudah ada. Jangan menghapus script lama secara manual, gunakan `scripts/consolidate_scripts.py` untuk pengarsipan otomatis.

✅ **Rule #5: Periodic Health Audit**
Setiap sesi audit kesehatan (Health Check), agen **WAJIB** menyertakan hasil dari `scripts/fast_track.py serena-audit` untuk mendeteksi redundansi proses.

✅ **Rule #2: Code Intelligence (Serena)**
Gunakan tool `serena_*` untuk pencarian kode yang efisien:
1. Panggil `serena_activate_project` TERLEBIH DAHULU untuk target project
2. Gunakan `serena_get_symbols_overview` SEBELUM membaca isi file mentah
3. Fokus pada `serena_find_symbol` untuk memahami definisi fungsi/class

✅ **Rule #6: WAHA (WhatsApp Gateway) Startup Protocol**
Ketika menerima instruksi/permintaan untuk kesiapan, penyegaran, atau penautan sesi WhatsApp (WAHA):
1. **Audit Sesi**: Selalu periksa status sesi aktif saat ini menggunakan `python3 scripts/waha_manager.py status`.
2. **Fresh Restart**: Jika status sesi adalah `FAILED` atau tidak aktif, lakukan restart bersih via `python3 scripts/waha_manager.py restart` dan tunggu minimal 15 detik agar browser headless Chromium memuat WhatsApp Web.
3. **Dual-Mode Pairing**: Selalu dapatkan Pairing Code instan (`python3 scripts/waha_manager.py pair <phone>`) **DAN** unduh gambar QR aktif (`python3 scripts/waha_manager.py qr`) secara bersamaan untuk kenyamanan user.
4. **Visual & Text Delivery**: Sajikan kode pairing 8-digit secara jelas dengan font tebal/blok dan cantumkan tautan file gambar QR ([waha_qr.png](file:///home/aseps/MCP/waha_qr.png)).
5. **Verifikasi & Hygiene**: Setelah status menjadi `WORKING`, lakukan verifikasi pengiriman pesan tes (`python3 scripts/waha_manager.py send <phone> "..."`) dan **WAJIB** segera menghapus berkas residu `waha_qr.png` (`rm -f waha_qr.png`) untuk menjaga kerapian workspace.

---

## 📦 NAMESPACE REFERENSI

---

### 🔍 Namespace: serena/ (Code Intelligence)
LSP-based code intelligence untuk pemahaman kode tingkat tinggi.

| Tool | Fungsi | Kapan Digunakan |
|------|--------|-----------------|
| `serena_activate_project` | Aktifkan project untuk indexing | Langkah PERTAMA sebelum mencari kode |
| `serena_find_symbol` | Cari fungsi, class, variabel | Mencari definisi kode secara spesifik |
| `serena_get_symbols_overview` | Lihat struktur file (high-level) | Memahami isi file tanpa membaca seluruh teks |
| `serena_search_for_pattern` | Pencarian teks berbasis pattern | Mencari penggunaan pattern di seluruh project |

---

### 🏗️ Namespace: app_development/
Delegasi tugas pengembangan aplikasi ke `AppDeveloperAgent`

| Tool | Fungsi | Kapan Digunakan |
|------|--------|-----------------|
| `run_coding_task` | Submit tugas coding ke OpenHands | **STANDAR UTAMA** untuk fitur baru, CRUD, atau scaffolding |
| `get_task_status` | Cek progress/hasil coding | Polling setiap 30-60 detik setelah submit |
| `cancel_coding_task` | Hentikan tugas berjalan | Jika instruksi salah atau perlu reset |

> 📖 **Standard Operating Procedure**: Lihat [docs/00-meta/03-openhands-work-standard.md](../docs/00-meta/03-openhands-work-standard.md) untuk protokol delegasi lengkap.

---

### 🧠 Namespace: intelligence/ (Planning)
Audit dan perencanaan SEBELUM eksekusi berat.

| Tool | Fungsi | Kapan Digunakan |
|------|--------|-----------------|
| `create_plan` | Buat rencana langkah-demi-langkah | Sebelum mendelegasikan tugas ke agen lain |
| `save_plan_experience` | Simpan rencana yang sukses ke LTM | Setelah tugas coding atau riset selesai |

---

### 📊 Namespace: openhands/ (Observability)
Monitoring real-time untuk tugas otonom.

| Resource URI | Fungsi |
|--------------|--------|
| `mcp://openhands/task/{task_id}/logs` | Lihat log terminal agen otonom |
| `mcp://openhands/task/{task_id}/status` | Ambil detail JSON (file yang diubah, dll) |
| `mcp://openhands/task/env-context` | Lihat snapshot env task aktif |

> 💡 Catatan Akses Database:
> 1. Sebelum asumsi koneksi PostgreSQL, cek `DATABASE_URL` dan variabel `PG_*` runtime
> 2. Jangan berasumsi `localhost` di sandbox sama dengan host machine
> 3. Untuk debug cepat: `docs/06-database/agent-db-debug-checklist.md`
> 4. Format laporan investigasi: `knowledge/knowledge_template.md`

---

### 🔍 Namespace: ocr/
Ekstraksi teks dan parsing dokumen dari gambar.

| Tool | Fungsi | Kapan Digunakan |
|------|--------|-----------------|
| `parse_document` | Parsing dokumen ke Markdown | Dokumen kompleks (tabel, surat resmi) |
| `extract_text` | Ekstraksi teks mentah | Untuk analisis koordinat/detail gambar |

---

### 🌉 Namespace: gemini-bridge/ (External Reasoning)
Gunakan `gemini` (Flash) atau `gemini-pro` CLI untuk tugas penalaran tinggi dan integrasi Vertex AI.

| Strategi | Perintah / Alias | Tujuan |
|----------|------------------|--------|
| **Fast Reasoning** | `gemini` (alias `g`) | Tanya-jawab cepat dengan konteks 88 tools MCP |
| **Deep Research** | `gemini-pro` (alias `gp`) | Analisis kompleks lintas file/database |
| **Multimodal Context** | `gemini --file image.png` | Bertanya tentang gambar/dokumen scan |
| **Vertex AI Mode** | Otomatis via `.env` | Menggunakan infrastruktur Google Cloud yang stabil |
| **Interactive Debug** | `gemini-pro --interactive` | Chat langsung dalam terminal untuk debugging |

---

### 🧠 Namespace: memory/ (Distillation)
Monitoring pipeline memori 3-layer (STM-LTM-Knowledge).

| Komponen | Alat / Lokasi | Tujuan |
|----------|---------------|--------|
| **Quantize Layer 1** | `scripts/quantize_stm_to_ltm.py` | Kompresi semantik STM ke LTM |
| **Quantize Layer 2** | `scripts/abstract_ltm_to_knowledge.py` | Sintesis pola dari LTM ke Knowledge |
| **Status Report** | `scripts/report_memory_status.py` | **MANDATORY** untuk pelaporan status cepat |
| **Knowledge Base** | `docs/00-meta/ontology.json` | Sumber kebenaran terstruktur (Truth) |

> 💡 Protokol Pelaporan:
> 1. Eksekusi `/home/aseps/MCP/scripts/report_memory_status.py`
> 2. Laporkan ringkasan dari output script tersebut (Total LTM, Ontology status, dan Layer 2 Health).

---

### 🚀 Namespace: fast-track/ (Efficiency)
Otomatisasi perintah repetitif dan audit kode berbasis Serena.

| Shortcut | Perintah | Kegunaan |
|----------|----------|----------|
| `scripts/fast_track.py` | `./scripts/fast_track.py <keyword>` | **MANDATORY** untuk tugas rutin (db-sync, health, status) |
| `serena-audit` | via `fast_track.py` | Audit efisiensi proses dan identifikasi bottleneck |
| `audit-tools` | via `fast_track.py` | Analisis statistik frekuensi penggunaan tool |

> 💡 Protokol Efisiensi:
> 1. Gunakan `fast_track.py --list` untuk melihat daftar shortcut yang tersedia.
> 2. Panggil `serena-audit` secara berkala untuk membersihkan script residu dan mengoptimalkan pipeline.