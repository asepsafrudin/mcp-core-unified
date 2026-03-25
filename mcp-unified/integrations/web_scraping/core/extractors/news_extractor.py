"""
News Extractor - Ekstrak artikel berita dari berbagai portal berita.

Features:
- Support multiple news sites
- Extract title, content, author, date
- Clean article content
- Handle various news site layouts
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_extractor import BaseExtractor, ExtractedContent


class NewsExtractor(BaseExtractor):
    """
    Extractor untuk portal berita.
    
    Supports:
    - Kompas.com
    - Detik.com
    - CNN Indonesia
    - Tribunnews.com
    - Liputan6.com
    - Dan website berita lainnya
    """
    
    URL_PATTERNS = [
        "https://*.kompas.com/read/*",
        "https://*.detik.com/read/*",
        "https://*.cnnindonesia.com/*",
        "https://*.tribunnews.com/*",
        "https://*.liputan6.com/read/*",
        "https://*.merdeka.com/*",
        "https://*.tempo.co/read/*",
        "https://*.kumparan.com/*",
    ]
    
    DOMAINS = [
        "kompas.com",
        "detik.com",
        "cnnindonesia.com",
        "tribunnews.com",
        "liputan6.com",
        "merdeka.com",
        "tempo.co",
        "kumparan.com",
        "republika.co.id",
        "viva.co.id",
        "okezone.com",
        "sindonews.com",
    ]
    
    # Site-specific selectors
    SITE_SELECTORS = {
        "kompas.com": {
            "title": "h1.read__title, h1",
            "content": ".read__content, .detail__body-text",
            "author": ".read__author, .credit-author",
            "date": ".read__time, .date",
            "tags": ".tag__article a",
        },
        "detik.com": {
            "title": "h1.detail__title",
            "content": ".detail__body-text, .itp_bodycontent",
            "author": ".detail__author, .author",
            "date": ".detail__date",
            "tags": ".detail__tag a",
        },
        "cnnindonesia.com": {
            "title": "h1.title",
            "content": ".detail-text, article",
            "author": ".author",
            "date": ".date",
            "tags": ".tag a",
        },
        "tribunnews.com": {
            "title": "h1",
            "content": ".side-article.txt-article",
            "author": ".author",
            "date": "time",
        },
        "liputan6.com": {
            "title": "h1.read-page--header--title",
            "content": ".article-content-body__item-content",
            "author": ".read-page--header--author__name",
            "date": ".read-page--header--author__datetime",
        },
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize news extractor."""
        super().__init__(config)
    
    def can_handle(self, url: str) -> bool:
        """Check if URL is a news article."""
        return self._match_url_pattern(url)
    
    async def extract(self, page) -> ExtractedContent:
        """
        Extract article dari news page.
        
        Args:
            page: Playwright page object
            
        Returns:
            ExtractedContent dengan article data
        """
        url = page.url
        domain = self._get_domain(url)
        
        # Get selectors untuk domain ini
        selectors = self._get_selectors_for_domain(domain)
        
        # Wait untuk content load
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(1)  # Extra wait untuk dynamic content
        
        # Extract menggunakan JavaScript
        extraction_script = f"""
            () => {{
                const data = {{}};
                
                // Title
                const titleEl = document.querySelector('{selectors.get("title", "h1")}');
                data.title = titleEl?.innerText?.trim() || document.title?.trim() || '';
                
                // Content - try multiple selectors
                let contentEl = document.querySelector('{selectors.get("content", "article")}');
                if (!contentEl) {{
                    contentEl = document.querySelector('article, .article-content, .post-content, .entry-content, [class*="content"]');
                }}
                data.content = contentEl?.innerText?.trim() || '';
                
                // Author
                const authorEl = document.querySelector('{selectors.get("author", ".author")}');
                data.author = authorEl?.innerText?.trim() || '';
                
                // Date
                const dateEl = document.querySelector('{selectors.get("date", "time, .date, .published")}');
                data.date = dateEl?.innerText?.trim() || dateEl?.getAttribute('datetime') || '';
                
                // Tags
                const tagEls = document.querySelectorAll('{selectors.get("tags", ".tag a, [rel=\"tag\"]")}');
                data.tags = Array.from(tagEls).map(el => el.innerText.trim()).filter(t => t);
                
                // Images
                const imgEls = document.querySelectorAll('article img, .content img');
                data.images = Array.from(imgEls).map(el => el.src).filter(src => src);
                
                return data;
            }}
        """
        
        data = await page.evaluate(extraction_script)
        
        # Clean author text
        author = self._clean_author(data.get('author', ''))
        
        # Parse date
        published_date = self._parse_date(data.get('date', ''))
        
        # Build content dengan format yang bagus
        content_text = f"""# {data.get('title', 'Artikel Berita')}

**Sumber:** {domain}
**Penulis:** {author or 'Tidak diketahui'}
**Tanggal:** {published_date.strftime('%d %B %Y') if published_date else data.get('date', 'Tidak diketahui')}
**URL:** {url}
"""
        
        if data.get('tags'):
            content_text += f"\n**Tags:** {', '.join(data['tags'][:10])}\n"
        
        content_text += f"\n---\n\n{data.get('content', '')}"
        
        # Metadata
        metadata = {
            "source_type": "news",
            "news_portal": domain,
            "author": author,
            "tags": data.get('tags', []),
            "image_count": len(data.get('images', [])),
            "word_count": len(data.get('content', '').split()),
        }
        
        return ExtractedContent(
            url=url,
            title=data.get('title', 'Artikel Berita'),
            content=self._clean_text(content_text),
            author=author,
            published_date=published_date,
            metadata=metadata,
            extracted_at=datetime.now()
        )
    
    def _get_selectors_for_domain(self, domain: str) -> Dict[str, str]:
        """Get selectors untuk specific domain."""
        for site_domain, selectors in self.SITE_SELECTORS.items():
            if site_domain in domain:
                return selectors
        
        # Default selectors
        return {
            "title": "h1",
            "content": "article, .article, .content, main",
            "author": ".author, [class*='author'], meta[name='author']",
            "date": "time, .date, .published, [class*='date']",
            "tags": ".tag, [class*='tag']",
        }
    
    def _clean_author(self, author_text: str) -> str:
        """Clean author name dari noise."""
        if not author_text:
            return ""
        
        # Remove common prefixes
        prefixes = ["oleh", "by", "penulis", "author", "ditulis", "-"]
        author_lower = author_text.lower()
        
        for prefix in prefixes:
            if author_lower.startswith(prefix):
                author_text = author_text[len(prefix):].strip()
                break
        
        # Remove extra whitespace dan newlines
        author_text = re.sub(r'\s+', ' ', author_text).strip()
        
        return author_text
    
    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse date dari berbagai format."""
        if not date_text:
            return None
        
        # Try various patterns
        patterns = [
            # Indonesian format
            r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})',
            r'(\d{1,2})/(\d{1,2})/(\d{4})',
            r'(\d{4})-(\d{2})-(\d{2})',
        ]
        
        month_map = {
            'januari': 1, 'jan': 1,
            'februari': 2, 'feb': 2,
            'maret': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'mei': 5, 'may': 5,
            'juni': 6, 'jun': 6,
            'juli': 7, 'jul': 7,
            'agustus': 8, 'agu': 8, 'aug': 8,
            'september': 9, 'sep': 9,
            'oktober': 10, 'okt': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'desember': 12, 'des': 12, 'dec': 12,
        }
        
        for pattern in patterns:
            match = re.search(pattern, date_text, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 3:
                        day, month, year = groups
                        
                        # Handle month name
                        if month.lower() in month_map:
                            month = month_map[month.lower()]
                        
                        return datetime(int(year), int(month), int(day))
                except Exception:
                    continue
        
        return None
    
    def validate(self, content: ExtractedContent) -> bool:
        """Validate news content."""
        if not super().validate(content):
            return False
        
        # Check word count (minimal 100 kata)
        word_count = len(content.content.split())
        if word_count < 50:
            return False
        
        return True


# Import untuk async
import asyncio