# Knowledge Sharing Module

Modul untuk mengekstrak, memproses, dan berbagi pengetahuan antar agent dalam sistem MCP.

## 🏗️ Arsitektur

```
knowledge/
├── ingestion/          # Pipeline untuk ingest dokumen
│   ├── extractors/     # PDF, DOCX, XLSX extractors
│   ├── chunking/       # Text chunking strategies
│   └── quality/        # Quality scoring
├── sharing/            # Knowledge sharing antar agent
│   ├── namespace_manager.py
│   └── telegram_bridge.py
└── review/             # Review queue (placeholder)
```

## 🚀 Quick Start

### 1. Process File

```python
from knowledge.ingestion import DocumentProcessor

processor = DocumentProcessor()

# Process file
result = await processor.process_file(
    file_path="dokumen.pdf",
    suggested_namespace="shared_legal",
    tags=["regulasi", "2024"]
)

print(result.status)  # "approved" | "pending_review" | "error"
print(result.quality_score)  # 0.0 - 1.0
```

### 2. Namespace Management

```python
from knowledge.sharing import NamespaceManager

ns_manager = NamespaceManager()

# List namespaces
namespaces = await ns_manager.list_namespaces()

# Search across namespaces
results = await ns_manager.search_across_namespaces(
    query="prosedur pengadaan",
    top_k=5
)
```

### 3. Telegram Integration

```python
from knowledge.sharing import TelegramKnowledgeBridge
from knowledge.ingestion import DocumentProcessor
from knowledge.sharing import NamespaceManager

# Initialize
processor = DocumentProcessor()
ns_manager = NamespaceManager()
bridge = TelegramKnowledgeBridge(
    bot=bot,
    document_processor=processor,
    namespace_manager=ns_manager
)

# Register handlers
bridge.register_handlers(dispatcher)
```

## 📋 Commands Telegram

| Command | Deskripsi |
|---------|-----------|
| `/ask <pertanyaan>` | Cari informasi di knowledge base |
| `/namespaces` | List semua shared namespaces |
| `/knowledge_help` | Tampilkan bantuan |
| Upload file | Upload PDF/DOCX/XLSX untuk diproses |

## 📁 Shared Namespaces

| Namespace | Deskripsi |
|-----------|-----------|
| `shared_legal` | Dokumen hukum dan regulasi |
| `shared_admin` | Prosedur administrasi dan SOP |
| `shared_tech` | Dokumentasi teknis |
| `shared_general` | Dokumen umum |

## ⚙️ Quality Threshold

Default quality threshold: **0.7**

- Score ≥ 0.7: Auto-approved
- Score < 0.7: Pending review

## 📦 Dependencies

```bash
# PDF extraction
pip install pymupdf PyPDF2

# DOCX extraction
pip install python-docx

# XLSX extraction
pip install openpyxl pandas

# OCR (optional)
pip install pytesseract paddleocr
```

## 📝 TODO

- [ ] Integrasi dengan RAGEngine actual
- [ ] Persistent review queue (database)
- [ ] Admin dashboard untuk review
- [ ] Role-based access control
- [ ] Knowledge versioning
