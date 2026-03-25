"""
Generic Extractor

Fallback extractor untuk website yang tidak memiliki specialized extractor.
Menggunakan heuristic untuk detect struktur website.
"""

from typing import Dict, List, Any
from .base_extractor import BaseExtractor, ExtractionConfig


class GenericExtractor(BaseExtractor):
    """
    Generic extractor untuk website apapun.
    
    Strategy:
    1. Try common article selectors
    2. Try heading-based extraction
    3. Try paragraph-based extraction
    """
    
    @property
    def name(self) -> str:
        return "generic"
    
    @property
    def url_patterns(self) -> List[str]:
        """Generic extractor bisa handle any URL"""
        return ["*"]  # Wildcard - handle any URL
    
    @property
    def description(self) -> str:
        return "Generic extractor untuk website apapun (fallback)"
    
    def can_handle(self, url: str) -> bool:
        """Generic extractor bisa handle any URL sebagai fallback"""
        return True  # Always return True sebagai last resort
    
    def __init__(self):
        config = ExtractionConfig(
            timeout=45,
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
        Extract dengan multiple strategies.
        """
        # Try multiple extraction strategies
        strategies = [
            self._extract_article_based,
            self._extract_heading_based,
            self._extract_paragraph_based
        ]
        
        for strategy in strategies:
            try:
                results = await strategy(page)
                if results and len(results) > 0:
                    return results
            except Exception as e:
                continue
        
        return []
    
    async def _extract_article_based(self, page) -> List[Dict[str, Any]]:
        """Try article-based extraction"""
        script = """
            () => {
                const results = [];
                const selectors = ['article', '.article', '.post', '.news-item', '.entry'];
                
                for (const sel of selectors) {
                    const articles = document.querySelectorAll(sel);
                    if (articles.length === 0) continue;
                    
                    articles.forEach(article => {
                        const item = {};
                        
                        const titleEl = article.querySelector('h1, h2, h3, .title, .entry-title');
                        item.title = titleEl ? titleEl.innerText.trim() : '';
                        
                        const contentEl = article.querySelector('p, .content, .entry-content, .summary');
                        item.content = contentEl ? contentEl.innerText.trim() : '';
                        
                        const linkEl = article.querySelector('a');
                        item.url = linkEl ? linkEl.href : '';
                        
                        if (item.title && item.title.length > 10) {
                            results.push(item);
                        }
                    });
                    
                    if (results.length > 0) break;
                }
                
                return results;
            }
        """
        return await page.evaluate(script)
    
    async def _extract_heading_based(self, page) -> List[Dict[str, Any]]:
        """Try heading-based extraction"""
        script = """
            () => {
                const results = [];
                const headings = document.querySelectorAll('h2, h3');
                
                headings.forEach(heading => {
                    const item = {};
                    item.title = heading.innerText.trim();
                    
                    const linkEl = heading.querySelector('a');
                    item.url = linkEl ? linkEl.href : '';
                    
                    // Look for description in next siblings
                    let sibling = heading.nextElementSibling;
                    let attempts = 0;
                    while (sibling && attempts < 3) {
                        if (sibling.tagName === 'P' || sibling.classList.contains('description')) {
                            item.content = sibling.innerText.trim();
                            break;
                        }
                        sibling = sibling.nextElementSibling;
                        attempts++;
                    }
                    
                    if (item.title && item.title.length > 10) {
                        results.push(item);
                    }
                });
                
                return results;
            }
        """
        return await page.evaluate(script)
    
    async def _extract_paragraph_based(self, page) -> List[Dict[str, Any]]:
        """Try paragraph-based extraction sebagai last resort"""
        script = """
            () => {
                const results = [];
                const paragraphs = document.querySelectorAll('p');
                
                paragraphs.forEach((p, index) => {
                    const text = p.innerText.trim();
                    
                    // Only consider substantial paragraphs
                    if (text.length > 50 && text.length < 500) {
                        const item = {
                            title: text.substring(0, 80) + (text.length > 80 ? '...' : ''),
                            content: text,
                            url: ''
                        };
                        results.push(item);
                    }
                });
                
                // Limit to first 10 substantial paragraphs
                return results.slice(0, 10);
            }
        """
        return await page.evaluate(script)
    
    async def post_process(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter dan clean generic results"""
        filtered = []
        seen = set()
        
        for item in items:
            title = item.get("title", "").strip()
            
            # Basic validation
            if not title or len(title) < 10:
                continue
            
            # Skip navigation/footer items
            skip_keywords = ["home", "about", "contact", "privacy", "terms", "copyright"]
            if any(keyword in title.lower() for keyword in skip_keywords):
                continue
            
            # Deduplicate
            key = title.lower()[:50]
            if key in seen:
                continue
            seen.add(key)
            
            filtered.append(item)
        
        return filtered[:20]  # Limit to 20 items
