"""
Peraturan BPK Extractor

Specialized extractor untuk peraturan.bpk.go.id
Website peraturan Badan Pemeriksa Keuangan
"""

from typing import Dict, List, Any
from .base_extractor import BaseExtractor, ExtractionConfig


class PeraturanBPKExtractor(BaseExtractor):
    """
    Extractor untuk peraturan.bpk.go.id
    
    Struktur website:
    - Daftar peraturan dalam table/list
    - Detail peraturan dengan PDF links
    """
    
    @property
    def name(self) -> str:
        return "peraturan_bpk"
    
    @property
    def url_patterns(self) -> List[str]:
        return ["peraturan.bpk.go.id"]
    
    @property
    def description(self) -> str:
        return "Peraturan BPK - Badan Pemeriksa Keuangan"
    
    def __init__(self):
        config = ExtractionConfig(
            timeout=45,
            wait_for="domcontentloaded",
            scroll_count=2,
            js_render_wait=2,
            min_title_length=5,
            required_fields=["title"],
            optional_fields=["content", "url", "date", "type"]
        )
        super().__init__(config)
    
    async def extract(self, page) -> List[Dict[str, Any]]:
        """
        Extract peraturan dari BPK
        """
        extract_script = """
            () => {
                const results = [];
                
                // BPK menggunakan tabel atau list
                const rows = document.querySelectorAll('table tr, .item, .regulation-item');
                
                rows.forEach(row => {
                    const item = {};
                    
                    // Extract title
                    const titleEl = row.querySelector('a, .title, h3, h4');
                    item.title = titleEl ? titleEl.innerText.trim() : '';
                    
                    // Extract URL
                    const linkEl = row.querySelector('a');
                    item.url = linkEl ? linkEl.href : '';
                    
                    // Extract type (Peraturan, Keputusan, dll)
                    const typeEl = row.querySelector('.type, .category, td:nth-child(2)');
                    item.type = typeEl ? typeEl.innerText.trim() : '';
                    
                    // Extract date
                    const dateEl = row.querySelector('.date, td:nth-child(3)');
                    item.date = dateEl ? dateEl.innerText.trim() : '';
                    
                    // Extract description/content
                    const descEl = row.querySelector('.description, p');
                    item.content = descEl ? descEl.innerText.trim() : '';
                    
                    // Filter: hanya ambil yang ada title
                    if (item.title && item.title.length > 5) {
                        results.push(item);
                    }
                });
                
                return results;
            }
        """
        
        data = await page.evaluate(extract_script)
        return data if data else []
    
    async def post_process(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean dan format hasil
        """
        filtered = []
        seen_urls = set()
        
        for item in items:
            title = item.get("title", "").strip()
            url = item.get("url", "")
            
            # Skip empty
            if not title or len(title) < 5:
                continue
            
            # Skip duplicates
            if url and url in seen_urls:
                continue
            
            if url:
                seen_urls.add(url)
            
            # Format type
            if item.get("type"):
                item["type"] = item["type"].strip()
            
            filtered.append(item)
        
        return filtered
