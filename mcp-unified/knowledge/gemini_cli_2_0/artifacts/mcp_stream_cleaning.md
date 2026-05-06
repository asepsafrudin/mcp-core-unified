# MCP Stream Hardening & Cleaning

## Masalah
Pada koneksi MCP berbasis *stdio*, server (yang seringkali menggunakan library pihak ketiga) sering mengeluarkan pesan log, peringatan, atau info ke `stdout`. Karena `stdout` adalah jalur suci untuk pesan JSON-RPC, adanya "noise" berupa teks non-JSON (atau JSON log yang bukan standar RPC) akan merusak parser klien dan memutuskan koneksi.

## Solusi: Robust Stream Cleaner
Kami mengimplementasikan wrapper Python (`mcp_server_clean.py`) yang membungkus server utama.

### Mekanisme Kerja
1.  **Dual-Thread Pipe**: Menggunakan dua thread terpisah untuk memproses `stdout` dan `stderr` dari proses server secara asinkron.
2.  **Strict Pattern Matching**: Hanya baris yang mengandung substring `"jsonrpc":"2.0"` (dengan atau tanpa spasi) yang diizinkan untuk dikirim ke `stdout` fisik.
3.  **Automatic Redirection**: Semua output lain yang tidak lolos filter (termasuk JSON logs dari structlog) otomatis dialihkan ke `stderr`.
4.  **Unbuffered Processing**: Menggunakan `bufsize=0` pada subprocess untuk memastikan latensi minimal.

### Snippet Implementasi Utama
```python
if '"jsonrpc":"2.0"' in decoded_line or '"jsonrpc": "2.0"' in decoded_line:
    out_stream.write(line)
    out_stream.flush()
else:
    sys.stderr.buffer.write(line)
    sys.stderr.buffer.flush()
```

## Keuntungan
- **Protokol Stabil**: Klien MCP tidak akan pernah menerima data sampah.
- **Visibilitas Tetap Terjaga**: Developer tetap bisa melihat log server di terminal karena semua noise dialihkan ke `stderr`.
- **Transparan**: Klien (IDE Agent) tidak perlu tahu adanya proses pembersihan di balik layar.
