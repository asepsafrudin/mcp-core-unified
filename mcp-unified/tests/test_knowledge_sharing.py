"""
Test untuk Knowledge Sharing Module

Run: python -m pytest tests/test_knowledge_sharing.py -v
"""

import pytest
import asyncio
from pathlib import Path

from knowledge.ingestion import DocumentProcessor, QualityScorer
from knowledge.ingestion.chunking.text_chunker import SemanticChunker
from knowledge.sharing import NamespaceManager


class TestQualityScorer:
    """Test quality scoring."""
    
    def test_score_high_quality_text(self):
        scorer = QualityScorer()
        
        text = """
        Dokumen ini berisi informasi tentang prosedur pengadaan barang.
        Prosedur ini mengacu pada Perpres No. 16 Tahun 2018.
        
        ## Langkah-langkah
        1. Identifikasi kebutuhan
        2. Penyusunan spesifikasi
        3. Pemilihan penyedia
        
        Dokumen ini disusun oleh Tim Pengadaan.
        """
        
        chunks = [{"content": text, "metadata": {}}]
        score = scorer.score(text, chunks)
        
        assert 0.5 <= score <= 1.0
        print(f"High quality text score: {score}")
    
    def test_score_low_quality_text(self):
        scorer = QualityScorer()
        
        # Gibberish text dengan repeating patterns
        text = "xxxxxxx yyyyyyy zzzzzzz !@#$%^&*() 1234567890"
        
        chunks = [{"content": text, "metadata": {}}]
        score = scorer.score(text, chunks)
        
        # Score should be relatively lower than high quality
        assert score < 0.7
        print(f"Low quality text score: {score}")
    
    def test_score_empty_text(self):
        scorer = QualityScorer()
        
        score = scorer.score("", [])
        
        assert score == 0.0


class TestSemanticChunker:
    """Test text chunking."""
    
    def test_chunk_paragraphs(self):
        chunker = SemanticChunker(chunk_size=100, chunk_overlap=20)
        
        text = """
Paragraph pertama berisi informasi tentang topik A.
Ini adalah kalimat lanjutan dari paragraph pertama.

Paragraph kedua membahas topik B yang berbeda.
Kalimat ini melanjutkan pembahasan topik B.

Paragraph ketiga adalah kesimpulan.
"""
        
        chunks = chunker.chunk(text)
        
        assert len(chunks) > 0
        assert all(len(c["content"]) >= chunker.min_chunk_size for c in chunks)
        print(f"Chunks created: {len(chunks)}")
    
    def test_chunk_with_headers(self):
        chunker = SemanticChunker()
        
        text = """
## Section 1
Content of section 1.
More content here.

## Section 2
Content of section 2.
Even more content.
"""
        
        chunks = chunker.chunk(text)
        
        assert len(chunks) > 0
        print(f"Chunks with headers: {len(chunks)}")


class TestNamespaceManager:
    """Test namespace management."""
    
    @pytest.mark.asyncio
    async def test_list_namespaces(self):
        manager = NamespaceManager()
        
        namespaces = await manager.list_namespaces()
        
        assert len(namespaces) == 4
        assert any(ns["name"] == "shared_legal" for ns in namespaces)
        print(f"Namespaces: {[ns['name'] for ns in namespaces]}")
    
    def test_suggest_namespace_legal(self):
        manager = NamespaceManager()
        
        ns = manager.suggest_namespace("UU_No_23_2024.pdf")
        
        assert ns == "shared_legal"
    
    def test_suggest_namespace_admin(self):
        manager = NamespaceManager()
        
        ns = manager.suggest_namespace("SOP_Pengadaan.docx")
        
        assert ns == "shared_admin"
    
    def test_suggest_namespace_general(self):
        manager = NamespaceManager()
        
        ns = manager.suggest_namespace("random_file.txt")
        
        assert ns == "shared_general"


class TestDocumentProcessor:
    """Test document processor."""
    
    @pytest.mark.asyncio
    async def test_process_nonexistent_file(self):
        processor = DocumentProcessor()
        
        result = await processor.process_file("/nonexistent/file.pdf")
        
        assert result.status == "error"
        assert "tidak ditemukan" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_process_unsupported_format(self):
        processor = DocumentProcessor()
        
        # Create temporary file dengan unsupported extension
        test_file = Path("/tmp/test.xyz")
        test_file.write_text("test content")
        
        result = await processor.process_file(str(test_file))
        
        assert result.status == "error"
        assert "tidak didukung" in result.message.lower()
        
        test_file.unlink()
    
    @pytest.mark.asyncio
    async def test_get_pending_reviews(self):
        processor = DocumentProcessor()
        
        reviews = processor.get_pending_reviews()
        
        assert isinstance(reviews, list)


def run_tests():
    """Run all tests."""
    print("=" * 60)
    print("Knowledge Sharing Module Tests")
    print("=" * 60)
    
    # Quality Scorer tests
    print("\n🧪 Testing Quality Scorer...")
    scorer_test = TestQualityScorer()
    scorer_test.test_score_high_quality_text()
    scorer_test.test_score_low_quality_text()
    scorer_test.test_score_empty_text()
    print("✅ Quality Scorer tests passed")
    
    # Chunker tests
    print("\n🧪 Testing Semantic Chunker...")
    chunker_test = TestSemanticChunker()
    chunker_test.test_chunk_paragraphs()
    chunker_test.test_chunk_with_headers()
    print("✅ Semantic Chunker tests passed")
    
    # Namespace Manager tests
    print("\n🧪 Testing Namespace Manager...")
    ns_test = TestNamespaceManager()
    asyncio.run(ns_test.test_list_namespaces())
    ns_test.test_suggest_namespace_legal()
    ns_test.test_suggest_namespace_admin()
    ns_test.test_suggest_namespace_general()
    print("✅ Namespace Manager tests passed")
    
    # Document Processor tests
    print("\n🧪 Testing Document Processor...")
    proc_test = TestDocumentProcessor()
    asyncio.run(proc_test.test_process_nonexistent_file())
    asyncio.run(proc_test.test_process_unsupported_format())
    asyncio.run(proc_test.test_get_pending_reviews())
    print("✅ Document Processor tests passed")
    
    print("\n" + "=" * 60)
    print("All tests passed! ✅")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
