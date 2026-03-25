"""
Peraturan.go.id Scraper
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from datetime import datetime


class PeraturanScraper:
    """Scraper untuk peraturan.go.id"""
    
    BASE_URL = "https://peraturan.go.id"
    
    def __init__(self):
        self.session = None
        self.rate_limit_delay = 1.0
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_regulations(
        self,
        keyword: str = "",
        kategori: str = "",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search peraturan dari peraturan.go.id
        
        Args:
            keyword: Kata kunci
            kategori: Kategori peraturan
            limit: Max results
        """
        results = []
        
        try:
            params = {'q': keyword}
            if kategori:
                params['kategori'] = kategori
            
            async with self.session.get(
                f"{self.BASE_URL}/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Parse search results
                    items = soup.find_all('div', class_='search-result')
                    
                    for item in items[:limit]:
                        reg_data = self._parse_result(item)
                        if reg_data:
                            results.append(reg_data)
                    
                    await asyncio.sleep(self.rate_limit_delay)
        
        except Exception as e:
            print(f"Peraturan scraper error: {e}")
        
        return results
    
    def _parse_result(self, item) -> Optional[Dict]:
        """Parse search result item."""
        try:
            title = item.find('h4') or item.find('h3') or item.find('a')
            link = item.find('a', href=True)
            snippet = item.find('p') or item.find('div', class_='snippet')
            
            return {
                'source': 'peraturan.go.id',
                'title': title.get_text(strip=True) if title else 'Unknown',
                'url': f"{self.BASE_URL}{link['href']}" if link else None,
                'snippet': snippet.get_text(strip=True) if snippet else None,
                'scraped_at': datetime.now().isoformat()
            }
        except Exception:
            return None
