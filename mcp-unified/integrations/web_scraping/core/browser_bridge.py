"""
Generic Browser Bridge - Browser automation dengan Playwright.

Features:
- Headless/headed browser support
- Stealth mode untuk avoid detection
- Rate limiting dan retry logic
- Circuit breaker pattern
- Session management
"""

import asyncio
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from tenacity import retry, stop_after_attempt, wait_exponential


class CircuitBreaker:
    """Circuit breaker pattern untuk fault tolerance."""
    
    def __init__(self, threshold: int = 5, timeout: int = 60):
        self.failure_count = 0
        self.threshold = threshold
        self.timeout = timeout
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = None
    
    def can_execute(self) -> bool:
        """Check apakah boleh eksekusi."""
        if self.state == 'CLOSED':
            return True
        
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
                return True
            return False
        
        return True  # HALF_OPEN
    
    def _should_attempt_reset(self) -> bool:
        """Check apakah sudah waktunya retry."""
        if not self.last_failure_time:
            return True
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout
    
    def record_success(self):
        """Record successful execution."""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def record_failure(self):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.threshold:
            self.state = 'OPEN'


class GenericBrowserBridge:
    """
    Generic browser bridge menggunakan Playwright.
    
    Features:
    - Stealth mode untuk avoid detection
    - Rotating user agents
    - Rate limiting
    - Circuit breaker
    - Automatic retry
    """
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    def __init__(
        self,
        headless: bool = True,
        stealth_mode: bool = True,
        rate_limit_delay: float = 2.0,
        max_retries: int = 3,
        use_circuit_breaker: bool = True
    ):
        """
        Initialize browser bridge.
        
        Args:
            headless: Jalankan browser headless
            stealth_mode: Aktifkan stealth mode
            rate_limit_delay: Delay antar request (detik)
            max_retries: Maksimal retry attempts
            use_circuit_breaker: Gunakan circuit breaker
        """
        self.headless = headless
        self.stealth_mode = stealth_mode
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.use_circuit_breaker = use_circuit_breaker
        
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.circuit_breaker = CircuitBreaker() if use_circuit_breaker else None
        
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize browser dan context.
        
        Returns:
            True jika berhasil
        """
        try:
            self.playwright = await async_playwright().start()
            
            # Browser args
            browser_args = [
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
            
            if self.stealth_mode:
                browser_args.extend([
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ])
            
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=browser_args
            )
            
            # Create context dengan random user agent
            user_agent = random.choice(self.USER_AGENTS)
            
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent,
                locale="en-US",
                timezone_id="America/New_York",
            )
            
            # Stealth scripts
            if self.stealth_mode:
                await self._apply_stealth_scripts()
            
            self._initialized = True
            print(f"[INFO] Browser initialized (UA: {user_agent[:50]}...)")
            return True
            
        except Exception as e:
            print(f"[ERROR] Browser initialization failed: {e}")
            return False
    
    async def _apply_stealth_scripts(self):
        """Apply stealth scripts untuk avoid detection."""
        stealth_script = """
            () => {
                // Override navigator.webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Override plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Hide automation
                delete navigator.__proto__.webdriver;
            }
        """
        
        try:
            page = await self.context.new_page()
            await page.evaluate(stealth_script)
            await page.close()
        except Exception as e:
            print(f"[WARNING] Stealth script failed: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, min=2, max=10)
    )
    async def navigate(self, url: str, wait_until: str = "networkidle") -> Page:
        """
        Navigate ke URL.
        
        Args:
            url: URL tujuan
            wait_until: Wait condition
            
        Returns:
            Playwright Page object
        """
        if not self._initialized:
            raise RuntimeError("Browser not initialized. Call initialize() first.")
        
        if self.circuit_breaker and not self.circuit_breaker.can_execute():
            raise RuntimeError("Circuit breaker is OPEN")
        
        try:
            page = await self.context.new_page()
            
            # Set extra headers
            await page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
            })
            
            # Navigate
            response = await page.goto(
                url,
                wait_until=wait_until,
                timeout=30000
            )
            
            if response:
                print(f"[INFO] Navigated to {url} (Status: {response.status})")
            
            # Rate limiting
            await asyncio.sleep(self.rate_limit_delay)
            
            if self.circuit_breaker:
                self.circuit_breaker.record_success()
            
            return page
            
        except Exception as e:
            print(f"[ERROR] Navigation failed: {e}")
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            raise
    
    async def extract_content(
        self,
        url: str,
        extractor_class,
        **extractor_kwargs
    ) -> Any:
        """
        Navigate dan extract content menggunakan extractor.
        
        Args:
            url: URL target
            extractor_class: Class extractor yang akan digunakan
            **extractor_kwargs: Kwargs untuk extractor
            
        Returns:
            Extracted content
        """
        page = None
        try:
            page = await self.navigate(url)
            
            # Create extractor instance
            extractor = extractor_class(**extractor_kwargs)
            
            # Extract content
            content = await extractor.extract(page)
            
            return content
            
        finally:
            if page:
                await page.close()
    
    async def screenshot(self, page: Page, path: str):
        """Take screenshot dari page."""
        try:
            await page.screenshot(path=path, full_page=True)
            print(f"[INFO] Screenshot saved: {path}")
        except Exception as e:
            print(f"[WARNING] Screenshot failed: {e}")
    
    async def close(self):
        """Cleanup resources."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        
        self._initialized = False
        print("[INFO] Browser closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()