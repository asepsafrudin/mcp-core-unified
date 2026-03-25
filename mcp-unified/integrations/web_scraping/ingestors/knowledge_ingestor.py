"""
Web Scraping Knowledge Ingestor - Integration dengan AgentKnowledgeBridge.

Menghubungkan hasil scraping ke knowledge base dengan:
- Automatic extractor selection
- 4-Level validation
- Provenance tracking
- Versioned memory
"""

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

# Import extractors
from ..core.extractors.base_extractor import BaseExtractor, ExtractedContent
from ..core.extractors.perplexity_extractor import PerplexityExtractor
from ..core.extractors.jdih_extractor import JDIHExtractor
from ..core.extractors.news_extractor import NewsExtractor
from ..core.extractors.generic_extractor import GenericExtractor

# Import validator
from ..core.validators.four_level_validator import FourLevelValidator, ValidationResult

# Import browser bridge
from ..core.browser_bridge import GenericBrowserBridge


class WebScrapingIngestor:
    """
    Main ingestor untuk web scraping knowledge.
    
    Orchestrates:
    1. URL analysis untuk extractor selection
    2. Browser automation
    3. Content extraction
    4. Validation
    5. Storage ke knowledge base
    """
    
    # Registry of extractors (ordered by priority)
    EXTRACTORS: List[Type[BaseExtractor]] = [
        PerplexityExtractor,
        JDIHExtractor,
        NewsExtractor,
        GenericExtractor,  # Fallback
    ]
    
    def __init__(
        self,
        knowledge_bridge=None,
        namespace: str = "web_scraping",
        validator: Optional[FourLevelValidator] = None,
        browser_bridge: Optional[GenericBrowserBridge] = None,
    ):
        """
        Initialize ingestor.
        
        Args:
            knowledge_bridge: AgentKnowledgeBridge instance
            namespace: Default namespace untuk storage
            validator: FourLevelValidator instance
            browser_bridge: GenericBrowserBridge instance
        """
        self.knowledge_bridge = knowledge_bridge
        self.namespace = namespace
        self.validator = validator or FourLevelValidator()
        self.browser = browser_bridge
        
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize ingestor dan dependencies."""
        try:
            # Initialize browser jika belum ada
            if not self.browser:
                self.browser = GenericBrowserBridge()
                await self.browser.initialize()
            
            # Initialize knowledge bridge jika ada
            if self.knowledge_bridge and hasattr(self.knowledge_bridge, 'initialize'):
                await self.knowledge_bridge.initialize()
            
            self._initialized = True
            print("[INFO] WebScrapingIngestor initialized")
            return True
            
        except Exception as e:
            print(f"[ERROR] Ingestor initialization failed: {e}")
            return False
    
    def select_extractor(self, url: str) -> Optional[Type[BaseExtractor]]:
        """
        Select appropriate extractor untuk URL.
        
        Args:
            url: Target URL
            
        Returns:
            Extractor class atau None
        """
        for extractor_class in self.EXTRACTORS:
            try:
                extractor = extractor_class()
                if extractor.can_handle(url):
                    return extractor_class
            except Exception:
                continue
        
        return None
    
    async def scrape_and_ingest(
        self,
        url: str,
        domain: Optional[str] = None,
        tags: Optional[List[str]] = None,
        validate: bool = True,
        skip_validation: bool = False,
    ) -> Dict[str, Any]:
        """
        Scrape URL dan ingest ke knowledge base.
        
        Args:
            url: URL target
            domain: Legal domain (e.g., "hukum_perdata")
            tags: List of tags
            validate: Whether to validate content
            skip_validation: Skip validation entirely
            
        Returns:
            Result dict dengan status dan metadata
        """
        if not self._initialized:
            raise RuntimeError("Ingestor not initialized. Call initialize() first.")
        
        start_time = datetime.now()
        
        try:
            # Step 1: Select extractor
            extractor_class = self.select_extractor(url)
            if not extractor_class:
                return {
                    "success": False,
                    "error": "No suitable extractor found for URL",
                    "url": url,
                }
            
            print(f"[INFO] Using {extractor_class.__name__} for {url}")
            
            # Step 2: Extract content
            content = await self.browser.extract_content(
                url=url,
                extractor_class=extractor_class
            )
            
            if not content:
                return {
                    "success": False,
                    "error": "Extraction returned empty content",
                    "url": url,
                }
            
            # Step 3: Validate content
            validation_result = None
            if validate and not skip_validation:
                validation_result = await self.validator.validate(content)
                
                if not validation_result.should_store:
                    return {
                        "success": False,
                        "error": "Content failed validation",
                        "url": url,
                        "validation": validation_result,
                    }
                
                print(f"[INFO] Validation score: {validation_result.overall_score:.2f}")
            
            # Step 4: Store ke knowledge base
            if self.knowledge_bridge:
                doc_id = await self._store_content(
                    content=content,
                    domain=domain,
                    tags=tags,
                    validation=validation_result,
                )
                
                elapsed = (datetime.now() - start_time).total_seconds()
                
                return {
                    "success": True,
                    "doc_id": doc_id,
                    "url": url,
                    "title": content.title,
                    "extractor": extractor_class.__name__,
                    "validation_score": validation_result.overall_score if validation_result else None,
                    "requires_review": validation_result.requires_human_review if validation_result else False,
                    "elapsed_seconds": elapsed,
                }
            else:
                # Return content without storing
                return {
                    "success": True,
                    "content": content,
                    "url": url,
                    "extractor": extractor_class.__name__,
                    "stored": False,
                }
                
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"[ERROR] Scrape and ingest failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "url": url,
                "elapsed_seconds": elapsed,
            }
    
    async def scrape_batch(
        self,
        urls: List[str],
        domain: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scrape multiple URLs.
        
        Args:
            urls: List of URLs
            domain: Legal domain
            tags: Tags
            
        Returns:
            List of results
        """
        results = []
        
        for i, url in enumerate(urls, 1):
            print(f"[INFO] Processing {i}/{len(urls)}: {url}")
            
            result = await self.scrape_and_ingest(
                url=url,
                domain=domain,
                tags=tags,
            )
            
            results.append(result)
        
        # Summary
        successful = sum(1 for r in results if r.get('success'))
        print(f"[INFO] Batch complete: {successful}/{len(urls)} successful")
        
        return results
    
    async def _store_content(
        self,
        content: ExtractedContent,
        domain: Optional[str],
        tags: Optional[List[str]],
        validation: Optional[ValidationResult],
    ) -> str:
        """
        Store content ke knowledge base.
        
        Args:
            content: Extracted content
            domain: Legal domain
            tags: Tags
            validation: Validation result
            
        Returns:
            Document ID
        """
        # Generate doc_id
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        content_hash = hashlib.sha256(content.url.encode()).hexdigest()[:8]
        doc_id = f"web_{domain or 'general'}_{timestamp}_{content_hash}"
        
        # Build metadata
        metadata = {
            "source_type": content.metadata.get("source_type", "web"),
            "source_url": content.url,
            "extracted_at": content.extracted_at.isoformat(),
            "domain": domain,
            "tags": tags or [],
        }
        
        # Add extractor-specific metadata
        metadata.update(content.metadata)
        
        # Add validation info
        if validation:
            metadata["validation"] = {
                "overall_score": validation.overall_score,
                "level_results": validation.level_results,
                "requires_human_review": validation.requires_human_review,
            }
        
        # Add author if available
        if content.author:
            metadata["author"] = content.author
        
        # Add date if available
        if content.published_date:
            metadata["published_date"] = content.published_date.isoformat()
        
        # Store menggunakan AgentKnowledgeBridge
        if hasattr(self.knowledge_bridge, 'add_to_database'):
            await self.knowledge_bridge.add_to_database(
                doc_id=doc_id,
                content=content.content,
                metadata=metadata,
                namespace=self.namespace,
            )
        elif hasattr(self.knowledge_bridge, 'add_document'):
            await self.knowledge_bridge.add_document(
                doc_id=doc_id,
                content=content.content,
                metadata=metadata,
                namespace=self.namespace,
            )
        
        print(f"[INFO] Stored as {doc_id}")
        return doc_id
    
    async def close(self):
        """Cleanup resources."""
        if self.browser:
            await self.browser.close()
        
        self._initialized = False
        print("[INFO] WebScrapingIngestor closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()