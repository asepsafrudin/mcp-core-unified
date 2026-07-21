# Baseline Pengukuran TASK-106 (Registry & Discovery)

**Tanggal:** 2026-07-19
**Tujuan:** Mendokumentasikan kondisi awal (baseline) sebelum refaktorisasi MCP Unified Registry dan Discovery.

## 1. Jumlah Tool Saat Startup
Berdasarkan `bootstrap.py` dan dokumentasi di `AGENT_RULES.md`, saat startup sistem secara statis memuat (*eager loading*) **88+ tools** yang mencakup:
- Scheduler tools
- Google Drive tools
- Google Workspace tools
- WhatsApp tools
- Unified Sync tools
- Knowledge tools
- Semantic Analysis tools
- Blackbox tools
- Monitoring tools
- OCR tools
- SQL tools
- Serta berbagai tool dari *remote discovery* dan *local discovery*.

Proses pemanggilan `setup_registry()` mengeksekusi semua plugin tersebut dan memblokir eksekusi akibat pemanggilan *remote discovery* yang mencoba menghubungi server eksternal, sehingga menunjukkan inefisiensi yang signifikan pada saat inisialisasi.

## 2. Ukuran Response `handle_list_tools()`
Dengan total 88+ tools yang didaftarkan secara penuh (termasuk deskripsi panjang dan *schema* lengkap), estimasi ukuran *payload* dari pemanggilan `handle_list_tools()` adalah:
- Rata-rata 1 tool = ~200 - 300 karakter
- Total 88+ tools = **~20,000 - 25,000 karakter** (atau setara dengan ~5,000 hingga 6,250 token LLM).
Hal ini menyebabkan overhead besar pada klien (terutama LLM dengan *context window* terbatas) karena semua tool diekspos setiap kali klien meminta *list tools*.

## 3. Daftar Skrip `.sh`/`.js` Auto-Discover
Setelah dilakukan pencarian menggunakan perintah `find` di folder *standard locations* (`plugins`, `execution/tools`, `memory`, `intelligence`, `messaging`, `execution`), **tidak ditemukan file `.sh` maupun `.js`** saat ini.
Namun demikian, mekanisme *auto-discover* (`discover_all_standard_locations()`) saat ini masih akan secara otomatis membaca dan mengekspos semua file dengan ekstensi tersebut di masa depan tanpa *manifest*, yang merupakan risiko dan target untuk direfaktorisasi pada subtask 106-C (penerapan *soft cutover* via `.tool.json`).
