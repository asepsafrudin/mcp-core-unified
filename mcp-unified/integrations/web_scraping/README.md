# 🌐 Web Scraping Knowledge Bridge

Sistem web scraping terintegrasi untuk mengisi knowledge base Agent Legal dengan:
- **Multiple Site Support**: Perplexity.ai, JDIH, News sites, dan generic websites
- **4-Level Validation**: Quality assurance berdasarkan Autonomous Knowledge Update System
- **Autonomous Mode**: Self-healing, gap analysis, dan adaptive scheduling
- **Telegram Integration**: Commands untuk trigger scraping

## 🏗️ Arsitektur

```
mcp-unified/integrations/web_scraping/
├── core/
│   ├── browser_bridge.py          # Playwright automation dengan stealth mode
│   ├── extractors/
│   │   ├── base_extractor.py      # Abstract base class
│   │   ├── perplexity_extractor.py
│   │   ├── jdih_extractor.py
│   │   ├── news_extractor.py
│   │   └── generic_extractor.py   # Fallback
│   └── validators/
│       └── four_level_validator.py # 4-level validation
├── ingestors/
│   └── knowledge_ingestor.py      # Integration dengan AgentKnowledgeBridge
├── handlers/
│   └── telegram_commands.py       # Telegram bot commands
├── autonomous/
│   ├── gap_analyzer.py
│   ├── scheduler.py
│   └── self_healing.py
└── tests/
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install playwright tenacity
playwright install chromium
```

### 2. Basic Usage

```python
import asyncio
from mcp_unified.integrations.web_scraping import WebScrapingIngestor

async def main():
    # Create ingestor
    ingestor = WebScrapingIngestor()
    
    # Initialize
    await ingestor.initialize()
    
    # Scrape single URL
    result = await ingestor.scrape_and_ingest(
        url="https://www.perplexity.ai/search/abc123",
        domain="hukum_perdata",
        tags=["uu_23_2024", "perplexity"]
    )
    
    print(f"Success: {result['success']}")
    print(f"Doc ID: {result.get('doc_id')}")
    
    # Cleanup
    await ingestor.close()

asyncio.run(main())
```

### 3. Batch Scraping

```python
urls = [
    "https://www.perplexity.ai/search/abc123",
    "https://jdih.kemendagri.go.id/peraturan/xyz789",
    "https://news.kompas.com/read/123",
]

results = await ingestor.scrape_batch(
    urls=urls,
    domain="hukum_perdata",
    tags=["batch_scrape"]
)
```

## 📱 Telegram Commands

### `/scrape <URL> [domain] [tags]`
Scrape single URL.

**Contoh:**
```
/scrape https://www.perplexity.ai/search/abc123 hukum_perdata uu,perplexity
/scrape https://jdih.kemendagri.go.id/peraturan/xyz789 regulasi jdih
/scrape https://news.kompas.com/read/123 berita_hukum kompas
```

### `/scrape_batch <URL1> <URL2> ... [domain]`
Scrape multiple URLs.

**Contoh:**
```
/scrape_batch https://url1.com https://url2.com https://url3.com hukum_perdata
```

### `/scrape_help`
Show help message.

### `/scrape_status`
Show system status.

## 🔧 Supported Extractors

### PerplexityExtractor
Extract conversation threads dari Perplexity.ai.

**Features:**
- Q&A extraction
- Source/citation extraction
- Code block handling
- Thread metadata

**URL Patterns:**
- `https://www.perplexity.ai/search/*`
- `https://www.perplexity.ai/collections/*`

### JDIHExtractor
Extract peraturan dari JDIH (Jaringan Dokumentasi dan Informasi Hukum).

**Ranking Kualitas (terbaik ke bawah):**
| Rank | Penyedia | Kualitas | Update Speed |
|------|----------|----------|--------------|
| 1 | Hukumonline.com | ⭐⭐⭐ PDF konsolidasi, searchable, metadata lengkap | Tercepat: 4 jam (pusat), harian (daerah) |
| 2 | peraturan.go.id | ⭐⭐⭐ PDF resmi, status berlaku, relasi peraturan | Cepat: hari-minggu setelah diundangkan |
| 3 | peraturan.bpk.go.id | ⭐⭐⭐ PDF akurat, standar JDIH | Cepat: mudah & akurat untuk publik |
| 4 | jdih.mahkamahagung.go.id | ⭐⭐ Fokus putusan & peraturan, searchable | Relatif cepat: update dokumen terkini |
| 5 | pusatdata.hukumonline.com | ⭐⭐ Lengkap 74k+ dokumen, verifikasi resmi | Harian untuk koleksi besar |

**Features:**
- Metadata extraction (jenis, nomor, tahun, status)
- PDF link detection (searchable PDFs)
- Full text extraction
- Multi-site support dengan quality ranking
- Relasi peraturan detection

**URL Patterns:**
- `https://www.hukumonline.com/*` ⭐ Terbaik
- `https://peraturan.go.id/*` ⭐
- `https://peraturan.bpk.go.id/*` ⭐
- `https://jdih.mahkamahagung.go.id/*`
- `https://pusatdata.hukumonline.com/*`
- `https://jdih.kemendagri.go.id/*`

### NewsExtractor
Extract artikel dari portal berita.

**Supported Sites:**
- Kompas.com
- Detik.com
- CNN Indonesia
- Tribunnews.com
- Liputan6.com
- Dan lainnya...

**Features:**
- Title, content, author extraction
- Date parsing
- Tag extraction
- Site-specific selectors

### GenericExtractor
Fallback extractor untuk website apapun.

**Features:**
- Readability algorithm
- Meta tag extraction
- Content heuristics
- Schema.org parsing

## ✅ 4-Level Validation

Sistem menggunakan 4-level validation dari Autonomous Knowledge Update System:

### Level 1: Basic Validation
- Content length check
- Format validation
- Duplicate detection
- **Weight:** 20%

### Level 2: Semantic Validation
- Coherence check (readability)
- Topic relevance
- Language clarity
- **Weight:** 30%

### Level 3: Accuracy Validation
- Source verification
- Contradiction detection
- Date validation
- **Weight:** 30%

### Level 4: Utility Validation
- Information density
- Structured content detection
- Query coverage analysis
- **Weight:** 20%

**Scoring:**
- Score >= 0.75: ✅ Validated
- Score 0.70-0.75: ⚠️ Store but flag for review
- Score < 0.70: ❌ Reject

## 🤖 Autonomous Mode

### Gap Analyzer
Analyze knowledge gaps untuk autonomous updates.

```python
from mcp_unified.integrations.web_scraping.autonomous import GapAnalyzer

analyzer = GapAnalyzer()
gaps = await analyzer.analyze_gaps(days=7)
```

### Adaptive Scheduler
Schedule scraping tasks dengan dynamic intervals.

```python
from mcp_unified.integrations.web_scraping.autonomous import AdaptiveScheduler

scheduler = AdaptiveScheduler()
task_id = await scheduler.schedule_task(
    url="https://example.com",
    domain="hukum_perdata",
    interval="daily"
)
```

### Self-Healing Manager
Auto-recovery dari failures.

```python
from mcp_unified.integrations.web_scraping.autonomous import SelfHealingManager

healer = SelfHealingManager()
healer.record_failure(url, error)

if healer.should_retry(url):
    delay = healer.get_retry_delay(url)
    await asyncio.sleep(delay)
    # Retry scraping
```

## 🔐 Security & Ethics

- **Stealth Mode**: Rotating user agents, disable automation flags
- **Rate Limiting**: Respect website limits (default 2s delay)
- **Circuit Breaker**: Auto-stop jika terlalu banyak failures
- **Robots.txt**: Respect website rules
- **Ethical Scraping**: Hanya scrape public data

## 📊 Performance

| Metric | Target |
|--------|--------|
| Scraping Success Rate | > 90% |
| Validation Pass Rate | > 85% |
| End-to-End Latency | < 30s per URL |
| Concurrent Tasks | 3 (configurable) |

## 🧪 Testing

```bash
# Run tests
pytest mcp-unified/integrations/web_scraping/tests/

# Test specific extractor
python -m pytest tests/test_extractors.py::TestPerplexityExtractor
```

## 📝 Examples

### Example 1: Scrape Perplexity
```python
from mcp_unified.integrations.web_scraping import WebScrapingIngestor

ingestor = WebScrapingIngestor()
await ingestor.initialize()

result = await ingestor.scrape_and_ingest(
    url="https://www.perplexity.ai/search/jelaskan-uu-23-2024",
    domain="hukum_perdata",
    tags=["uu_23_2024", "perplexity"]
)

print(f"Quality Score: {result['validation_score']:.2f}")
print(f"Doc ID: {result['doc_id']}")

await ingestor.close()
```

### Example 2: Scrape JDIH
```python
result = await ingestor.scrape_and_ingest(
    url="https://jdih.kemendagri.go.id/peraturan/uu-23-2014",
    domain="regulasi",
    tags=["uu_23_2014", "desa", "jdih"]
)

print(f"Jenis: {result['content'].metadata['jenis_peraturan']}")
print(f"Nomor: {result['content'].metadata['nomor']}")
```

### Example 3: Context Manager
```python
async with WebScrapingIngestor() as ingestor:
    result = await ingestor.scrape_and_ingest(
        url="https://example.com",
        domain="hukum_pidana"
    )
    # Auto cleanup
```

## 🔧 Configuration

```python
from mcp_unified.integrations.web_scraping import GenericBrowserBridge, FourLevelValidator

# Custom browser config
browser = GenericBrowserBridge(
    headless=True,
    stealth_mode=True,
    rate_limit_delay=3.0,
    max_retries=5
)

# Custom validator config
validator = FourLevelValidator(
    min_overall_score=0.80,
    store_threshold=0.75,
    min_content_length=200
)

ingestor = WebScrapingIngestor(
    browser_bridge=browser,
    validator=validator,
    namespace="custom_namespace"
)
```

## 🐛 Troubleshooting

### Issue: Website blocks scraper
**Solution:**
- Enable stealth mode (default: True)
- Increase rate limit delay
- Use proxy (future feature)

### Issue: Content extraction empty
**Solution:**
- Check URL accessibility
- Verify extractor support
- Use generic extractor sebagai fallback

### Issue: Low validation scores
**Solution:**
- Check content quality
- Adjust validation thresholds
- Review 4-level validation results

## 📚 Dependencies

- `playwright>=1.40.0` - Browser automation
- `tenacity>=8.2.0` - Retry logic
- `aiogram>=3.0.0` - Telegram integration
- `python-dateutil>=2.8.0` - Date parsing

## 🎯 Roadmap

- [ ] JavaScript rendering untuk SPAs
- [ ] Proxy rotation
- [ ] ML-based content classification
- [ ] Auto-summarization
- [ ] Multi-language support
- [ ] Distributed crawling

## 🤝 Contributing

1. Fork repository
2. Create feature branch
3. Implement changes
4. Add tests
5. Submit PR

## 📄 License

MIT License - See LICENSE file for details.

---

**Built for MCP-Unified Agent Legal** 🏛️