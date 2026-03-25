"""
Kemenpan Extractor

Specialized extractor untuk kemenpan.go.id
Website Kementerian Pendayagunaan Aparatur Negara
"""

from typing import Dict, List, Any
from .base_extractor import BaseExtractor, ExtractionConfig


class KemenpanExtractor(BaseExtractor):
    """
    Extractor untuk kemenpan.go.id

    Struktur website:
    - Peraturan ASN dan reformasi birokrasi
    - List dan card layout
    """

    @property
    def name(self) -> str:
        return "kemenpan"

    @property
    def url_patterns(self) -> List[str]:
        return ["kemenpan.go.id"]

    @property
    def description(self) -> str:
        return "Kemenpan - Kementerian PANRB"

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
        """Extract peraturan dari Kemenpan"""
        extract_script = """
            () => {
                const results = [];
                const items = document.querySelectorAll(
                    '.news-item, article, .post-item, .list-item'
                );

                items.forEach(item => {
                    const data = {};

                    const titleEl = item.querySelector('h3, h4, .title, a');
                    data.title = titleEl ? titleEl.innerText.trim() : '';

                    const linkEl = item.querySelector('a');
                    data.url = linkEl ? linkEl.href : '';

                    const dateEl = item.querySelector('.date, time, .published');
                    data.date = dateEl ? dateEl.innerText.trim() : '';

                    const descEl = item.querySelector('p, .description, .summary');
                    data.content = descEl ? descEl.innerText.trim() : '';

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
        filtered = []
        seen_urls = set()

        for item in items:
            title = item.get("title", "").strip()
            url = item.get("url", "")

            if not title or len(title) < 5:
                continue

            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)

            filtered.append(item)

        return filtered
