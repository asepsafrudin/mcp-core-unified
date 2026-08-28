# Document AI Service — Generic Multi-PDF Table & Document Extraction Engine

Service untuk mengekstraksi tabel dan data terstruktur dari **berbagai file PDF** (surat tagihan, rekapitulasi, kuitansi, faktur, dll.) menggunakan **Google Cloud Document AI API**, lalu mengekspor hasilnya ke Markdown (`.md`) dan JSON Lines (`.jsonl`).

## 🎯 Fitur

- **Generic parser** — membaca skema tabel apa saja tanpa hardcode nama kolom
- **Flexible page range** — dukung `"all"`, `"4-7"`, `"1,3,5"`, `"1"`
- **Multi-page table merge** — gabungkan baris tabel yang berlanjut di beberapa halaman
- **Data cleansing** — hapus newline, whitespace berlebih, normalisasi karakter
- **Dual-runtime** — jalankan di Google Colab (prototyping) atau MCP server (otomasi)
- **Export fleksibel** — Markdown (`.md`), JSONL (`.jsonl`), atau keduanya (sesuai kebijakan format file output)

## 📁 Struktur

### Source Code (di `core/`)

```
core/mcp-unified/services/documentai/
├── __init__.py              # Export public API
├── config.py                # Konfigurasi GCP (env vars)
├── engine.py                # DocumentAIEngine (API client + generic table parser)
├── pdf_handler.py           # PDF slicer (pypdf) + page range parser
├── text_cleaner.py          # Data cleansing
├── exporter.py              # Export ke Markdown/JSONL
├── tools.py                 # MCP tools (docai_*)
├── requirements.txt         # Dependency
├── README.md                # Dokumentasi ini
└── notebooks/
    └── documentai_prototype.ipynb   # Colab prototyping notebook
```

### Data Output (di `storage/` — sesuai kebijakan isolasi data)

```
storage/raw_documents/
├── input/                           # File PDF sumber (input)
└── processed/
    └── documentai/                  # Hasil ekstraksi Document AI
        ├── Surat BPJS-0726_extracted.md       # Laporan tabel (Markdown)
        └── Surat BPJS-0726_extracted.jsonl    # Data terstruktur (JSON Lines)
```

> **Kebijakan Isolasi Data**: File output (`.md`, `.jsonl`) **WAJIB** disimpan di `storage/`, **DILARANG** di `core/`. Lihat [`docs/00-meta/04-project-conventions.md`](../../docs/00-meta/04-project-conventions.md).

## 🔧 Konfigurasi GCP

Set environment variables:

```bash
export GCP_PROJECT_ID="your-project-id"
export DOCAI_LOCATION="asia-southeast1"      # lokasi processor (us, eu, atau regional)
export DOCAI_PROCESSOR_ID="your-processor-id"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"  # opsional
```

> **Catatan**: Gunakan `DOCAI_LOCATION` (khusus Document AI). `GCP_LOCATION` digunakan service lain dan bisa berbeda. Processor harus bertipe **FORM_PARSER** agar menghasilkan struktur tabel — processor **Document OCR** hanya menghasilkan teks, tidak menghasilkan `page.tables`.

> **Konfigurasi aktual project ini** (`.env.workspace`):
> - `DOCAI_PROCESSOR_ID=b3eea4becb9e5efb` (SIP-DADES-FormParser)
> - `DOCAI_LOCATION=asia-southeast1`
> - `GCP_PROJECT_ID=mcp-gmail-482015`

Atau gunakan `gcloud auth application-default login` untuk ADC (Application Default Credentials).

## ⚙️ Konfigurasi Robust untuk Dokumen OCR Rumit

Engine sudah dilengkapi `ProcessOptions` yang dioptimalkan untuk dokumen rumit (scan, kualitas rendah, banyak bahasa, tabel kompleks).

### Mode Dasar (default — aman untuk semua processor)

| Fitur | Env | Default |
|-------|-----|---------|
| Native PDF parsing (PDF digital) | - | ✅ Aktif |
| Language hints (multi-bahasa) | `DOCAI_LANGUAGE_HINTS` | `id,en` |
| Deteksi header cerdas | - | ✅ Aktif |
| Infer kolom kosong | - | ✅ Aktif (`Kolom N`) |

```bash
# Contoh: tambah bahasa
export DOCAI_LANGUAGE_HINTS="id,en,zh"
```

### Mode Premium (opsional — hanya OCR 2.0+ processors)

> ⚠️ Fitur premium **tidak didukung** oleh FORM_PARSER / OCR 1.0. Aktifkan hanya jika processor Anda bertipe **OCR 2.0** (`PRETRAINED_OCR_V2_TYPE` atau sejenisnya).

| Fitur | Env | Efek |
|-------|-----|------|
| Image quality scores | `DOCAI_PREMIUM_FEATURES=1` | Deteksi kualitas scan |
| Symbol detection | `DOCAI_PREMIUM_FEATURES=1` | Deteksi simbol/spesial |
| Style info (bold/italic) | `DOCAI_PREMIUM_FEATURES=1` | Deteksi header bold |
| Selection mark detection | `DOCAI_PREMIUM_FEATURES=1` | Deteksi centang/checklist |
| Table annotation + bbox | `DOCAI_PREMIUM_FEATURES=1` | Deteksi tabel lebih baik |

```bash
export DOCAI_PREMIUM_FEATURES=1
```

### Menangani Dokumen Tanpa Header Eksplisit

Dokumen rekapitulasi (seperti contoh BPJS) sering **tidak memiliki baris header di dalam tabel** — judul kolom berada di luar deteksi `page.tables`. Untuk kasus ini:
1. **Deteksi header cerdas** sudah mencoba mengidentifikasi baris header terbaik
2. Jika masih kurang akurat, beri **column mapping** manual (post-processing) sesuai kebutuhan domain
3. Kolom kosong otomatis diberi nama generik (`Kolom N`)

## 🚀 Penggunaan

### Runtime A: Google Colab (Prototyping)

1. Buka `notebooks/documentai_prototype.ipynb` di Google Colab
2. Jalankan cell-by-cell:
   - Install dependencies
   - Auth GCP (interactive atau service account)
   - Set konfigurasi GCP
   - Upload modul dari `services/documentai/`
   - Upload PDF yang akan diproses
   - Proses & export
   - Download hasil

### Runtime B: MCP Server (Otomasi)

Service diregistrasi otomatis saat MCP server start (via `core/bootstrap.py`).

**Tools yang tersedia:**

| Tool | Deskripsi |
|------|-----------|
| `docai_extract_tables` | Ekstraksi tabel dari PDF via Document AI |
| `docai_get_processor_info` | Info konfigurasi processor |
| `docai_export_result` | Export ulang hasil ekstraksi (JSON) ke Markdown/JSONL |

**Contoh pemanggilan `docai_extract_tables`:**

```json
{
  "file_path": "/path/to/Surat BPJS-0726.pdf",
  "pages": "4-7",
  "output_format": "both"
}
```

### Runtime C: Python Script (Langsung)

```python
from services.documentai import DocumentAIEngine, export_both

engine = DocumentAIEngine()
tables = engine.extract_tables("storage/raw_documents/input/Surat BPJS-0726.pdf", pages="4-7")

result = export_both(
    tables,
    "storage/raw_documents/processed/documentai/Surat BPJS-0726_extracted",
    source_file="Surat BPJS-0726.pdf",
    page_range="4-7",
)
print(f"Markdown: {result['markdown_path']}")
print(f"JSONL: {result['jsonl_path']}")
```

## 📦 Dependencies

```bash
pip install -r requirements.txt
```

Isi `requirements.txt`:
```
google-cloud-documentai>=2.20.0
google-cloud-storage>=2.10.0
pypdf>=4.0.0
```

> **Catatan**: `openpyxl` dan `pandas` tidak lagi diperlukan karena output sekarang dalam format `.md` + `.jsonl` (menggunakan library bawaan Python: `json`, `datetime`).

## 🛠️ Error Handling

| Error | Penyebab | Solusi |
|-------|----------|--------|
| `ConfigError` | GCP config tidak lengkap | Set `GCP_PROJECT_ID` dan `DOCAI_PROCESSOR_ID` |
| `PDFProcessingError` | File tidak ditemukan / PDF rusak | Periksa path dan validitas file |
| `DocumentAIError` | API call gagal | Periksa kredensial, processor ID, dan koneksi |
| `ExportError` | Export gagal | Periksa izin direktori output |

## 🔄 Alur Kerja

```
Read Input → Slice PDF (if needed) → Call Document AI → Parse Tables → Export Output
```

## 📝 Catatan

- **Dual-runtime**: Engine inti (`engine.py`, `pdf_handler.py`, dll.) murni Python tanpa dependensi Colab — portable ke kedua runtime
- **Isolasi dependency**: `google-cloud-documentai` hanya dimuat saat `register_tools()` dipanggil (pola `try/except ImportError` di bootstrap)
- **Colab gratis cukup**: Tidak butuh GPU lokal karena proses AI ada di cloud
- **Region**: Untuk processor regional (mis. `asia-southeast1`), engine otomatis menggunakan endpoint `{location}-documentai.googleapis.com`
- **Hasil pengujian**: Ekstraksi `Surat BPJS-0726.pdf` halaman 4-7 → 4 tabel (62, 60, 59, 48 baris) → file output `.md` + `.jsonl` di `storage/raw_documents/processed/documentai/`
- **Format output**: Hanya `.md` (Markdown) dan `.jsonl` (JSON Lines) — sesuai kebijakan format file output di `docs/00-meta/04-project-conventions.md`
