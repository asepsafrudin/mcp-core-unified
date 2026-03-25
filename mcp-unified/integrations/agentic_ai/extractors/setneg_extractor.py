"""
Setneg Extractor

Specialized extractor untuk jdih.setneg.go.id
Website peraturan Sekretariat Negara
"""

from typing import Dict, List, Any
from .base_extractor import BaseExtractor, ExtractionConfig


class SetnegExtractor(BaseExtractor):
    """
    Extractor untuk jdih.setneg.go.id
    
    Struktur website:
    - List peraturan dengan pagination
    - Detail peraturan dengan PDF download
    """
    
    @property
    def name(self) -> str:
        return "setneg"
    
    @property
    def url_patterns(self) -> List[str]:
        return ["jdih.setneg.go.id", "setneg.go.id"]
    
    @property
    def description(self) -> str:
        return "JDIH Setneg - Sekretariat Negara"
    
    def __init__(self):
        config = ExtractionConfig(
            timeout=45,
            wait_for="domcontentloaded",
            scroll_count=3,
            js_render_wait=3,
            min_title_length=5,
            required_fields=["title"],
            optional_fields=["content", "url", "date", "number"]
        )
        super().__init__(config)
    
    async def extract(self, page) -> List[Dict[str, Any]]:
        """
        Extract peraturan dari Setneg
        """
        extract_script = """
            () => {
                const results = [];
                
                // Setneg menggunakan list atau table
                const items = document.querySelectorAll(
                    '.list-group-item, tr, .item, .regulation-item'
                );
                
                items.forEach(item => {
                    const data = {};
                    
                    // Extract title
                    const titleEl = item.querySelector('h4, h5, .title, a');
                    data.title = titleEl ? titleEl.innerText.trim() : '';
                    
                    // Extract URL
                    const linkEl = item.querySelector('a');
                    data.url = linkEl ? linkEl.href : '';
                    
                    // Extract number (nomor peraturan)
                    const numberEl = item.querySelector('.number, .nomor, td:nth-child(2)');
                    data.number = numberEl ? numberEl.innerText.trim() : '';
                    
                    // Extract date
                    const dateEl = item.querySelector('.date, .tanggal, td:nth-child(3)');
                    data.date = dateEl ? dateEl.innerText.trim() : '';
                    
                    // Extract description
                    const descEl = item.querySelector('.description, p');
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
            
            # Clean number field
            if item.get("number"):
                item["number"] = item["number"].strip()
            
            filtered.append(item)
        
        return filtered
