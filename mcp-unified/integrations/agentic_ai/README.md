# 🤖 Agentic AI Extractor System

**Modular Web Scraping System untuk Legal Content**

Sistem extractor modular dengan auto-discovery, ML-based selection, dan knowledge bridge integration.

---

## 📚 Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Extractors](#extractors)
- [Architecture](#architecture)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Testing](#testing)

---

## 🚀 Quick Start

```python
from extractors import HukumonlineExtractor
from knowledge_bridge_integration import ExtractorKnowledgeBridge
from playwright.async_api import async_playwright

async def main():
    # 1. Create extractor
    extractor = HukumonlineExtractor()
    
    # 2. Extract data
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://www.hukumonline.com/berita")
        
        results = await extractor.extract(page)
        results = await extractor.post_process(results)
        
        print(f"Extracted: {len(results)} items")
    
    # 3. Save to knowledge base
    kb = ExtractorKnowledgeBridge()
    summary = await kb.save_extraction_results(
        results=results,
        source="hukumonline",
        url="https://www.hukumonline.com/berita"
    )
    
    print(f"Saved: {summary['saved']} items")

# Run
import asyncio
asyncio.run(main())
```

---

## ✨ Features

### 1. **Auto-Discovery** 🔍
```python
from extractor_discovery import discover_extractors

# Auto-scan folder extractors/
extractors = discover_extractors()
# Returns: [HukumonlineExtractor, JDIHExtractor, ...]
```

### 2. **Extractor Chain** ⛓️
```python
from extractor_chain import ExtractorChain

# Create chain dengan multiple extractors
chain = ExtractorChain([extractor1, extractor2, extractor3])

# Sequential: Stop at first good result
result = await chain.extract_sequential(page, min_quality_score=0.6)

# Parallel: Run all, merge results
result = await chain.extract_parallel(page, merge_strategy="best")
```

### 3. **ML-Based Selection** 🤖
```python
from extractor_chain import MLExtractorSelector

# AI pilih extractor terbaik berdasarkan historical performance
selector = MLExtractorSelector(extractors)
extractor = selector.select_extractor("https://example.com")

# Update performance
selector.update_performance(extractor.name, score=0.85)
```

### 4. **Knowledge Bridge Integration** 🔌
```python
from knowledge_bridge_integration import save_extraction_results

# Auto-save ke database
summary = await save_extraction_results(
    results=results,
    source="kemenkeu",
    url="https://jdih.kemenkeu.go.id"
)
```

---

## 🏗️ Extractors

### **Available Extractors (11)**

| Extractor | Website | Type | Status |
|-----------|---------|------|--------|
| **HukumonlineExtractor** | hukumonline.com | News | ✅ Ready |
| **DetikExtractor** | detik.com | News | ✅ Ready |
| **JDIHExtractor** | jdihn.go.id | Regulations | ✅ Ready |
| **PeraturanBPKExtractor** | peraturan.bpk.go.id | Regulations | ✅ Ready |
| **KemenkeuExtractor** | jdih.kemenkeu.go.id | Regulations | ✅ Ready |
| **SetnegExtractor** | jdih.setneg.go.id | Regulations | ✅ Ready |
| **KominfoExtractor** | kominfo.go.id | Regulations | ✅ Ready |
| **KemenkumhamExtractor** | hukum.kemenkumham.go.id | Regulations | ✅ Ready |
| **KemenpanExtractor** | kemenpan.go.id | Regulations | ✅ Ready |
| **OJKExtractor** | ojk.go.id | Regulations | ✅ Ready |
| **GenericExtractor** | * | Fallback | ✅ Ready |

### **Creating New Extractor**

```python
from extractors.base_extractor import BaseExtractor, ExtractionConfig

class MyExtractor(BaseExtractor):
    @property
    def name(self) -> str:
        return "myextractor"
    
    @property
    def url_patterns(self) -> List[str]:
        return ["mywebsite.com"]
    
    async def extract(self, page) -> List[Dict]:
        # Your extraction logic
        data = await page.evaluate("""
            () => {
                // JavaScript extraction
                return results;
            }
        """)
        return data
    
    async def post_process(self, items):
        # Clean and filter
        return [item for item in items if item.get("title")]
```

---

## 🏛️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTRACTOR SYSTEM                         │
├─────────────────────────────────────────────────────────────┤
│  INPUT                                                      │
│  └── URL → Registry.get_extractor_for_url()                 │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  REGISTRY (Plugin Manager)                                  │
│  ├── Auto-Discovery                                         │
│  ├── URL Pattern Matching                                   │
│  └── Extractor Chain                                        │
├─────────────────────────────────────────────────────────────┤
│  SELECTION                                                  │
│  ├── ML-Based (Epsilon-Greedy)                             │
│  └── Quality Scoring                                        │
├─────────────────────────────────────────────────────────────┤
│  EXTRACTION                                                 │
│  ├── Pre-process (scroll, wait)                             │
│  ├── Extract (JavaScript injection)                         │
│  └── Post-process (filter, dedup)                           │
├─────────────────────────────────────────────────────────────┤
│  KNOWLEDGE BRIDGE                                           │
│  ├── Auto-save to Database                                  │
│  ├── Categorize by Source                                   │
│  └── Search Integration                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 📖 Usage

### **Basic Usage**

```python
from extractors import HukumonlineExtractor
from playwright.async_api import async_playwright

async def extract():
    extractor = HukumonlineExtractor()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto("https://www.hukumonline.com/berita")
        await extractor.pre_process(page)
        
        results = await extractor.extract(page)
        results = await extractor.post_process(results)
        
        return results
```

### **With Knowledge Bridge**

```python
from knowledge_bridge_integration import ExtractorKnowledgeBridge

async def extract_and_save():
    # Extract
    results = await extract()
    
    # Save to knowledge base
    kb = ExtractorKnowledgeBridge()
    summary = await kb.save_extraction_results(
        results=results,
        source="hukumonline",
        url="https://www.hukumonline.com/berita",
        namespace="legal_regulations"
    )
    
    print(f"Saved: {summary['saved']}, Skipped: {summary['skipped']}")
```

### **Using Registry**

```python
from extractor_registry import get_registry

# Get registry (auto-discovers all extractors)
registry = get_registry()

# Find extractor for URL
extractor = registry.get_extractor_for_url("https://www.hukumonline.com/berita")
# Returns: HukumonlineExtractor

# List all extractors
for ext in registry.list_extractors():
    print(f"{ext['name']}: {ext['description']}")
```

### **Using Chain**

```python
from extractor_chain import ExtractorChain
from extractors import HukumonlineExtractor, GenericExtractor

# Create chain
chain = ExtractorChain([
    HukumonlineExtractor(),
    GenericExtractor()
])

# Extract dengan chain
result = await chain.extract_sequential(page, min_quality_score=0.6)
# atau
result = await chain.extract_parallel(page, merge_strategy="best")
```

### **ML-Based Selection**

```python
from extractor_chain import MLExtractorSelector
from extractor_registry import get_registry

# Get all extractors
registry = get_registry()
extractors = [registry.get_extractor(name) for name in registry.get_stats()['extractor_names']]

# Create ML selector
selector = MLExtractorSelector(extractors)

# Select best extractor for URL
extractor = selector.select_extractor("https://example.com")

# After extraction, update performance
selector.update_performance(extractor.name, score=0.85)

# Get stats
stats = selector.get_stats()
# {"hukumonline": {"avg_score": 0.82, "attempts": 10}}
```

---

## 📚 API Reference

### **BaseExtractor**

Abstract base class untuk semua extractors.

```python
class BaseExtractor(ABC):
    @property
    @abstractmethod
    def name(self) -> str
    
    @property
    @abstractmethod
    def url_patterns(self) -> List[str]
    
    @abstractmethod
    async def extract(self, page) -> List[Dict]
    
    async def pre_process(self, page)
    async def post_process(self, items) -> List[Dict]
    def can_handle(self, url: str) -> bool
    def validate_item(self, item: Dict) -> bool
```

### **ExtractorRegistry**

Plugin manager untuk extractors.

```python
class ExtractorRegistry:
    def register(self, extractor_class: Type[BaseExtractor])
    def get_extractor(self, name: str) -> Optional[BaseExtractor]
    def get_extractor_for_url(self, url: str) -> Optional[BaseExtractor]
    def list_extractors(self) -> List[Dict]
    def get_stats(self) -> Dict
```

### **ExtractorKnowledgeBridge**

Integration dengan knowledge base.

```python
class ExtractorKnowledgeBridge:
    async def save_extraction_results(
        self,
        results: List[Dict],
        source: str,
        url: str,
        namespace: str = "legal_regulations"
    ) -> Dict[str, Any]
    
    async def search_saved_results(
        self,
        query: str,
        namespace: str = "legal_regulations",
        top_k: int = 5
    ) -> List[Dict]
    
    async def get_stats(self, namespace: str = "legal_regulations") -> Dict
```

---

## 🧪 Testing

### **Run Tests**

```bash
cd /home/aseps/MCP
python3 test_extractor_with_knowledge_bridge.py
```

### **Test Coverage**

- ✅ Extractor extraction
- ✅ Knowledge Bridge integration
- ✅ Registry auto-discovery
- ✅ URL pattern matching
- ✅ Chain execution
- ✅ Quality scoring

---

## 🔧 Configuration

### **ExtractionConfig**

```python
from extractors.base_extractor import ExtractionConfig

config = ExtractionConfig(
    timeout=45,              # Request timeout
    wait_for="domcontentloaded",  # Wait condition
    scroll_count=3,          # Number of scrolls
    js_render_wait=3,        # Wait for JS render
    min_title_length=5,      # Minimum title length
    required_fields=["title"],      # Required fields
    optional_fields=["content", "url", "date"]  # Optional fields
)
```

---

## 📈 Performance

### **Quality Scoring Formula**

```
Score = (Item Count × 0.25) +
        (Field Completeness × 0.35) +
        (Title Quality × 0.25) +
        (URL Presence × 0.15)
```

### **Metrics**

- **Extraction Time**: 2-5 seconds per page
- **Quality Threshold**: 0.6 (configurable)
- **Auto-retry**: Up to 3 attempts

---

## 🤝 Contributing

### **Adding New Extractor**

1. Create file: `extractors/myextractor_extractor.py`
2. Extend `BaseExtractor`
3. Implement `name`, `url_patterns`, `extract()`
4. Add to `extractors/__init__.py`
5. Auto-discovered on next run!

### **Export/Share Extractor**

```python
from extractor_marketplace import ExtractorMarketplace

marketplace = ExtractorMarketplace()
marketplace.export_extractor(MyExtractor)
# Saved: ~/.mcp/extractors/myextractor.json
```

---

## 📄 License

MIT License - MCP Legal Agent System

---

## 🆘 Support

For issues and feature requests, please use the task management system or contact the development team.

**Status**: ✅ Production Ready  
**Version**: 1.0.0  
**Last Updated**: 2026-03-06
