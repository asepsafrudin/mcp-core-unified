import asyncio
from playwright.async_api import async_playwright, Page, BrowserContext
from typing import Optional, Dict, Any

class PlaywrightAdapter:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def start(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"]
            )
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            self.page = await self.context.new_page()

    async def stop(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def navigate(self, url: str, wait_for: str = "load", timeout: int = 25000) -> Dict[str, Any]:
        """Navigate to URL."""
        if not self.page:
            await self.start()
        
        try:
            response = await self.page.goto(url, wait_until=wait_for, timeout=timeout)
            title = await self.page.title()
            return {
                "success": True,
                "url": self.page.url,
                "title": title,
                "http_status": response.status if response else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    async def get_interactive_elements(self) -> list:
        """Simple mock of accessibility tree / interactive elements for snapshot."""
        if not self.page:
            return []
        
        # A simple evaluation to get buttons and links
        elements = await self.page.evaluate('''() => {
            const els = Array.from(document.querySelectorAll('a, button, input, select, textarea'));
            return els.map((el, idx) => ({
                ref: `@e${idx}`,
                role: el.tagName.toLowerCase(),
                name: el.innerText || el.value || el.name || '',
                selector: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''),
                state: el.disabled ? 'disabled' : 'enabled'
            })).slice(0, 100); // limit to 100
        }''')
        return elements

playwright_adapter = PlaywrightAdapter()
