"""
Kominfo Extractor

Specialized extractor untuk kominfo.go.id
Website Kementerian Komunikasi dan Informatika
"""

from typing import Dict, List, Any
from .base_extractor import BaseExtractor, ExtractionConfig


class KominfoExtractor(BaseExtractor):
    """
    Extractor untuk kominfo.go.id
    
    Struktur website:
    - Peraturan Kominfo
    - News dan pengumuman
    """
    
    @property
    def name(self) -> str:
        return "kominfo"
    
    @property
    def url_patterns(self) -> List[str]:
        return ["kominfo.go.id"]
    
    @property
    def description(self) -> str:
        return "Kominfo - Kementerian Komunikasi dan Informatika"
    
    def __init__(self):
        config = ExtractionConfig(
            timeout=45,
            wait_for="domcontentloaded",
            scroll_count=3,
            js_render_wait=3,
            min_title_length=5,
            required_fields=["title"],
            optional_fields=["content", "url", "date", "category"]
        )
        super().__init__(config)
    
    async def extract(self, page) -> List[Dict[str, Any]]:
        """
        Extract peraturan dari Kominfo
        """
        extract_script = """
            () => {
                const results = [];
                
                // Kominfo menggunakan card atau list
                const items = document.querySelectorAll(
                    '.berita-item, .news-item, article, .post'
                );
                
                items.forEach(item => {
                    const data = {};
                    
                    // Extract title
                    const titleEl = item.querySelector('h3, h4, .title, a');
                    data.title = titleEl ? titleEl.innerText.trim() : '';
                    
                    // Extract URL
                    const linkEl = item.querySelector('a');
                    data.url = linkEl ? linkEl.href : '';
                    
                    // Extract category
                    const catEl = item.querySelector('.category, .kategori');
                    data.category = catEl ? catEl.innerText.trim() : '';
                    
                    // Extract date
                    const dateEl = item.querySelector('.date, .tanggal, time');
                    data.date = dateEl ? dateEl.innerText.trim() : '';
                    
                    // Extract description
                    const descEl = item.querySelector('.description, p, .summary');
                    data.content = descEl ? descEl.innerText.trim() : '';
                    
                    // Filter: hanya ambil yang ada title
                    if (data.title && data.title.length > 5) {
                        results.push(data);
                    }
                });
                
                return results;
            }
        """
        
        data = await page.evaluate(extract_script)
        return data if data else []
    
    async def post_process(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean dan filter hasil
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
            
            filtered.append(item)
        
        return filtered
