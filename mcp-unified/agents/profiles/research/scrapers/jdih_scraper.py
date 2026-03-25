"""
JDIH Kemendagri Scraper - jdih.kemendagri.go.id
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import json
from datetime import datetime


class JDIHScraper:
    """Scraper untuk JDIH Kemendagri."""
    
    BASE_URL = "https://jdih.kemendagri.go.id"
    
    def __init__(self):
        self.session = None
        self.rate_limit_delay = 1.0  # seconds between requests
    
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
        jenis: str = "",
        tahun: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search peraturan dari JDIH.
        
        Args:
            keyword: Kata kunci pencarian
            jenis: Jenis peraturan (Perda, Perwal, dll)
            tahun: Tahun peraturan
            limit: Max results
        
        Returns:
            List of regulation data
        """
        results = []
        
        try:
            # Build search URL
            params = {'search': keyword}
            if jenis:
                params['jenis'] = jenis
            if tahun:
                params['tahun'] = tahun
            
            async with self.session.get(
                f"{self.BASE_URL}/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Parse results (adjust selector based on actual site structure)
                    items = soup.find_all('div', class_='regulation-item')
                    
                    for item in items[:limit]:
                        reg_data = self._parse_regulation_item(item)
                        if reg_data:
                            results.append(reg_data)
                    
                    await asyncio.sleep(self.rate_limit_delay)
        
        except Exception as e:
            print(f"JDIH scraper error: {e}")
        
        return results
    
    def _parse_regulation_item(self, item) -> Optional[Dict]:
        """Parse single regulation item from HTML."""
        try:
            title = item.find('h4') or item.find('h3')
            link = item.find('a', href=True)
            meta = item.find('div', class_='meta')
            
            return {
                'source': 'jdih.kemendagri.go.id',
                'title': title.get_text(strip=True) if title else 'Unknown',
                'url': f"{self.BASE_URL}{link['href']}" if link else None,
                'metadata': meta.get_text(strip=True) if meta else None,
                'scraped_at': datetime.now().isoformat()
            }
        except Exception:
            return None
    
    async def get_latest_regulations(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get regulations published in last N days."""
        # This would need actual implementation based on site structure
        return await self.search_regulations(limit=20)
