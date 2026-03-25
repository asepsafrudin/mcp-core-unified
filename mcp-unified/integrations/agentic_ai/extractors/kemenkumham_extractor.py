"""
Kemenkumham Extractor

Specialized extractor untuk hukum.kemenkumham.go.id
Website Direktorat Jenderal Kekayaan Intelektual
"""

from typing import Dict, List, Any
from .base_extractor import BaseExtractor, ExtractionConfig


class KemenkumhamExtractor(BaseExtractor):
    """
    Extractor untuk hukum.kemenkumham.go.id

    Struktur website:
    - Database peraturan hukum
    - PDF documents
    """

    @property
    def name(self) -> str:
        return "kemenkumham"

    @property
    def url_patterns(self) -> List[str]:
        return ["hukum.kemenkumham.go.id"]

    @property
    def description(self) -> str:
        return "Kemenkumham - Kementerian Hukum dan HAM"

    def __init__(self):
        config = ExtractionConfig(
            timeout=45,
            wait_for="domcontentloaded",
            scroll_count=2,
            js_render_wait=2,
            min_title_length=5,
            required_fields=["title"],
            optional_fields=["content", "url", "date", "number", "type"]
        )
        super().__init__(config)

    async def extract(self, page) -> List[Dict[str, Any]]:
        """Extract peraturan dari Kemenkumham"""
        extract_script = """
            () => {
                const results = [];
                const rows = document.querySelectorAll('table tr, .item');

                rows.forEach(row => {
                    const data = {};

                    const titleEl = row.querySelector('a, .title, h4');
                    data.title = titleEl ? titleEl.innerText.trim() : '';

                    const linkEl = row.querySelector('a');
                    data.url = linkEl ? linkEl.href : '';

                    const numberEl = row.querySelector('.number, td:nth-child(2)');
                    data.number = numberEl ? numberEl.innerText.trim() : '';

                    const typeEl = row.querySelector('.type, .jenis, td:nth-child(3)');
                    data.type = typeEl ? typeEl.innerText.trim() : '';

                    const dateEl = row.querySelector('.date, td:nth-child(4)');
                    data.date = dateEl ? dateEl.innerText.trim() : '';

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
        seen = set()

        for item in items:
            title = item.get("title", "").strip()
            if not title or len(title) < 5:
                continue

            key = f"{title}_{item.get('number', '')}"
            if key in seen:
                continue
            seen.add(key)

            filtered.append(item)

        return filtered
