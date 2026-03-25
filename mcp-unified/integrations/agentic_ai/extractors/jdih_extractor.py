"""
JDIH Extractor

Specialized extractor untuk website JDIHN (Jaringan Dokumentasi Hukum Nasional).
Struktur: Article-based dengan wrapper elements
"""

from typing import Dict, List, Any
from .base_extractor import BaseExtractor, ExtractionConfig


class JDIHExtractor(BaseExtractor):
    """
    Extractor untuk JDIHN.go.id
    
    Struktur website:
    - News items dalam .news-item atau article elements
    - Traditional article structure
    """
    
    @property
    def name(self) -> str:
        return "jdih"
    
    @property
    def url_patterns(self) -> List[str]:
        return ["jdihn.go.id", "jdih.go.id"]
    
    @property
    def description(self) -> str:
        return "JDIHN - Jaringan Dokumentasi Hukum Nasional"
    
    def __init__(self):
        config = ExtractionConfig(
            timeout=60,
            wait_for="load",
            scroll_count=3,
            js_render_wait=3,
            min_title_length=5,
            required_fields=["title"],
            optional_fields=["content", "url", "author", "date"]
        )
        super().__init__(config)
    
    async def extract(self, page) -> List[Dict[str, Any]]:
        """
        Extract news/document dari JDIHN.
        Strategy: Traditional article-based extraction.
        """
        extract_script = """
            () => {
                const results = [];
                
                // Try multiple selectors untuk articles
                const articleSelectors = [
                    '.news-item',
                    '.peraturan-item', 
                    'article',
                    '.content-item'
                ];
                
                let articles = [];
                for (const selector of articleSelectors) {
                    articles = document.querySelectorAll(selector);
                    if (articles.length > 0) break;
                }
                
                articles.forEach((article) => {
                    const item = {};
                    
                    // Extract title
                    const titleEl = article.querySelector('h1, h2, h3, .title, .headline');
                    item.title = titleEl ? titleEl.innerText.trim() : '';
                    
                    // Extract content/description
                    const contentEl = article.querySelector('.content, .description, p, .summary');
                    item.content = contentEl ? contentEl.innerText.trim() : '';
                    
                    // Extract date
                    const dateEl = article.querySelector('.date, .tanggal, time, .published');
                    item.date = dateEl ? dateEl.innerText.trim() : '';
                    
                    // Extract author
                    const authorEl = article.querySelector('.author, .byline, .writer');
                    item.author = authorEl ? authorEl.innerText.trim() : '';
                    
                    // Extract URL
                    const linkEl = article.querySelector('a');
                    item.url = linkEl ? linkEl.href : '';
                    
                    // Only add if we have minimal data
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
        Post-processing: clean data dan filter duplicates.
        """
        filtered = []
        seen_titles = set()
        
        for item in items:
            title = item.get("title", "").strip()
            
            # Skip empty titles
            if not title or len(title) < 5:
                continue
            
            # Skip duplicates by title
            title_lower = title.lower()
            if title_lower in seen_titles:
                continue
            
            seen_titles.add(title_lower)
            
            # Clean content
            content = item.get("content", "")
            if content:
                # Remove excessive whitespace
                item["content"] = " ".join(content.split())
            
            filtered.append(item)
        
        return filtered
