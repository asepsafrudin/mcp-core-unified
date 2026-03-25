#!/usr/bin/env python3
"""
DMS Knowledge Connector
=======================
Connector untuk mengintegrasikan Document Management System (DMS)
dengan Agent Knowledge Bridge di MCP Unified.

Menyediakan akses ke:
- Full-text search dari SQLite FTS
- Auto-labeling metadata (jenis dokumen, instansi, tahun)
- OCR content dari dokumen
- Multi-source documents (OneDrive, Google Drive, Local)
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# Add DMS to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent.parent / 'src'))

from document_management.core.database import DatabaseManager, get_db
from document_management.core.config import SQLITE_PATH


@dataclass
class DMSQueryResult:
    """Result dari DMS query"""
    success: bool
    query: str
    documents: List[Dict[str, Any]] = field(default_factory=list)
    total_found: int = 0
    context: str = ""
    error: Optional[str] = None


class DMSKnowledgeConnector:
    """
    Connector untuk Document Management System.
    
    Usage:
        connector = DMSKnowledgeConnector()
        
        # Search documents
        result = await connector.search("UU tentang desa")
        
        # Search with filters
        result = await connector.search(
            "peraturan",
            filters={"jenis_dokumen": "Undang-Undang", "tahun": "2023"}
        )
        
        # Get document dengan content
        doc = await connector.get_document(doc_id=123)
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(SQLITE_PATH)
        self.db = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize DMS connector"""
        try:
            self.db = DatabaseManager(Path(self.db_path))
            self._initialized = True
            print(f"✅ DMS Connector initialized: {self.db_path}")
            return True
        except Exception as e:
            print(f"❌ DMS Connector init failed: {e}")
            return False
    
    async def search(
        self,
        query: str,
        filters: Dict[str, str] = None,
        top_k: int = 5,
        include_content: bool = True
    ) -> DMSQueryResult:
        """
        Search documents di DMS.
        
        Args:
            query: Search query (FTS)
            filters: Optional filters (jenis_dokumen, instansi, tahun, dll)
            top_k: Maximum results
            include_content: Include full text content
        
        Returns:
            DMSQueryResult
        """
        if not self._initialized:
            success = await self.initialize()
            if not success:
                return DMSQueryResult(
                    success=False,
                    query=query,
                    error="DMS connector not initialized"
                )
        
        try:
            # Search dengan FTS
            results = self.db.search_documents(query, limit=top_k * 2)  # Get more for filtering
            
            # Apply filters if provided
            if filters:
                results = self._apply_filters(results, filters)
            
            # Limit to top_k
            results = results[:top_k]
            
            # Enrich dengan content dan labels
            enriched_results = []
            for doc in results:
                enriched_doc = await self._enrich_document(doc, include_content)
                enriched_results.append(enriched_doc)
            
            # Build context untuk LLM
            context = self._build_context(enriched_results)
            
            return DMSQueryResult(
                success=True,
                query=query,
                documents=enriched_results,
                total_found=len(enriched_results),
                context=context
            )
            
        except Exception as e:
            return DMSQueryResult(
                success=False,
                query=query,
                error=str(e)
            )
    
    async def get_document(self, doc_id: int, include_content: bool = True) -> Optional[Dict]:
        """
        Get document by ID dengan metadata lengkap.
        
        Args:
            doc_id: Document ID
            include_content: Include extracted text
        
        Returns:
            Document dict atau None
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            doc = self.db.get_document_by_id(doc_id)
            if not doc:
                return None
            
            return await self._enrich_document(doc, include_content)
            
        except Exception as e:
            print(f"❌ Error getting document {doc_id}: {e}")
            return None
    
    async def get_documents_by_label(
        self,
        label_type: str,
        label_value: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get documents by label.
        
        Args:
            label_type: jenis_dokumen, instansi, tahun, dll
            label_value: Value untuk label
            limit: Maximum results
        
        Returns:
            List of documents
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    SELECT d.*, s.source_name
                    FROM file_documents d
                    JOIN file_sources s ON d.source_id = s.id
                    JOIN document_labels l ON d.id = l.document_id
                    WHERE l.label_type = ? AND l.label_value = ?
                    ORDER BY d.indexed_at DESC
                    LIMIT ?
                """, (label_type, label_value, limit))
                
                results = [dict(row) for row in cursor.fetchall()]
                
                # Enrich dengan labels
                for doc in results:
                    doc['labels'] = self.db.get_document_labels(doc['id'])
                
                return results
                
        except Exception as e:
            print(f"❌ Error getting documents by label: {e}")
            return []
    
    async def get_documents_by_metadata(
        self,
        jenis_dokumen: str = None,
        instansi: str = None,
        tahun: int = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get documents by government metadata.
        
        Args:
            jenis_dokumen: UU, PP, PERPRES, dll
            instansi: KEMENKUMHAM, KEMENKEU, dll
            tahun: Tahun dokumen
            limit: Maximum results
        
        Returns:
            List of documents
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            conditions = []
            params = []
            
            if jenis_dokumen:
                conditions.append("g.jenis_dokumen LIKE ?")
                params.append(f"%{jenis_dokumen}%")
            
            if instansi:
                conditions.append("g.instansi_pembuat LIKE ?")
                params.append(f"%{instansi}%")
            
            if tahun:
                conditions.append("g.tahun_dokumen = ?")
                params.append(tahun)
            
            if not conditions:
                return []
            
            where_clause = " AND ".join(conditions)
            params.append(limit)
            
            with self.db.get_cursor() as cursor:
                cursor.execute(f"""
                    SELECT d.*, g.jenis_dokumen, g.instansi_pembuat, 
                           g.tahun_dokumen, g.nomor_dokumen, g.tentang
                    FROM file_documents d
                    JOIN government_metadata g ON d.id = g.document_id
                    WHERE {where_clause}
                    ORDER BY g.tahun_dokumen DESC
                    LIMIT ?
                """, params)
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"❌ Error getting documents by metadata: {e}")
            return []
    
    async def get_recent_documents(self, limit: int = 10) -> List[Dict]:
        """Get recent documents"""
        if not self._initialized:
            await self.initialize()
        
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    SELECT d.*, s.source_name
                    FROM file_documents d
                    JOIN file_sources s ON d.source_id = s.id
                    ORDER BY d.indexed_at DESC
                    LIMIT ?
                """, (limit,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"❌ Error getting recent documents: {e}")
            return []
    
    async def get_statistics(self) -> Dict:
        """Get DMS statistics"""
        if not self._initialized:
            await self.initialize()
        
        return self.db.get_stats()
    
    async def _enrich_document(self, doc: Dict, include_content: bool = True) -> Dict:
        """Enrich document dengan labels dan content"""
        doc_id = doc['id']
        
        # Get labels
        labels = self.db.get_document_labels(doc_id)
        doc['labels'] = labels
        
        # Build label dict untuk easy access
        label_dict = {}
        for label in labels:
            label_dict[label['label_type']] = label['label_value']
        doc['label_dict'] = label_dict
        
        # Get content if requested
        if include_content:
            content = self.db.get_document_content(doc_id)
            if content:
                doc['content'] = content.get('extracted_text', '')
                doc['ocr_confidence'] = content.get('ocr_confidence')
                doc['ocr_engine'] = content.get('ocr_engine')
        
        # Get government metadata
        gov_meta = self.db.get_government_metadata(doc_id)
        if gov_meta:
            doc['government_metadata'] = gov_meta
        
        return doc
    
    def _apply_filters(self, results: List[Dict], filters: Dict) -> List[Dict]:
        """Apply filters ke search results"""
        filtered = []
        
        for doc in results:
            match = True
            
            # Check each filter
            for key, value in filters.items():
                if key == 'jenis_dokumen':
                    # Check labels
                    labels = self.db.get_document_labels(doc['id'])
                    jenis_values = [l['label_value'] for l in labels if l['label_type'] == 'jenis_dokumen']
                    if value not in jenis_values:
                        match = False
                        break
                
                elif key == 'instansi':
                    labels = self.db.get_document_labels(doc['id'])
                    instansi_values = [l['label_value'] for l in labels if l['label_type'] == 'instansi']
                    if value not in instansi_values:
                        match = False
                        break
                
                elif key == 'tahun':
                    labels = self.db.get_document_labels(doc['id'])
                    tahun_values = [l['label_value'] for l in labels if l['label_type'] == 'tahun']
                    if str(value) not in tahun_values:
                        match = False
                        break
                
                elif key == 'category':
                    if doc.get('category') != value:
                        match = False
                        break
                
                elif key == 'source':
                    if doc.get('source_name') != value:
                        match = False
                        break
            
            if match:
                filtered.append(doc)
        
        return filtered
    
    def _build_context(self, documents: List[Dict]) -> str:
        """Build context string untuk LLM dari documents"""
        if not documents:
            return ""
        
        context_parts = ["=== Dokumen dari Document Management System ===\n"]
        
        for i, doc in enumerate(documents, 1):
            # Header
            context_parts.append(f"\n[{i}] {doc.get('file_name', 'Unknown')}")
            
            # Labels
            labels = doc.get('label_dict', {})
            if labels:
                label_str = " | ".join([f"{k}={v}" for k, v in labels.items()])
                context_parts.append(f"    Label: {label_str}")
            
            # Metadata
            gov = doc.get('government_metadata', {})
            if gov:
                meta_parts = []
                if gov.get('jenis_dokumen'):
                    meta_parts.append(f"Jenis: {gov['jenis_dokumen']}")
                if gov.get('nomor_dokumen'):
                    meta_parts.append(f"Nomor: {gov['nomor_dokumen']}")
                if gov.get('tahun_dokumen'):
                    meta_parts.append(f"Tahun: {gov['tahun_dokumen']}")
                if gov.get('instansi_pembuat'):
                    meta_parts.append(f"Instansi: {gov['instansi_pembuat']}")
                if meta_parts:
                    context_parts.append(f"    {' | '.join(meta_parts)}")
            
            # Content preview
            content = doc.get('content', '')
            if content:
                preview = content[:500].replace('\n', ' ')
                context_parts.append(f"    Konten: {preview}...")
            
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    async def close(self):
        """Cleanup resources"""
        if self.db:
            # SQLite connections are closed automatically
            pass


# Singleton instance
_dms_connector = None


def get_dms_connector() -> DMSKnowledgeConnector:
    """Get or create global DMS connector"""
    global _dms_connector
    if _dms_connector is None:
        _dms_connector = DMSKnowledgeConnector()
    return _dms_connector


async def test_dms_connector():
    """Test DMS connector"""
    connector = get_dms_connector()
    
    print("🧪 Testing DMS Knowledge Connector")
    print("=" * 60)
    
    # Initialize
    success = await connector.initialize()
    if not success:
        print("❌ Failed to initialize")
        return
    
    # Get stats
    stats = await connector.get_statistics()
    print(f"\n📊 DMS Statistics:")
    print(f"  Total documents: {stats.get('total_documents', 0)}")
    print(f"  With content: {stats.get('with_content', 0)}")
    print(f"  With OCR: {stats.get('with_ocr', 0)}")
    
    # Search test
    print(f"\n🔍 Search test: 'peraturan'")
    result = await connector.search("peraturan", top_k=3)
    
    if result.success:
        print(f"  Found: {result.total_found} documents")
        for doc in result.documents:
            print(f"  - {doc.get('file_name')}")
            labels = doc.get('label_dict', {})
            if labels:
                print(f"    Labels: {labels}")
    else:
        print(f"  Error: {result.error}")
    
    # Get recent
    print(f"\n🕐 Recent documents:")
    recent = await connector.get_recent_documents(limit=3)
    for doc in recent:
        print(f"  - {doc.get('file_name')} ({doc.get('source_name')})")
    
    print("\n✅ Test complete")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_dms_connector())