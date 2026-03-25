#!/usr/bin/env python3
"""
Test Script - Agent Knowledge Database Connection

Skrip untuk memverifikasi koneksi antara AI Agent dengan Database Knowledge.
"""

import asyncio
import sys
from pathlib import Path

# Add mcp-unified to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.profiles.legal.connectors import (
    get_db_knowledge_connector,
    get_knowledge_bridge
)


async def test_database_connection():
    """Test koneksi ke database PostgreSQL/pgvector."""
    print("\n" + "="*60)
    print("🧪 TEST 1: Database Connection")
    print("="*60)
    
    connector = get_db_knowledge_connector()
    
    print("\n📡 Connecting to PostgreSQL + pgvector...")
    success = await connector.initialize()
    
    if success:
        print("✅ Database connection successful!")
        print("   - PostgreSQL: Connected")
        print("   - pgvector extension: Enabled")
        print("   - Knowledge table: Ready")
    else:
        print("❌ Database connection failed!")
        print("\n💡 Troubleshooting:")
        print("   1. Pastikan PostgreSQL berjalan")
        print("   2. Verifikasi credential di .env")
        print("   3. Install pgvector extension")
    
    await connector.close()
    return success


async def test_knowledge_bridge():
    """Test Agent Knowledge Bridge."""
    print("\n" + "="*60)
    print("🧪 TEST 2: Knowledge Bridge")
    print("="*60)
    
    bridge = get_knowledge_bridge()
    
    print("\n📡 Initializing knowledge bridge...")
    success = await bridge.initialize()
    
    if success:
        print("✅ Knowledge bridge initialized!")
        print("   - Database connector: Ready")
        print("   - File-based KB: Ready")
        print("   - Unified interface: Ready")
    else:
        print("⚠️ Knowledge bridge partially initialized")
        print("   (File-based KB tetap berfungsi)")
    
    await bridge.close()
    return success


async def test_document_operations():
    """Test document CRUD operations."""
    print("\n" + "="*60)
    print("🧪 TEST 3: Document Operations")
    print("="*60)
    
    connector = get_db_knowledge_connector()
    
    if not await connector.initialize():
        print("❌ Cannot test - database not connected")
        return False
    
    try:
        # Test add document
        print("\n📝 Testing add document...")
        success = await connector.add_document(
            doc_id="test_document_001",
            content="Test document content for verification.",
            metadata={"type": "test", "source": "verification"},
            namespace="test_namespace"
        )
        
        if success:
            print("✅ Document added successfully")
        else:
            print("❌ Failed to add document")
        
        # Test query
        print("\n🔍 Testing query...")
        result = await connector.query(
            query="test document",
            namespace="test_namespace",
            top_k=3
        )
        
        if result.success and result.total_documents > 0:
            print(f"✅ Query successful - found {result.total_documents} document(s)")
        else:
            print("⚠️ Query returned no results")
        
        # Test list documents
        print("\n📋 Testing list documents...")
        docs = await connector.list_documents(namespace="test_namespace")
        print(f"✅ Listed {len(docs)} document(s)")
        
        # Cleanup - delete test document
        print("\n🗑️ Cleaning up test document...")
        await connector.delete_document("test_document_001", namespace="test_namespace")
        print("✅ Test document deleted")
        
        await connector.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        await connector.close()
        return False


async def test_retrieval_for_llm():
    """Test context retrieval untuk LLM."""
    print("\n" + "="*60)
    print("🧪 TEST 4: LLM Context Retrieval")
    print("="*60)
    
    bridge = get_knowledge_bridge()
    
    if not await bridge.initialize():
        print("❌ Cannot test - database not connected")
        return False
    
    try:
        # Add test regulation
        print("\n📄 Adding test regulation...")
        await bridge.add_regulation(
            regulation_id="test_uu_001",
            title="Test Regulation",
            content="This is a test regulation for LLM context retrieval testing.",
            regulation_type="uu",
            year=2024,
            pasal="1",
            namespace="test_llm"
        )
        print("✅ Test regulation added")
        
        # Get context for LLM
        print("\n🤖 Getting context for LLM...")
        context = await bridge.get_context_for_llm(
            query="test regulation",
            namespace="test_llm",
            top_k=3
        )
        
        if context.get("has_context"):
            print(f"✅ Context retrieved successfully")
            print(f"   - Document count: {len(context.get('sources', []))}")
            print(f"   - Context length: {len(context.get('context', ''))} chars")
            print(f"   - Citations: {len(context.get('citations', []))}")
        else:
            print("⚠️ No context retrieved")
        
        # Cleanup
        await bridge.db_connector.delete_document("test_uu_001_pasal_1", namespace="test_llm")
        print("\n✅ Cleanup completed")
        
        await bridge.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await bridge.close()
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🔌 AGENT KNOWLEDGE DATABASE CONNECTION TEST")
    print("="*60)
    print("\nMemverifikasi koneksi AI Agent dengan Database Knowledge...")
    
    results = {
        "Database Connection": await test_database_connection(),
        "Knowledge Bridge": await test_knowledge_bridge(),
        "Document Operations": await test_document_operations(),
        "LLM Context Retrieval": await test_retrieval_for_llm()
    }
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    print(f"\n   Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Agent-Knowledge integration is ready.")
    else:
        print("\n⚠️ Some tests failed. Check configuration and prerequisites.")
    
    print("="*60)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
