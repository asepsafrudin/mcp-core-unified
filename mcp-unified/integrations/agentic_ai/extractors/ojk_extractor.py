"""
OJK Extractor

Specialized extractor untuk ojk.go.id
Website Otoritas Jasa Keuangan
"""

from typing import Dict, List, Any
from .base_extractor import BaseExtractor, ExtractionConfig


class OJKExtractor(BaseExtractor):
    """
    Extractor untuk ojk.go.id

    Struktur website:
    - Regulasi dan peraturan OJK
    - SIAR (Sistem Informasi Aturan)
    """

    @property
    def name(self) -> str:
        return "ojk"

    @property
    def url_patterns(self) -> List[str]:
        return ["ojk.go.id"]

    @property
    def description(self) -> str:
        return "OJK - Otoritas Jasa Keuangan"

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
        """Extract regulasi dari OJK"""
        extract_script = """
            () => {
                const results = [];
                const rows = document.querySelectorAll('table tr, .regulation-item, .item');

                rows.forEach(row => {
                    const data = {};

                    const titleEl = row.querySelector('a, .title, h4, td:nth-child(2)');
                    data.title = titleEl ? titleEl.innerText.trim() : '';

                    const linkEl = row.querySelector('a');
                    data.url = linkEl ? linkEl.href : '';

                    const numberEl = row.querySelector('.number, td:nth-child(3)');
                    data.number = numberEl ? numberEl.innerText.trim() : '';

                    const typeEl = row.querySelector('.type, .jenis, td:nth-child(1)');
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

            if item.get("type"):
                item["type"] = item["type"].strip().upper()

            filtered.append(item)

        return filtered
