"""
Generic Extractor - Fallback extractor untuk website apapun.

Features:
- Article extraction menggunakan readability
- Metadata extraction dari meta tags
- Content cleaning
- Automatic content detection
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_extractor import BaseExtractor, ExtractedContent


class GenericExtractor(BaseExtractor):
    """
    Generic fallback extractor untuk website apapun.
    
    Menggunakan berbagai teknik untuk mengekstrak konten:
    1. Readability algorithm
    2. Meta tag extraction
    3. Content heuristics
    4. Schema.org structured data
    """
    
    URL_PATTERNS = ["*"]  # Accept all URLs
    DOMAINS = []  # All domains
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize generic extractor."""
        super().__init__(config)
        self.min_content_length = config.get("min_content_length", 200) if config else 200
    
    def can_handle(self, url: str) -> bool:
        """Generic extractor bisa handle semua URL."""
        return True
    
    async def extract(self, page) -> ExtractedContent:
        """
        Extract content dari page menggunakan berbagai metode.
        
        Args:
            page: Playwright page object
            
        Returns:
            ExtractedContent
        """
        url = page.url
        
        # Wait untuk page load
        await page.wait_for_load_state("networkidle")
        
        # Extract menggunakan JavaScript (readability-like algorithm)
        extraction_script = """
            () => {
                const data = {};
                
                // Helper: Get text density
                function getTextDensity(element) {
                    const text = element.innerText || '';
                    const textLength = text.length;
                    const linkLength = Array.from(element.querySelectorAll('a'))
                        .reduce((sum, a) => sum + (a.innerText || '').length, 0);
                    return textLength > 0 ? (textLength - linkLength) / textLength : 0;
                }
                
                // Helper: Score element
                function scoreElement(element) {
                    let score = 0;
                    const text = element.innerText || '';
                    
                    // Length bonus
                    score += Math.min(text.length / 100, 10);
                    
                    // Paragraph density
                    const paragraphs = element.querySelectorAll('p').length;
                    score += paragraphs * 2;
                    
                    // Text density
                    score += getTextDensity(element) * 10;
                    
                    // Class/id penalties/bonuses
                    const classAndId = (element.className || '') + ' ' + (element.id || '');
                    if (/article|content|post|entry|main/i.test(classAndId)) score += 5;
                    if (/comment|footer|sidebar|nav|menu/i.test(classAndId)) score -= 5;
                    
                    return score;
                }
                
                // Extract title
                data.title = document.querySelector('h1')?.innerText?.trim() 
                    || document.querySelector('title')?.innerText?.trim()
                    || 'Untitled';
                
                // Extract meta description
                data.description = document.querySelector('meta[name="description"]')?.content
                    || document.querySelector('meta[property="og:description"]')?.content
                    || '';
                
                // Extract author
                data.author = document.querySelector('meta[name="author"]')?.content
                    || document.querySelector('meta[property="og:author"]')?.content
                    || document.querySelector('[class*="author"]')?.innerText?.trim()
                    || '';
                
                // Extract date
                data.date = document.querySelector('meta[property="article:published_time"]')?.content
                    || document.querySelector('time')?.getAttribute('datetime')
                    || document.querySelector('time')?.innerText
                    || '';
                
                // Find main content
                const candidates = [];
                const elements = document.querySelectorAll('article, [class*="article"], [class*="content"], [class*="post"], [class*="entry"], main, section');
                
                elements.forEach(el => {
                    const score = scoreElement(el);
                    candidates.push({ element: el, score: score });
                });
                
                // Also check divs
                document.querySelectorAll('div').forEach(el => {
                    if (el.children.length > 3) {
                        const score = scoreElement(el);
                        if (score > 10) {
                            candidates.push({ element: el, score: score });
                        }
                    }
                });
                
                // Sort by score
                candidates.sort((a, b) => b.score - a.score);
                
                // Get best candidate
                if (candidates.length > 0) {
                    const best = candidates[0].element;
                    data.content = best.innerText.trim();
                    data.html = best.innerHTML;
                } else {
                    // Fallback: get body text
                    data.content = document.body?.innerText?.trim() || '';
                }
                
                // Extract images
                const images = [];
                document.querySelectorAll('article img, .content img, img').forEach(img => {
                    if (img.src && !img.src.includes('icon') && !img.src.includes('logo')) {
                        images.push({
                            src: img.src,
                            alt: img.alt || '',
                        });
                    }
                });
                data.images = images.slice(0, 10); // Max 10 images
                
                // Extract links
                const links = [];
                document.querySelectorAll('article a, .content a').forEach(a => {
                    if (a.href && a.innerText.trim()) {
                        links.push({
                            url: a.href,
                            text: a.innerText.trim(),
                        });
                    }
                });
                data.links = links.slice(0, 20); // Max 20 links
                
                // Extract schema.org data
                const schemaScript = document.querySelector('script[type="application/ld+json"]');
                if (schemaScript) {
                    try {
                        data.schema = JSON.parse(schemaScript.innerText);
                    } catch (e) {
                        data.schema = null;
                    }
                }
                
                return data;
            }
        """
        
        data = await page.evaluate(extraction_script)
        
        # Parse date
        published_date = self._extract_date(data.get('date', ''))
        
        # Clean content
        content_text = data.get('content', '')
        
        # Build structured content
        structured_content = f"""# {data.get('title', 'Untitled')}

**Sumber:** {url}
**Tanggal:** {published_date.strftime('%d %B %Y') if published_date else 'Tidak diketahui'}
"""
        
        if data.get('author'):
            structured_content += f"**Penulis:** {data['author']}\n"
        
        if data.get('description'):
            structured_content += f"\n**Ringkasan:** {data['description']}\n"
        
        structured_content += f"\n---\n\n{content_text}"
        
        # Metadata
        metadata = {
            "source_type": "generic_web",
            "description": data.get('description', ''),
            "image_count": len(data.get('images', [])),
            "link_count": len(data.get('links', [])),
            "has_schema": data.get('schema') is not None,
            "word_count": len(content_text.split()),
        }
        
        return ExtractedContent(
            url=url,
            title=data.get('title', 'Untitled'),
            content=self._clean_text(structured_content),
            author=data.get('author') or None,
            published_date=published_date,
            metadata=metadata,
            extracted_at=datetime.now()
        )
    
    def _extract_date(self, date_text: str) -> Optional[datetime]:
        """Extract date dari berbagai format."""
        if not date_text:
            return None
        
        # ISO format
        iso_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_text)
        if iso_match:
            try:
                return datetime(
                    int(iso_match.group(1)),
                    int(iso_match.group(2)),
                    int(iso_match.group(3))
                )
            except ValueError:
                pass
        
        # Try dateutil parser
        try:
            from dateutil import parser
            return parser.parse(date_text, fuzzy=True)
        except Exception:
            pass
        
        return None
    
    def validate(self, content: ExtractedContent) -> bool:
        """Validate generic content."""
        # Check basic requirements
        if not content.title or content.title == 'Untitled':
            return False
        
        if len(content.content) < self.min_content_length:
            return False
        
        # Check untuk duplicate content markers
        if content.content.count('\n') < 2:
            return False
        
        return True