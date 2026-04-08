## Namespace: ocr/

Tools untuk ekstraksi teks dan parsing dokumen dari gambar.
## 🛡️ Aturan Global: Isolasi & Indexing
1. **Memory (LTM) & Planning**: WAJIB menggunakan parameter `namespace`. Gunakan nama folder proyek sebagai namespace (contoh: `korespondensi-server`).
2. **Code Intelligence (Serena)**: Gunakan tool `serena_*` untuk pencarian kode yang efisien.
   - Panggil `serena_activate_project` terlebih dahulu untuk target project.
   - Gunakan `serena_get_symbols_overview` sebelum membaca isi file mentah.
   - Fokus pada `serena_find_symbol` untuk memahami definisi fungsi/class.

---

## 🔍 Namespace: serena/ (Code Intelligence)
Gunakan Serena untuk pemahaman kode tingkat tinggi (LSP-based).

| Tool | Deskripsi | Kapan Digunakan |
|------|-----------|-----------------|
| `serena_activate_project` | Aktifkan project untuk indexing | Langkah pertama sebelum mencari kode. |
| `serena_find_symbol` | Cari fungsi, class, atau variabel | Mencari definisi kode secara spesifik. |
| `serena_get_symbols_overview`| Lihat struktur file (high-level) | Memahami isi file tanpa membaca seluruh teks. |
| `serena_search_for_pattern` | Pencarian teks berbasis pattern | Mencari penggunaan pattern di seluruh project. |

---

## 🏗️ Namespace: app_development/
Gunakan `AppDeveloperAgent` untuk delegasi tugas pengembangan aplikasi.

| Tool | Deskripsi | Kapan Digunakan |
|------|-----------|-----------------|
| `run_coding_task` | Submit tugas coding ke OpenHands | Membuat fitur baru, CRUD, atau scaffolding. |
| `get_task_status` | Cek progress/hasil coding | Polling setiap 30-60 detik setelah submit. |
| `cancel_coding_task` | Hentikan tugas berjalan | Jika instruksi salah atau perlu reset. |

---

## 🧠 Namespace: intelligence/ (Planning)
Audit dan perencanaan sebelum eksekusi berat.

| Tool | Deskripsi | Kapan Digunakan |
|------|-----------|-----------------|
| `create_plan` | Buat rencana langkah-demi-langkah | Sebelum mendelegasikan tugas ke agen lain. |
| `save_plan_experience` | Simpan rencana yang sukses ke LTM | Setelah tugas coding atau riset selesai. |

---

## 📊 Namespace: openhands/ (Observability)
Monitoring real-time untuk tugas otonom.

| Resource URI | Deskripsi |
|--------------|-----------|
| `mcp://openhands/task/{task_id}/logs` | Lihat log terminal agen otonom. |
| `mcp://openhands/task/{task_id}/status` | Ambil detail JSON (file yang diubah, dll). |

---

## 🔍 Namespace: ocr/
Ekstraksi teks dan parsing dokumen dari gambar.

| Tool | Deskripsi | Kapan Digunakan |
|------|-----------|-----------------|
| `extract_text` | Ekstraksi teks + bounding box | Butuh koordinat teks mentah. |
| `parse_document` | Parsing dokumen ke Markdown | Dokumen kompleks (tabel, surat resmi). |
