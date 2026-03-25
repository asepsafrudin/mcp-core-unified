"""
Agent Knowledge Database Integration Example

Contoh penggunaan koneksi AI Agent dengan Database Knowledge.
Menunjukkan cara menggunakan DBKnowledgeConnector dan AgentKnowledgeBridge.
"""

import asyncio
import sys
from pathlib import Path

# Add mcp-unified to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.profiles.legal.connectors import (
    DBKnowledgeConnector,
    AgentKnowledgeBridge,
    KnowledgeSource,
    get_db_knowledge_connector,
    get_knowledge_bridge
)


async def example_1_basic_database_connector():
    """
    Example 1: Menggunakan DBKnowledgeConnector secara langsung.
    
    Ini adalah cara paling dasar untuk mengakses database knowledge.
    """
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Database Connector")
    print("="*60)
    
    # Create connector
    connector = DBKnowledgeConnector()
    
    # Initialize connection
    print("\n📡 Initializing database connection...")
    success = await connector.initialize()
    
    if not success:
        print("❌ Failed to initialize database connection")
        return
    
    print("✅ Database connection initialized")
    
    # Add some sample documents
    print("\n📄 Adding sample documents...")
    
    await connector.add_document(
        doc_id="uu_23_2014_pasal_1",
        content="""Pasal 1
Desa adalah kesatuan masyarakat hukum yang memiliki batas-batas wilayah 
berwenang untuk mengatur dan mengurus urusan pemerintahan, kepentingan 
masyarakat setempat berdasarkan prakarsa masyarakat, hak asal-usul, 
dan/atau hak tradisional yang diakui dan dihormati dalam sistem 
pemerintahan Negara Kesatuan Republik Indonesia.""",
        metadata={
            "type": "regulation",
            "regulation_type": "uu",
            "title": "Undang-Undang Desa",
            "year": 2014,
            "pasal": "1"
        },
        namespace="legal_uu_desa"
    )
    
    await connector.add_document(
        doc_id="uu_23_2014_pasal_2",
        content="""Pasal 2
(1) Desa menyelenggarakan urusan pemerintahan yang menjadi kewenangannya.
(2) Urusan pemerintahan yang menjadi kewenangan Desa sebagaimana dimaksud 
pada ayat (1) meliputi urusan pemerintahan konkuren sesuai kewenangan 
Desa, urusan pemerintahan wajib, dan urusan pemerintahan pilihan.""",
        metadata={
            "type": "regulation",
            "regulation_type": "uu",
            "title": "Undang-Undang Desa",
            "year": 2014,
            "pasal": "2"
        },
        namespace="legal_uu_desa"
    )
    
    await connector.add_regulation_document(
        regulation_id="uu_23_2014",
        title="Tentang Pemerintahan Desa",
        content="""BAB I - KETENTUAN UMUM

Pasal 1
Desa adalah kesatuan masyarakat hukum yang memiliki batas-batas wilayah 
berwenang untuk mengatur dan mengurus urusan pemerintahan.

Pasal 2
Desa menyelenggarakan urusan pemerintahan yang menjadi kewenangannya 
yang meliputi urusan pemerintahan konkuren, urusan wajib, dan urusan pilihan.""",
        regulation_type="uu",
        year=2014,
        namespace="legal_regulations"
    )
    
    print("✅ Documents added")
    
    # Query the knowledge base
    print("\n🔍 Querying knowledge base...")
    
    result = await connector.query(
        query="apa itu desa?",
        namespace="legal_uu_desa",
        top_k=3
    )
    
    if result.success:
        print(f"\n✅ Query successful!")
        print(f"   Found {result.total_documents} documents")
        print(f"\n📋 Context:\n{result.context[:500]}...")
        print(f"\n📚 Sources:")
        for source in result.sources:
            print(f"   - {source['id']} (similarity: {source['similarity']:.4f})")
    else:
        print(f"❌ Query failed: {result.error}")
    
    # Search regulations
    print("\n🔍 Searching regulations...")
    reg_result = await connector.search_regulations(
        query="pemerintahan desa",
        regulation_type="uu",
        namespace="legal_regulations"
    )
    
    if reg_result.success:
        print(f"\n✅ Found {reg_result.total_documents} regulations")
    
    # Cleanup
    await connector.close()
    print("\n✅ Example 1 completed")


async def example_2_unified_bridge():
    """
    Example 2: Menggunakan AgentKnowledgeBridge.
    
    Ini adalah cara yang lebih advanced dengan unified interface
    yang mendukung multiple sources (database + file-based KB).
    """
    print("\n" + "="*60)
    print("EXAMPLE 2: Unified Knowledge Bridge")
    print("="*60)
    
    # Create bridge
    bridge = AgentKnowledgeBridge()
    
    # Initialize
    print("\n📡 Initializing knowledge bridge...")
    success = await bridge.initialize()
    
    if not success:
        print("❌ Failed to initialize bridge")
        return
    
    print("✅ Bridge initialized")
    
    # Add some documents to database
    print("\n📄 Adding documents to database...")
    
    await bridge.add_regulation(
        regulation_id="uu_11_2006",
        title="Tentang Pemerintahan Aceh",
        content="""BAB I - KETENTUAN UMUM

Pasal 1
Dalam Undang-Undang ini yang dimaksud dengan:
1. Provinsi Nanggroe Aceh Darussalam yang selanjutnya disebut Provinsi NAD 
   adalah daerah otonom yang mempunyai batas-batas wilayah tertentu 
   berwenang mengatur dan mengurus urusan pemerintahan.""",
        regulation_type="uu",
        year=2006,
        namespace="legal_regulations"
    )
    
    print("✅ Documents added")
    
    # Query dari multiple sources
    print("\n🔍 Querying from multiple sources...")
    
    result = await bridge.query(
        query="apa itu desa dan pemerintahannya?",
        sources=[KnowledgeSource.DATABASE, KnowledgeSource.FILE_BASED],
        namespace="legal_uu_desa",
        top_k=3
    )
    
    if result.success:
        print(f"\n✅ Query successful!")
        print(f"\n📋 Aggregated Context:")
        print(result.context[:800] + "...")
        
        print(f"\n📚 Citations:")
        for citation in result.citations:
            print(f"   📖 {citation}")
        
        print(f"\n📊 Results breakdown:")
        print(f"   - File KB: {len(result.file_results)} results")
        print(f"   - Database: {len(result.db_results)} results")
    else:
        print(f"❌ Query failed: {result.error}")
    
    # Query database only
    print("\n🔍 Querying database only...")
    db_result = await bridge.query_database(
        query="pemerintahan Aceh",
        namespace="legal_regulations",
        top_k=3
    )
    
    if db_result.success:
        print(f"\n✅ Database query successful!")
        print(f"   Found {db_result.total_documents} documents")
    
    # Get context untuk LLM
    print("\n🤖 Getting context for LLM...")
    llm_context = await bridge.get_context_for_llm(
        query="bagaimana desa menyelenggarakan pemerintahan?",
        namespace="legal_uu_desa",
        top_k=3
    )
    
    print(f"\n✅ LLM Context ready:")
    print(f"   Has context: {llm_context['has_context']}")
    print(f"   Citations: {len(llm_context.get('citations', []))}")
    print(f"   Sources: {len(llm_context.get('sources', []))}")
    
    # Cleanup
    await bridge.close()
    print("\n✅ Example 2 completed")


async def example_3_singleton_pattern():
    """
    Example 3: Menggunakan singleton pattern.
    
    Menggunakan global instance untuk konsistensi di seluruh aplikasi.
    """
    print("\n" + "="*60)
    print("EXAMPLE 3: Singleton Pattern")
    print("="*60)
    
    # Get global instances
    print("\n📡 Getting global connector instances...")
    
    connector1 = get_db_knowledge_connector()
    connector2 = get_db_knowledge_connector()
    
    print(f"   Connector 1 ID: {id(connector1)}")
    print(f"   Connector 2 ID: {id(connector2)}")
    print(f"   Same instance: {connector1 is connector2}")
    
    bridge1 = get_knowledge_bridge()
    bridge2 = get_knowledge_bridge()
    
    print(f"   Bridge 1 ID: {id(bridge1)}")
    print(f"   Bridge 2 ID: {id(bridge2)}")
    print(f"   Same instance: {bridge1 is bridge2}")
    
    # Initialize once
    print("\n📡 Initializing once...")
    await bridge1.initialize()
    
    # Both bridges are the same instance
    print(f"   Bridge 1 initialized: {bridge1._initialized}")
    print(f"   Bridge 2 initialized: {bridge2._initialized}")
    
    print("\n✅ Example 3 completed")


async def example_4_practical_usage():
    """
    Example 4: Practical usage scenario.
    
    Simulasi penggunaan nyata oleh Legal Agent.
    """
    print("\n" + "="*60)
    print("EXAMPLE 4: Practical Legal Agent Usage")
    print("="*60)
    
    bridge = get_knowledge_bridge()
    
    if not bridge._initialized:
        await bridge.initialize()
    
    # Scenario: Legal Agent menerima pertanyaan tentang desa
    user_question = "Apa saja urusan pemerintahan yang menjadi kewenangan desa?"
    
    print(f"\n👤 User Question: {user_question}")
    print("\n🤖 Legal Agent processing...")
    
    # Step 1: Get context dari knowledge base
    print("   Step 1: Retrieving knowledge...")
    context_result = await bridge.get_context_for_llm(
        query=user_question,
        namespace="legal_uu_desa",
        top_k=5
    )
    
    if context_result["has_context"]:
        print(f"   ✅ Retrieved {len(context_result['sources'])} relevant documents")
        
        # Step 2: Prepare prompt dengan context
        print("   Step 2: Preparing prompt with context...")
        
        prompt = f"""Berikut adalah informasi relevan dari basis pengetahuan hukum:

{context_result['context']}

Berdasarkan informasi di atas, jawablah pertanyaan berikut:
{user_question}

Sertakan referensi/citation yang relevan."""
        
        print(f"   ✅ Prompt prepared ({len(prompt)} characters)")
        
        # Step 3: Show citations
        print("   Step 3: Available citations:")
        for citation in context_result.get("citations", []):
            print(f"      📖 {citation}")
        
        # Step 4: Simulated LLM response
        print("\n📝 Simulated LLM Response:")
        print("   Berdasarkan UU Nomor 23 Tahun 2014 tentang Pemerintahan Desa,")
        print("   kewenangan desa meliputi:")
        print("   1. Urusan pemerintahan konkuren sesuai kewenangan Desa")
        print("   2. Urusan pemerintahan wajib")
        print("   3. Urusan pemerintahan pilihan")
        print("\n   📚 Referensi: Pasal 2 UU 23/2014")
        
    else:
        print("   ⚠️ No relevant context found in knowledge base")
    
    print("\n✅ Example 4 completed")


async def main():
    """Main function untuk menjalankan semua examples."""
    print("\n" + "="*60)
    print("AGENT KNOWLEDGE DATABASE INTEGRATION")
    print("Examples & Demonstrations")
    print("="*60)
    
    try:
        # Run examples
        await example_1_basic_database_connector()
        await example_2_unified_bridge()
        await example_3_singleton_pattern()
        await example_4_practical_usage()
        
        print("\n" + "="*60)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY ✅")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run async examples
    asyncio.run(main())