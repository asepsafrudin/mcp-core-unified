"""
Knowledge Bridge Integration

Integrasi Extractor System dengan AgentKnowledgeBridge.
Auto-save hasil scraping ke knowledge database.
"""

import asyncio
import hashlib
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

# Setup path untuk imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.profiles.legal.connectors.agent_knowledge_bridge import (
    AgentKnowledgeBridge, get_knowledge_bridge
)
from extractors.base_extractor import BaseExtractor

logger = logging.getLogger('KnowledgeBridgeIntegration')


def extraction_doc_id(source: str, item: Dict[str, Any], index: int, base_url: str) -> str:
    """
    ID dokumen stabil per item: utama dari URL artikel (re-run update row yang sama di pgvector).
    Fallback: hash dari source + base_url + title + index jika URL kosong.
    """
    item_url = (item.get("url") or "").strip()
    if item_url:
        h = hashlib.sha256(item_url.encode("utf-8")).hexdigest()[:16]
        return f"ext_{source}_{h}"
    key = f"{source}|{base_url}|{item.get('title', '')}|{index}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"ext_{source}_{h}"


class ExtractorKnowledgeBridge:
    """
    Bridge antara Extractor System dan Knowledge Base.
    
    Features:
    - Auto-save extraction results ke database
    - Categorize by source (JDIH, Kemenkeu, dll)
    - Deduplication before saving
    - Batch processing
    """
    
    def __init__(self, knowledge_bridge: AgentKnowledgeBridge = None):
        self.kb = knowledge_bridge or get_knowledge_bridge()
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize knowledge bridge"""
        if not self._initialized:
            self._initialized = await self.kb.initialize()
            if self._initialized:
                logger.info("✅ Knowledge Bridge initialized")
            else:
                logger.error("❌ Failed to initialize Knowledge Bridge")
        return self._initialized
    
    async def save_extraction_results(
        self,
        results: List[Dict[str, Any]],
        source: str,
        url: str,
        namespace: str = "legal_regulations"
    ) -> Dict[str, Any]:
        """
        Save extraction results ke knowledge base.
        
        Args:
            results: List of extracted items
            source: Source name (e.g., "kemenkeu", "jdih")
            url: Source URL
            namespace: Database namespace
            
        Returns:
            Summary dict dengan stats
        """
        if not self._initialized:
            await self.initialize()
        
        if not results:
            logger.warning(f"⚠️ No results to save from {source}")
            return {"saved": 0, "skipped": 0, "errors": 0, "total": 0}
        
        saved = 0
        skipped = 0
        errors = 0
        
        for i, item in enumerate(results):
            try:
                doc_id = extraction_doc_id(source, item, i, url)
                
                # Prepare content
                content_parts = [
                    f"Title: {item.get('title', 'N/A')}",
                    f"Source: {source}",
                    f"URL: {item.get('url', url)}",
                ]
                
                if item.get('number'):
                    content_parts.append(f"Number: {item.get('number')}")
                if item.get('date'):
                    content_parts.append(f"Date: {item.get('date')}")
                if item.get('type'):
                    content_parts.append(f"Type: {item.get('type')}")
                if item.get('content'):
                    content_parts.append(f"Content: {item.get('content')}")
                
                content = "\n".join(content_parts)
                
                # Prepare metadata
                metadata = {
                    "source": source,
                    "source_url": url,
                    "extracted_at": datetime.now().isoformat(),
                    "type": "regulation",
                    "regulation_type": item.get("type", "unknown"),
                    "number": item.get("number", ""),
                    "date": item.get("date", ""),
                    "url": item.get("url", ""),
                    "doc_id_scheme": "url_sha256_v1",
                }
                
                # Save to knowledge base
                success = await self.kb.add_to_database(
                    doc_id=doc_id,
                    content=content,
                    metadata=metadata,
                    namespace=namespace
                )
                
                if success:
                    saved += 1
                    logger.debug(f"✅ Saved: {doc_id}")
                else:
                    skipped += 1
                    logger.warning(f"⚠️ Skipped: {doc_id}")
                    
            except Exception as e:
                errors += 1
                logger.error(f"❌ Error saving item {i}: {e}")
        
        summary = {
            "saved": saved,
            "skipped": skipped,
            "errors": errors,
            "total": len(results),
            "source": source,
            "namespace": namespace,
        }
        
        logger.info(
            f"📊 Knowledge Bridge Save Summary: "
            f"{saved} saved, {skipped} skipped, {errors} errors"
        )
        
        return summary
    
    async def save_single_item(
        self,
        item: Dict[str, Any],
        source: str,
        namespace: str = "legal_regulations"
    ) -> bool:
        """
        Save single item ke knowledge base.
        
        Args:
            item: Single extracted item
            source: Source name
            namespace: Database namespace
            
        Returns:
            True jika berhasil
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            base_url = item.get("source_page_url") or item.get("url") or ""
            doc_id = extraction_doc_id(source, item, 0, base_url)
            
            # Prepare content
            content = f"""Title: {item.get('title', 'N/A')}
Source: {source}
URL: {item.get('url', 'N/A')}
Number: {item.get('number', 'N/A')}
Date: {item.get('date', 'N/A')}
Type: {item.get('type', 'N/A')}
Content: {item.get('content', 'N/A')}"""
            
            # Metadata
            metadata = {
                "source": source,
                "type": "regulation",
                "extracted_at": datetime.now().isoformat(),
                "doc_id_scheme": "url_sha256_v1",
                **{k: v for k, v in item.items() if v}
            }
            
            return await self.kb.add_to_database(
                doc_id=doc_id,
                content=content,
                metadata=metadata,
                namespace=namespace
            )
            
        except Exception as e:
            logger.error(f"❌ Error saving single item: {e}")
            return False
    
    async def search_saved_results(
        self,
        query: str,
        namespace: str = "legal_regulations",
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search saved extraction results.
        
        Args:
            query: Search query
            namespace: Database namespace
            top_k: Number of results
            
        Returns:
            List of matching results
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            result = await self.kb.query_database(
                query=query,
                namespace=namespace,
                top_k=top_k
            )
            
            if result and result.success:
                return result.sources
            return []
            
        except Exception as e:
            logger.error(f"❌ Error searching: {e}")
            return []
    
    async def get_stats(self, namespace: str = "legal_regulations") -> Dict[str, Any]:
        """
        Get statistics dari knowledge base.
        
        Args:
            namespace: Database namespace
            
        Returns:
            Stats dict
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            documents = await self.kb.list_database_documents(
                namespace=namespace,
                limit=1000
            )
            
            # Group by source
            sources = {}
            for doc in documents:
                source = doc.get("metadata", {}).get("source", "unknown")
                sources[source] = sources.get(source, 0) + 1
            
            return {
                "total_documents": len(documents),
                "namespace": namespace,
                "sources": sources,
                "by_source": sources
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting stats: {e}")
            return {"total_documents": 0, "error": str(e)}


# Convenience function
async def save_extraction_results(
    results: List[Dict[str, Any]],
    source: str,
    url: str,
    namespace: str = "legal_regulations"
) -> Dict[str, Any]:
    """
    Convenience function untuk save results tanpa setup.
    
    Usage:
        summary = await save_extraction_results(
            results=[{"title": "...", "url": "..."}],
            source="kemenkeu",
            url="https://jdih.kemenkeu.go.id"
        )
    """
    bridge = ExtractorKnowledgeBridge()
    return await bridge.save_extraction_results(
        results=results,
        source=source,
        url=url,
        namespace=namespace
    )
