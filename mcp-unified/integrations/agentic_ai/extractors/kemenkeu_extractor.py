"""
Kemenkeu Extractor

Specialized extractor untuk jdih.kemenkeu.go.id
Website peraturan Kementerian Keuangan
"""

from typing import Dict, List, Any
from .base_extractor import BaseExtractor, ExtractionConfig


class KemenkeuExtractor(BaseExtractor):
    """
    Extractor untuk jdih.kemenkeu.go.id
    
    Struktur website:
    - Daftar peraturan dengan filter dan search
    - Card-based layout untuk peraturan
    - Detail dengan PDF download
    """
    
    @property
    def name(self) -> str:
        return "kemenkeu"
    
    @property
    def url_patterns(self) -> List[str]:
        return ["jdih.kemenkeu.go.id", "kemenkeu.go.id"]
    
    @property
    def description(self) -> str:
        return "JDIH Kemenkeu - Kementerian Keuangan"
    
    def __init__(self):
        config = ExtractionConfig(
            timeout=45,
            wait_for="domcontentloaded",
            scroll_count=3,
            js_render_wait=3,
            min_title_length=5,
            required_fields=["title"],
            optional_fields=["content", "url", "date", "number", "type"]
        )
        super().__init__(config)
    
    async def extract(self, page) -> List[Dict[str, Any]]:
        """
        Extract peraturan dari Kemenkeu
        """
        extract_script = """
            () => {
                const results = [];
                
                // Kemenkeu menggunakan card layout
                const cards = document.querySelectorAll(
                    '.card, .regulation-card, .item-list, tr'
                );
                
                cards.forEach(card => {
                    const item = {};
                    
                    // Extract title
                    const titleEl = card.querySelector('h4, h5, .title, a');
                    item.title = titleEl ? titleEl.innerText.trim() : '';
                    
                    // Extract URL
                    const linkEl = card.querySelector('a');
                    item.url = linkEl ? linkEl.href : '';
                    
                    // Extract number (nomor peraturan)
                    const numberEl = card.querySelector('.number, .nomor');
                    item.number = numberEl ? numberEl.innerText.trim() : '';
                    
                    // Extract type (PMK, Perdirjen, dll)
                    const typeEl = card.querySelector('.type, .jenis');
                    item.type = typeEl ? typeEl.innerText.trim() : '';
                    
                    // Extract date
                    const dateEl = card.querySelector('.date, .tanggal');
                    item.date = dateEl ? dateEl.innerText.trim() : '';
                    
                    // Extract description
                    const descEl = card.querySelector('.description, p, .content');
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
        seen = set()
        
        for item in items:
            title = item.get("title", "").strip()
            
            # Skip empty
            if not title or len(title) < 5:
                continue
            
            # Deduplicate by title + number
            key = f"{title}_{item.get('number', '')}"
            if key in seen:
                continue
            seen.add(key)
            
            # Format type (uppercase)
            if item.get("type"):
                item["type"] = item["type"].strip().upper()
            
            filtered.append(item)
        
        return filtered
