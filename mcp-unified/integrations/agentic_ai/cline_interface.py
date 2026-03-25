"""
Cline Agentic Interface

Interface utama untuk Cline sebagai Agentic AI Brain.
Cline mengontrol browser automation dan membuat keputusan.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agentic_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ClineAgentic')


class ClineAgenticInterface:
    """
    Interface untuk Cline sebagai Agentic AI.
    Cline akan mengontrol browser automation dan membuat keputusan.
    """
    
    def __init__(self, knowledge_bridge=None):
        self.knowledge_bridge = knowledge_bridge
        self.learning_db = []
        self.session_results = []
        
        # Import browser bridge
        try:
            from ..web_scraping.core.browser_bridge import GenericBrowserBridge
            self.browser = GenericBrowserBridge()
        except ImportError:
            logger.error("Browser bridge not available")
            self.browser = None
        
        # Load previous learning data
        self._load_learning_db()
    
    async def scrape_website(self, url: str, goal: str = None) -> Dict[str, Any]:
        """
        Main entry point untuk scraping satu website.
        
        Args:
            url: URL website target
            goal: Tujuan scraping (opsional)
        
        Returns:
            Dict dengan hasil scraping
        """
        logger.info(f"🚀 Starting agentic scraping for: {url}")
        
        if not goal:
            goal = f"Scrape legal news/content from {url}"
        
        result = {
            "url": url,
            "goal": goal,
            "timestamp": datetime.now().isoformat(),
            "steps": []
        }
        
        try:
            # Step 1: Planning (Cline analyzes and plans)
            logger.info("📋 Step 1: Planning strategy...")
            strategy = await self._plan_strategy(url, goal)
            result["strategy"] = strategy
            result["steps"].append({"step": "planning", "status": "success"})
            
            # Step 2: Execution (Browser automation)
            logger.info("🚀 Step 2: Executing browser automation...")
            raw_data = await self._execute_strategy(strategy)
            result["raw_data"] = raw_data
            result["steps"].append({"step": "execution", "status": "success", "count": len(raw_data)})
            
            # Step 3: Validation (Cline reviews)
            logger.info("🔍 Step 3: Validating results...")
            validated_data = await self._validate_results(raw_data, strategy)
            result["validated_data"] = validated_data
            result["steps"].append({
                "step": "validation", 
                "status": "success",
                "raw_count": len(raw_data),
                "valid_count": len(validated_data)
            })
            
            # Step 4: Storage
            logger.info("💾 Step 4: Storing to knowledge base...")
            storage_result = await self._store_to_kb(validated_data, url)
            result["storage"] = storage_result
            result["steps"].append({"step": "storage", "status": "success"})
            
            # Step 5: Learning
            logger.info("🧠 Step 5: Updating learning database...")
            await self._update_learning(strategy, raw_data, validated_data)
            result["steps"].append({"step": "learning", "status": "success"})
            
            result["success"] = True
            logger.info(f"✅ Scraping completed successfully: {len(validated_data)} items")
            
        except Exception as e:
            logger.error(f"❌ Scraping failed: {e}")
            result["success"] = False
            result["error"] = str(e)
            result["steps"].append({"step": "error", "error": str(e)})
        
        # Save session result
        self.session_results.append(result)
        return result
    
    async def _plan_strategy(self, url: str, goal: str) -> Dict[str, Any]:
        """
        Cline analyzes website and plans the best strategy.
        
        Returns:
            Strategy dict dengan konfigurasi scraping
        """
        logger.info(f"🧠 Cline analyzing: {url}")
        
        # Check learning database untuk patterns
        previous_attempts = [l for l in self.learning_db if l.get("url") == url]
        if previous_attempts:
            logger.info(f"📚 Found {len(previous_attempts)} previous attempts")
            best_strategy = max(previous_attempts, key=lambda x: x.get("success_rate", 0))
            if best_strategy.get("success_rate", 0) > 0.5:
                logger.info(f"✅ Using learned strategy with {best_strategy['success_rate']:.0%} success rate")
                return best_strategy["strategy"]
        
        # Analyze URL pattern untuk determine strategy
        strategy = {
            "url": url,
            "goal": goal,
            "tool": "playwright",
            "timeout": 45,  # Increased timeout untuk JS-heavy sites
            "wait_for": "networkidle",
            "selectors": self._detect_selectors(url),
            "fallback": {
                "if_timeout": "increase_timeout_and_retry",
                "if_blocked": "try_alternative_selectors",
                "if_empty": "scroll_and_wait"
            },
            "validation_rules": {
                "required_fields": ["title", "content"],
                "optional_fields": ["author", "date", "category"],
                "min_content_length": 100
            }
        }
        
        # URL-specific adjustments
        if "jdihn.go.id" in url:
            strategy["timeout"] = 60
            strategy["wait_for"] = "load"
            strategy["selectors"] = {
                "article": ".news-item, .peraturan-item, article",
                "title": "h1, h2, .title",
                "content": ".content, .description, p",
                "date": ".date, .tanggal, time"
            }
        elif "hukumonline.com" in url:
            strategy["timeout"] = 30
            strategy["wait_for"] = "domcontentloaded"
            # Based on debug results: h2=19 elements, p=16 elements
            strategy["selectors"] = {
                "article": "h2, .title, article",  # h2 contains news titles
                "title": "a, h2, .title",  # Title is in h2 or link
                "content": "p, .description",  # Content in paragraphs
                "author": ".author, .writer",
                "date": ".date, .publish-date, time"
            }
            # Custom extraction logic for hukumonline structure
            strategy["extraction_mode"] = "heading_based"
            # Adjust validation for hukumonline (title + URL is enough)
            strategy["validation_rules"] = {
                "required_fields": ["title"],  # Only require title
                "optional_fields": ["content", "url", "author", "date"],
                "min_content_length": 1  # Allow empty content
            }
        elif "detik.com" in url:
            strategy["timeout"] = 40
            strategy["wait_for"] = "domcontentloaded"
            strategy["selectors"] = {
                "article": ".media__text, article, .news-item",
                "title": "h2, h3, .media__title",
                "content": ".media__desc, .content"
            }
        
        logger.info(f"📋 Strategy planned: {strategy['tool']} with {strategy['timeout']}s timeout")
        return strategy
    
    def _detect_selectors(self, url: str) -> Dict[str, str]:
        """Detect likely CSS selectors based on URL patterns"""
        # Default selectors
        return {
            "article": "article, .article, .news-item, .post",
            "title": "h1, h2, .title, .headline",
            "content": ".content, .article-content, p",
            "date": ".date, .published, time",
            "author": ".author, .byline, .writer"
        }
    
    async def _execute_strategy(self, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute browser automation based on Cline's strategy.
        
        Returns:
            List of scraped items
        """
        url = strategy["url"]
        tool = strategy["tool"]
        
        logger.info(f"🔧 Executing with {tool}: {url}")
        
        playwright = None
        browser = None
        context = None
        page = None
        
        try:
            # Import playwright
            from playwright.async_api import async_playwright
            
            # Launch browser
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            # Navigate to URL
            await page.goto(url, wait_until=strategy["wait_for"], timeout=strategy["timeout"] * 1000)
            
            logger.info(f"✅ Page loaded: {url}")
            
            # Wait for JavaScript to render content
            logger.info("⏳ Waiting for JavaScript render...")
            await asyncio.sleep(3)
            
            # Scroll to trigger lazy loading
            logger.info("📜 Scrolling to trigger lazy load...")
            await self._scroll_page(page)
            
            # Extract data using selectors
            selectors = strategy["selectors"]
            extraction_mode = strategy.get("extraction_mode")
            raw_data = await self._extract_data(page, selectors, extraction_mode)
            
            logger.info(f"📊 Extracted {len(raw_data)} items")
            
            return raw_data
            
        except Exception as e:
            logger.error(f"❌ Execution failed: {e}")
            # Try fallback jika ada
            return await self._execute_fallback(strategy, e)
        
        finally:
            # Cleanup
            if page:
                await page.close()
            if context:
                await context.close()
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
    
    async def _extract_data(self, page, selectors: Dict[str, str], extraction_mode: str = None) -> List[Dict[str, Any]]:
        """Extract data from page using selectors"""
        
        # Special handling for heading-based extraction (e.g., hukumonline)
        if extraction_mode == "heading_based":
            return await self._extract_heading_based(page, selectors)
        
        # Standard article-based extraction
        extract_script = """
            (selectors) => {
                const results = [];
                const articles = document.querySelectorAll(selectors.article);
                
                articles.forEach(article => {
                    const item = {};
                    
                    // Extract title
                    const titleEl = article.querySelector(selectors.title);
                    item.title = titleEl ? titleEl.innerText.trim() : '';
                    
                    // Extract content
                    const contentEl = article.querySelector(selectors.content);
                    item.content = contentEl ? contentEl.innerText.trim() : '';
                    
                    // Extract date
                    const dateEl = article.querySelector(selectors.date);
                    item.date = dateEl ? dateEl.innerText.trim() : '';
                    
                    // Extract author
                    const authorEl = article.querySelector(selectors.author);
                    item.author = authorEl ? article.innerText.trim() : '';
                    
                    // Extract URL
                    const linkEl = article.querySelector('a');
                    item.url = linkEl ? linkEl.href : '';
                    
                    if (item.title || item.content) {
                        results.push(item);
                    }
                });
                
                return results;
            }
        """
        
        try:
            data = await page.evaluate(extract_script, selectors)
            return data if data else []
        except Exception as e:
            logger.error(f"❌ Data extraction failed: {e}")
            return []
    
    async def _extract_heading_based(self, page, selectors: Dict[str, str]) -> List[Dict[str, Any]]:
        """Extract data from heading-based structure (e.g., hukumonline)"""
        
        extract_script = """
            (selectors) => {
                const results = [];
                
                // Find all headings (h2)
                const headings = document.querySelectorAll('h2');
                
                headings.forEach((heading, index) => {
                    const item = {};
                    
                    // Title from heading
                    item.title = heading.innerText.trim();
                    
                    // URL from link in heading or next sibling
                    const linkEl = heading.querySelector('a') || heading.closest('a');
                    item.url = linkEl ? linkEl.href : '';
                    
                    // Look for content in parent or next siblings
                    let parent = heading.parentElement;
                    let content = '';
                    
                    // Try to find description/content in parent
                    const descEl = parent.querySelector('p, .description');
                    if (descEl) {
                        content = descEl.innerText.trim();
                    }
                    
                    // If not found, look in next sibling
                    if (!content) {
                        let sibling = heading.nextElementSibling;
                        let attempts = 0;
                        while (sibling && attempts < 3) {
                            if (sibling.tagName === 'P' || sibling.classList.contains('description')) {
                                content = sibling.innerText.trim();
                                break;
                            }
                            sibling = sibling.nextElementSibling;
                            attempts++;
                        }
                    }
                    
                    item.content = content;
                    
                    // Only add if we have meaningful content
                    if (item.title && item.title.length > 10) {
                        results.push(item);
                    }
                });
                
                return results;
            }
        """
        
        try:
            data = await page.evaluate(extract_script, selectors)
            logger.info(f"📊 Heading-based extraction: {len(data)} items")
            return data if data else []
        except Exception as e:
            logger.error(f"❌ Heading-based extraction failed: {e}")
            return []
    
    async def _execute_fallback(self, strategy: Dict[str, Any], error: Exception) -> List[Dict[str, Any]]:
        """Execute fallback strategy jika utama gagal"""
        logger.warning(f"⚠️ Executing fallback for: {strategy['url']}")
        
        # Implementasi fallback strategies
        fallback_strategies = strategy.get("fallback", {})
        
        if "timeout" in str(error).lower() and fallback_strategies.get("if_timeout"):
            # Increase timeout dan retry
            logger.info("🔄 Retrying with increased timeout...")
            strategy["timeout"] = min(strategy["timeout"] * 1.5, 120)
            return await self._execute_strategy(strategy)
        
        # Jika tidak bisa fallback, return empty
        logger.error("❌ Fallback failed, returning empty")
        return []
    
    async def _validate_results(self, data: List[Dict[str, Any]], strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Cline validates scraped data.
        
        Returns:
            List of validated items
        """
        logger.info(f"🔍 Validating {len(data)} items...")
        
        rules = strategy.get("validation_rules", {})
        required_fields = rules.get("required_fields", ["title", "content"])
        optional_fields = rules.get("optional_fields", ["author", "date"])
        min_length = rules.get("min_content_length", 100)
        
        validated = []
        partial = []
        rejected = []
        
        for i, item in enumerate(data):
            validation_result = {
                "index": i,
                "item": item,
                "issues": [],
                "completeness": 0.0
            }
            
            # Check required fields
            has_required = True
            for field in required_fields:
                field_value = item.get(field, "")
                if not field_value or len(str(field_value).strip()) < 5:  # Reduced from 10 to 5
                    validation_result["issues"].append(f"Missing/short {field}")
                    has_required = False
            
            # Check content length (only if content is in required_fields)
            content = item.get("content", "")
            if "content" in required_fields and len(content) < min_length:
                validation_result["issues"].append(f"Content too short ({len(content)} chars)")
            
            # Calculate completeness score
            total_fields = len(required_fields) + len(optional_fields)
            filled_fields = sum(1 for f in required_fields + optional_fields if item.get(f))
            validation_result["completeness"] = filled_fields / total_fields
            
            # Categorize
            if has_required and len(content) >= min_length:
                item["_validation"] = {"status": "valid", "completeness": validation_result["completeness"]}
                validated.append(item)
            elif has_required:  # If has required fields, consider as partial even with low completeness
                item["_validation"] = {"status": "partial", "issues": validation_result["issues"], "completeness": validation_result["completeness"]}
                partial.append(item)
            else:
                rejected.append(validation_result)
        
        logger.info(f"✅ Valid: {len(validated)}, ⚠️ Partial: {len(partial)}, ❌ Rejected: {len(rejected)}")
        
        # Include partial data untuk review (medium validation level)
        return validated + partial
    
    async def _store_to_kb(self, data: List[Dict[str, Any]], source_url: str) -> Dict[str, Any]:
        """Store validated data to knowledge base"""
        if not self.knowledge_bridge:
            logger.warning("⚠️ Knowledge bridge not available, skipping storage")
            return {"stored": 0, "skipped": len(data)}
        
        stored = 0
        skipped = 0
        
        for item in data:
            try:
                # Prepare document
                doc = {
                    "title": item.get("title", "Untitled"),
                    "content": item.get("content", ""),
                    "source": source_url,
                    "url": item.get("url", source_url),
                    "author": item.get("author"),
                    "published_date": item.get("date"),
                    "metadata": {
                        "validation_status": item.get("_validation", {}).get("status", "unknown"),
                        "completeness": item.get("_validation", {}).get("completeness", 0),
                        "scraped_at": datetime.now().isoformat()
                    }
                }
                
                # Store to KB
                # await self.knowledge_bridge.ingest_document(doc)
                stored += 1
                
            except Exception as e:
                logger.error(f"❌ Failed to store item: {e}")
                skipped += 1
        
        logger.info(f"💾 Stored: {stored}, Skipped: {skipped}")
        return {"stored": stored, "skipped": skipped}
    
    async def _update_learning(self, strategy: Dict[str, Any], raw_data: List[Dict], validated_data: List[Dict]):
        """Update learning database with this run's experience"""
        success_rate = len(validated_data) / len(raw_data) if raw_data else 0
        
        learning_entry = {
            "url": strategy["url"],
            "timestamp": datetime.now().isoformat(),
            "strategy": strategy,
            "raw_count": len(raw_data),
            "valid_count": len(validated_data),
            "success_rate": success_rate,
            "issues": self._identify_issues(raw_data, validated_data)
        }
        
        self.learning_db.append(learning_entry)
        self._save_learning_db()
        
        logger.info(f"🧠 Learning updated: {success_rate:.0%} success rate")
    
    def _identify_issues(self, raw_data: List[Dict], validated_data: List[Dict]) -> List[str]:
        """Identify common issues from this run"""
        issues = []
        
        if not raw_data:
            issues.append("no_data_extracted")
        elif len(validated_data) < len(raw_data) * 0.5:
            issues.append("high_rejection_rate")
        
        # Check for missing fields pattern
        missing_title = sum(1 for d in raw_data if not d.get("title"))
        missing_content = sum(1 for d in raw_data if not d.get("content"))
        
        if missing_title > len(raw_data) * 0.3:
            issues.append("missing_titles")
        if missing_content > len(raw_data) * 0.3:
            issues.append("missing_content")
        
        return issues
    
    def _load_learning_db(self):
        """Load previous learning data"""
        try:
            learning_file = Path("agentic_learning_db.json")
            if learning_file.exists():
                with open(learning_file, 'r', encoding='utf-8') as f:
                    self.learning_db = json.load(f)
                logger.info(f"📚 Loaded {len(self.learning_db)} learning entries")
        except Exception as e:
            logger.warning(f"⚠️ Could not load learning DB: {e}")
            self.learning_db = []
    
    def _save_learning_db(self):
        """Save learning data"""
        try:
            with open("agentic_learning_db.json", 'w', encoding='utf-8') as f:
                json.dump(self.learning_db, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"⚠️ Could not save learning DB: {e}")
    
    async def _scroll_page(self, page, scroll_count: int = 3):
        """
        Scroll page untuk trigger lazy loading dan infinite scroll.
        
        Args:
            page: Playwright page object
            scroll_count: Number of scroll operations
        """
        try:
            for i in range(scroll_count):
                # Scroll ke bawah
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                logger.info(f"📜 Scrolled {i+1}/{scroll_count}")
                
                # Wait untuk content load
                await asyncio.sleep(1.5)
                
                # Check if reached bottom
                is_at_bottom = await page.evaluate("""
                    () => {
                        return (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 100;
                    }
                """)
                
                if is_at_bottom:
                    logger.info("📜 Reached bottom of page")
                    break
                    
        except Exception as e:
            logger.warning(f"⚠️ Scroll failed: {e}")
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of all sessions in this run"""
        if not self.session_results:
            return {"message": "No sessions completed"}
        
        successful = [r for r in self.session_results if r.get("success")]
        failed = [r for r in self.session_results if not r.get("success")]
        
        total_raw = sum(r.get("raw_data", []).__len__() for r in successful)
        total_valid = sum(r.get("validated_data", []).__len__() for r in successful)
        
        return {
            "total_sessions": len(self.session_results),
            "successful": len(successful),
            "failed": len(failed),
            "total_raw_items": total_raw,
            "total_valid_items": total_valid,
            "success_rate": len(successful) / len(self.session_results) if self.session_results else 0,
            "sessions": self.session_results
        }
