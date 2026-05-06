# Dokumentasi Gemini CLI 2.0 (gemini-pro)

Versi modern dari Gemini CLI yang terintegrasi penuh dengan ekosistem **Model Context Protocol (MCP)** dan dioptimalkan untuk performa tinggi menggunakan SDK `google-genai`.

## Fitur Utama
- **Automatic Function Calling**: Gemini secara otomatis mendeteksi dan menggunakan tools yang tersedia di server MCP (WhatsApp, Google Drive, SQL, dll).
- **Streaming & Real-time**: Output instan untuk pengalaman interaktif yang lebih baik.
- **Dukungan Multi-modal**: Mengirimkan file (gambar/kode) langsung ke Gemini.
- **Mode Interaktif (REPL)**: Chat langsung dengan Gemini dalam terminal.
- **Deep Context**: Terkoneksi ke database LTM (Long Term Memory) dan knowledge base proyek Anda.

## Instalasi & Setup
Perintah `gemini-pro` sudah terinstal di jalur binary lokal Anda.

```bash
# Memberikan izin eksekusi (jika belum)
chmod +x ~/.local/bin/gemini-pro
```

Pastikan variabel `GEMINI_API_KEY` tersedia di file `/home/aseps/MCP/.env`.

## Panduan Penggunaan

### 1. Pertanyaan Cepat
```bash
gemini-pro "Tolong rangkum struktur database MCP kita"
```

### 2. Mode Interaktif (Chat)
```bash
gemini-pro --interactive
```

### 3. Menggunakan File sebagai Konteks
```bash
gemini-pro "Apa yang dilakukan fungsi ini?" --file ./path/to/script.py
```

### 4. Menggunakan Tool Secara Otomatis
Contoh: Gemini akan mendeteksi tool WhatsApp dan mengirim pesan secara otomatis jika diminta.
```bash
gemini-pro "Kirim pesan ke Asep via WhatsApp bilang saya akan telat"
```

## Integrasi IDE Agent (Cursor / VS Code)

### Cursor
1. Buka **Settings** -> **Models**.
2. Pilih model `gemini-2.0-flash`.
3. Tambahkan `gemini-pro` sebagai tool eksternal atau gunakan melalui terminal terintegrasi untuk debugging cepat.

### VS Code (menggunakan MCP)
Agen IDE Anda (seperti Roo Code atau Cline) dapat langsung dihubungkan ke `mcp_server.py`. Tambahkan konfigurasi berikut pada pengaturan MCP Anda:

```json
{
  "mcpServers": {
    "mcp-unified": {
      "command": "python3",
      "args": ["/home/aseps/MCP/mcp-unified/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/home/aseps/MCP/mcp-unified"
      }
    }
  }
}
```

## Troubleshooting
Jika terjadi error JSON-RPC, pastikan tidak ada `print()` tambahan di server MCP yang mencemari `stdout`. Semua log harus diarahkan ke `stderr`.

---
*Dokumentasi ini dibuat otomatis oleh Antigravity pada 2026-04-13.*
