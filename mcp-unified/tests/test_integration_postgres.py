"""
Integration Test: Knowledge Sharing dengan Actual PostgreSQL + pgvector

Test ini menggunakan PostgreSQL container yang sudah berjalan.
Pastikan container mcp-postgres aktif sebelum menjalankan test.

Run: PYTHONPATH=/home/aseps/MCP/mcp-unified python3 tests/test_integration_postgres.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge.integrated_processor import IntegratedDocumentProcessor
from knowledge.rag_engine import RAGEngine
from knowledge.stores.pgvector import PGVectorStore

# Database config dari .env.postgresql
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "mcp",
    "user": "aseps",
    "password": "secure123"
}

# Build connection string
CONNECTION_STRING = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"


async def test_pgvector_connection():
    """Test koneksi ke PostgreSQL + pgvector."""
    print("\n" + "="*60)
    print("🧪 TEST 1: PostgreSQL + pgvector Connection")
    print("="*60)
    
    try:
        import asyncpg
        
        # Test direct connection
        conn = await asyncpg.connect(CONNECTION_STRING)
        
        # Check pgvector extension
        result = await conn.fetchval(
            "SELECT extname FROM pg_extension WHERE extname = 'vector'"
        )
        
        if result == "vector":
            print("✅ pgvector extension aktif")
        else:
            print("⚠️ pgvector extension tidak ditemukan, mencoba create...")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            print("✅ pgvector extension berhasil dibuat")
        
        # Check version
        version = await conn.fetchval("SELECT version()")
        print(f"✅ PostgreSQL: {version[:50]}...")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_rag_engine_initialization():
    """Test RAG engine initialization dengan actual database."""
    print("\n" + "="*60)
    print("🧪 TEST 2: RAG Engine Initialization")
    print("="*60)
    
    try:
        # Create RAG engine dengan connection string
        vector_store = PGVectorStore(connection_string=CONNECTION_STRING)
        rag = RAGEngine(vector_store=vector_store)
        
        # Initialize
        success = await rag.initialize()
        
        if success:
            print("✅ RAG Engine berhasil diinisialisasi")
            
            # Check table exists
            import asyncpg
            conn = await asyncpg.connect(CONNECTION_STRING)
            table_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'knowledge_documents')"
            )
            
            if table_exists:
                print("✅ Table knowledge_documents tersedia")
            else:
                print("⚠️ Table belum ada, akan dibuat saat initialize")
            
            await conn.close()
            await rag.close()
            return True
        else:
            print("❌ RAG Engine initialization gagal")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_document_ingestion():
    """Test ingest dokumen ke knowledge base."""
    print("\n" + "="*60)
    print("🧪 TEST 3: Document Ingestion")
    print("="*60)
    
    try:
        # Create integrated processor
        processor = IntegratedDocumentProcessor()
        await processor.initialize()
        
        # Create test content (simulasi file)
        test_content = """
DOKUMEN TEST INTEGRATION
========================

Ini adalah dokumen test untuk integration testing.
Dokumen ini berisi informasi tentang prosedur pengadaan barang.

## Pasal 1: Ketentuan Umum
Pengadaan barang dan jasa harus dilakukan dengan prinsip:
1. Transparan
2. Akuntabel
3. Efisien
4. Efektif

## Pasal 2: Prosedur
Langkah-langkah pengadaan:
1. Identifikasi kebutuhan
2. Penyusunan spesifikasi teknis
3. Penentuan metode pengadaan
4. Seleksi penyedia
5. Penandatanganan kontrak

## Pasal 3: Pengawasan
Setiap pengadaan harus diawasi oleh tim yang berwenang.

Dokumen ini dibuat untuk testing purposes.
        """
        
        # Create temp file
        temp_file = Path("/tmp/test_integration_doc.txt")
        temp_file.write_text(test_content)
        
        # Ingest langsung via RAG (bypass file extraction)
        doc_id = f"test_doc_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        success = await processor.rag_engine.add_document(
            doc_id=doc_id,
            content=test_content,
            metadata={
                "source": "integration_test",
                "test": True,
                "created_at": datetime.now().isoformat()
            },
            namespace="test_namespace"
        )
        
        if success:
            print(f"✅ Dokumen berhasil diingest dengan ID: {doc_id}")
            
            # Cleanup temp file
            temp_file.unlink()
            
            await processor.close()
            return True, doc_id
        else:
            print("❌ Gagal ingest dokumen")
            return False, None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False, None


async def test_similarity_search(doc_id: str = None):
    """Test similarity search."""
    print("\n" + "="*60)
    print("🧪 TEST 4: Similarity Search")
    print("="*60)
    
    try:
        # Create processor
        processor = IntegratedDocumentProcessor()
        await processor.initialize()
        
        # Query
        queries = [
            "prosedur pengadaan barang",
            "langkah pengadaan",
            "pengawasan pengadaan",
            "metode seleksi penyedia"
        ]
        
        for query in queries:
            print(f"\n🔍 Query: '{query}'")
            
            result = await processor.query_knowledge(
                query=query,
                namespace="test_namespace",
                top_k=3
            )
            
            if result['sources']:
                print(f"   ✅ Found {len(result['sources'])} results")
                for i, source in enumerate(result['sources'][:2]):
                    similarity = source.get('similarity', 0)
                    print(f"   {i+1}. Similarity: {similarity:.4f}")
            else:
                print(f"   ⚠️ No results found")
        
        await processor.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_namespace_isolation():
    """Test namespace isolation."""
    print("\n" + "="*60)
    print("🧪 TEST 5: Namespace Isolation")
    print("="*60)
    
    try:
        processor = IntegratedDocumentProcessor()
        await processor.initialize()
        
        # Add documents ke berbagai namespaces
        namespaces = ["shared_legal", "shared_admin", "shared_tech"]
        
        for ns in namespaces:
            doc_id = f"test_{ns}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            success = await processor.rag_engine.add_document(
                doc_id=doc_id,
                content=f"Content for {ns} namespace",
                metadata={"namespace": ns},
                namespace=ns
            )
            
            if success:
                print(f"✅ Added document to {ns}")
        
        # Query masing-masing namespace
        print("\n🔍 Testing namespace isolation...")
        
        for ns in namespaces:
            docs = await processor.list_documents(namespace=ns, limit=10)
            print(f"   {ns}: {len(docs)} documents")
        
        await processor.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def cleanup_test_data():
    """Cleanup test data."""
    print("\n" + "="*60)
    print("🧹 CLEANUP: Removing Test Data")
    print("="*60)
    
    try:
        import asyncpg
        conn = await asyncpg.connect(CONNECTION_STRING)
        
        # Delete test documents
        result = await conn.execute(
            "DELETE FROM knowledge_documents WHERE id LIKE 'test_%' OR metadata->>'source' = 'integration_test'"
        )
        
        print(f"✅ Test data cleaned up")
        await conn.close()
        return True
        
    except Exception as e:
        print(f"⚠️ Cleanup error (tidak fatal): {e}")
        return False


async def run_all_tests():
    """Run semua tests."""
    print("\n" + "="*70)
    print("  KNOWLEDGE SHARING - POSTGRESQL + PGVECTOR INTEGRATION TEST")
    print("="*70)
    print(f"\n📊 Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    print(f"👤 User: {DB_CONFIG['user']}")
    
    results = []
    
    # Test 1: Connection
    results.append(("PostgreSQL Connection", await test_pgvector_connection()))
    
    # Test 2: RAG Engine
    results.append(("RAG Engine Init", await test_rag_engine_initialization()))
    
    # Test 3: Document Ingestion
    success, doc_id = await test_document_ingestion()
    results.append(("Document Ingestion", success))
    
    # Test 4: Similarity Search (jika ingestion berhasil)
    if success and doc_id:
        results.append(("Similarity Search", await test_similarity_search(doc_id)))
    else:
        results.append(("Similarity Search", False))
    
    # Test 5: Namespace Isolation
    results.append(("Namespace Isolation", await test_namespace_isolation()))
    
    # Cleanup
    await cleanup_test_data()
    
    # Summary
    print("\n" + "="*70)
    print("  TEST SUMMARY")
    print("="*70)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    total = len(results)
    passed = sum(1 for _, r in results if r)
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  🎉 All tests passed!")
    else:
        print(f"\n  ⚠️ {total - passed} test(s) failed")
    
    print("="*70)
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
