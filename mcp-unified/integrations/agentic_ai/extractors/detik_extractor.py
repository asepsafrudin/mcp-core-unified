"""
Detik Extractor

Specialized extractor untuk website Detik.com.
Struktur: Media text dengan class spesifik
"""

from typing import Dict, List, Any
from .base_extractor import BaseExtractor, ExtractionConfig


class DetikExtractor(BaseExtractor):
    """
    Extractor untuk Detik.com
    
    Struktur website:
    - News items dalam .media__text elements
    - Title dalam .media__title
    - Description dalam .media__desc
    """
    
    @property
    def name(self) -> str:
        return "detik"
    
    @property
    def url_patterns(self) -> List[str]:
        return ["detik.com", "detiknews.com"]
    
    @property
    def description(self) -> str:
        return "Detik.com - Portal Berita Indonesia"
    
    def __init__(self):
        config = ExtractionConfig(
            timeout=40,
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
        Extract news dari Detik.
        Strategy: Detik-specific class selectors.
        """
        extract_script = """
            () => {
                const results = [];
                
                // Detik-specific selectors
                const articleSelectors = [
                    '.media__text',
                    '.box_text',
                    '.list-content__item'
                ];
                
                let articles = [];
                for (const selector of articleSelectors) {
                    articles = document.querySelectorAll(selector);
                    if (articles.length > 0) break;
                }
                
                articles.forEach((article) => {
                    const item = {};
                    
                    // Extract title
                    const titleEl = article.querySelector('.media__title, h2, h3, .title');
                    item.title = titleEl ? titleEl.innerText.trim() : '';
                    
                    // Extract description
                    const descEl = article.querySelector('.media__desc, .description, p');
                    item.content = descEl ? descEl.innerText.trim() : '';
                    
                    // Extract date
                    const dateEl = article.querySelector('.date, .media__date, time');
                    item.date = dateEl ? dateEl.innerText.trim() : '';
                    
                    // Extract URL
                    const linkEl = article.querySelector('a');
                    item.url = linkEl ? linkEl.href : '';
                    
                    // Only add if we have minimal data
                    if (item.title && item.title.length > 10) {
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
        Post-processing: clean data dan filter.
        """
        filtered = []
        seen_urls = set()
        
        for item in items:
            title = item.get("title", "").strip()
            url = item.get("url", "")
            
            # Skip empty titles
            if not title or len(title) < 10:
                continue
            
            # Skip ads/promo
            skip_keywords = ["promo", "iklan", "sponsored"]
            if any(keyword in title.lower() for keyword in skip_keywords):
                continue
            
            # Skip duplicates by URL
            if url and url in seen_urls:
                continue
            
            if url:
                seen_urls.add(url)
            
            filtered.append(item)
        
        return filtered
