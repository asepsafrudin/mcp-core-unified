"""
Hukumonline Extractor

Specialized extractor untuk website Hukumonline.
Struktur: Heading-based (h2 untuk titles)
"""

from typing import Dict, List, Any
from .base_extractor import BaseExtractor, ExtractionConfig


class HukumonlineExtractor(BaseExtractor):
    """
    Extractor untuk Hukumonline.com
    
    Struktur website:
    - News titles di h2 elements
    - URLs di link dalam h2
    - Tidak ada article wrapper
    """
    
    @property
    def name(self) -> str:
        return "hukumonline"
    
    @property
    def url_patterns(self) -> List[str]:
        return ["hukumonline.com"]
    
    @property
    def description(self) -> str:
        return "Hukumonline.com - Portal Berita Hukum Indonesia"
    
    def __init__(self):
        config = ExtractionConfig(
            timeout=30,
            wait_for="domcontentloaded",
            scroll_count=3,
            js_render_wait=3,
            min_title_length=5,
            required_fields=["title"],
            optional_fields=["content", "url", "author", "date"]
        )
        super().__init__(config)
    
    async def extract(self, page) -> List[Dict[str, Any]]:
        """
        Extract news dari Hukumonline.
        Strategy: Ambil semua h2 sebagai titles, cari URL di link dalam h2.
        """
        extract_script = """
            () => {
                const results = [];
                
                // Find all headings (h2)
                const headings = document.querySelectorAll('h2');
                
                headings.forEach((heading) => {
                    const item = {};
                    
                    // Title from heading
                    item.title = heading.innerText.trim();
                    
                    // URL from link in heading
                    const linkEl = heading.querySelector('a');
                    item.url = linkEl ? linkEl.href : '';
                    
                    // Try to find description in parent
                    let parent = heading.parentElement;
                    let content = '';
                    
                    // Try to find description/content in parent
                    const descEl = parent.querySelector('p, .description, .summary');
                    if (descEl) {
                        content = descEl.innerText.trim();
                    }
                    
                    // If not found, look in next sibling
                    if (!content) {
                        let sibling = heading.nextElementSibling;
                        let attempts = 0;
                        while (sibling && attempts < 3) {
                            if (sibling.tagName === 'P' || 
                                sibling.classList.contains('description') ||
                                sibling.classList.contains('summary')) {
                                content = sibling.innerText.trim();
                                break;
                            }
                            sibling = sibling.nextElementSibling;
                            attempts++;
                        }
                    }
                    
                    item.content = content;
                    
                    // Filter: only add if title is meaningful (not section headers)
                    if (item.title && 
                        item.title.length > 10 && 
                        !item.title.toLowerCase().includes('berlangganan') &&
                        !item.title.toLowerCase().includes('katalog') &&
                        !item.title.toLowerCase().includes('solusi')) {
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
        Post-processing: filter out section headers dan duplicates.
        """
        filtered = []
        seen_urls = set()
        
        for item in items:
            title = item.get("title", "").lower()
            url = item.get("url", "")
            
            # Skip common section headers
            skip_keywords = [
                "premium stories", "kabar kampus", "berlangganan",
                "katalog produk", "solusi", "info hukum"
            ]
            
            if any(keyword in title for keyword in skip_keywords):
                continue
            
            # Skip duplicates by URL
            if url and url in seen_urls:
                continue
            
            if url:
                seen_urls.add(url)
            
            filtered.append(item)
        
        return filtered
