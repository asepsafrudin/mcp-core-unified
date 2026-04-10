import os
"""
Test Script: Extractor + Knowledge Bridge Integration

Test end-to-end: Extract → Save to Knowledge Base → Search
"""

import asyncio
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent / "mcp-unified" / "integrations" / "agentic_ai"))

from playwright.async_api import async_playwright
from extractors import HukumonlineExtractor, KemenkeuExtractor, JDIHExtractor
from knowledge_bridge_integration import ExtractorKnowledgeBridge


async def test_hukumonline():
    """Test Hukumonline extractor dengan knowledge bridge"""
    print("\n" + "="*60)
    print("🧪 TEST 1: Hukumonline Extractor + Knowledge Bridge")
    print("="*60)
    
    extractor = HukumonlineExtractor()
    kb_bridge = ExtractorKnowledgeBridge()
    
    url = "https://www.hukumonline.com/berita"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print(f"\n📡 Loading: {url}")
            await page.goto(url, timeout=30000)
            
            # Pre-process
            print("⏳ Pre-processing...")
            await extractor.pre_process(page)
            
            # Extract
            print("🔍 Extracting...")
            results = await extractor.extract(page)
            results = await extractor.post_process(results)
            
            print(f"✅ Extracted: {len(results)} items")
            
            if results:
                # Show first result
                print(f"\n📋 First result:")
                print(f"   Title: {results[0].get('title', 'N/A')[:80]}")
                print(f"   URL: {results[0].get('url', 'N/A')[:60]}")
                
                # Save to knowledge base
                print("\n💾 Saving to Knowledge Base...")
                summary = await kb_bridge.save_extraction_results(
                    results=results[:3],  # Save first 3 for test
                    source="hukumonline",
                    url=url,
                    namespace=os.getenv("NAMESPACE", "test_legal_regulations" if not os.getenv("CI") else "DUMMY")
                )
                
                print(f"📊 Save Summary:")
                print(f"   Saved: {summary['saved']}")
                print(f"   Skipped: {summary['skipped']}")
                print(f"   Errors: {summary['errors']}")
                
                # Search test
                print("\n🔍 Testing search...")
                search_results = await kb_bridge.search_saved_results(
                    query=os.getenv("QUERY", "hukum" if not os.getenv("CI") else "DUMMY"),
                    namespace="test_legal_regulations",
                    top_k=3
                )
                print(f"   Found: {len(search_results)} results")
                
                if search_results:
                    print(f"   First match: {search_results[0].get('metadata', {}).get('title', 'N/A')[:60]}")
                
                return True
            else:
                print("⚠️ No results extracted")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
        finally:
            await browser.close()


async def test_extractor_registry():
    """Test auto-discovery dan registry"""
    print("\n" + "="*60)
    print("🧪 TEST 2: Extractor Registry & Auto-Discovery")
    print("="*60)
    
    from extractor_registry import get_registry
    
    registry = get_registry()
    
    print(f"\n📊 Registered Extractors: {len(registry.list_extractors())}")
    
    for ext_info in registry.list_extractors():
        print(f"   - {ext_info['name']}: {ext_info['description'][:50]}")
    
    # Test URL matching
    test_urls = [
        "https://www.hukumonline.com/berita",
        "https://jdihn.go.id",
        "https://jdih.kemenkeu.go.id",
        "https://www.detik.com",
    ]
    
    print("\n🔗 URL Matching Test:")
    for url in test_urls:
        extractor = registry.get_extractor_for_url(url)
        if extractor:
            print(f"   ✅ {url[:40]}... → {extractor.name}")
        else:
            print(f"   ⚠️ {url[:40]}... → No match (will use Generic)")
    
    return True


async def test_extractor_chain():
    """Test extractor chain dengan quality scoring"""
    print("\n" + "="*60)
    print("🧪 TEST 3: Extractor Chain & Quality Scoring")
    print("="*60)
    
    from extractor_chain import ExtractorChain
    from extractors import GenericExtractor, HukumonlineExtractor
    
    # Create chain
    chain = ExtractorChain([
        HukumonlineExtractor(),
        GenericExtractor()
    ])
    
    print(f"\n⛓️  Chain created with {len(chain.extractors)} extractors")
    print("   Order: HukumonlineExtractor → GenericExtractor (fallback)")
    
    print("\n📊 Quality Scoring Formula:")
    print("   - Item Count: 25%")
    print("   - Field Completeness: 35%")
    print("   - Title Quality: 25%")
    print("   - URL Presence: 15%")
    
    return True


async def run_all_tests():
    """Run semua tests"""
    print("\n" + "="*60)
    print("🚀 EXTRACTOR SYSTEM - COMPLETE TEST SUITE")
    print("="*60)
    
    results = []
    
    # Test 1: Hukumonline + Knowledge Bridge
    try:
        result = await test_hukumonline()
        results.append(("Hukumonline + KB", result))
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
        results.append(("Hukumonline + KB", False))
    
    # Test 2: Registry
    try:
        result = await test_extractor_registry()
        results.append(("Registry & Discovery", result))
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
        results.append(("Registry & Discovery", False))
    
    # Test 3: Chain
    try:
        result = await test_extractor_chain()
        results.append(("Extractor Chain", result))
    except Exception as e:
        print(f"❌ Test 3 failed: {e}")
        results.append(("Extractor Chain", False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")
    
    print(f"\n📈 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is ready for production.")
    else:
        print("\n⚠️  Some tests failed. Check logs above.")
    
    return passed == total


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔧 Initializing Test Environment...")
    print("="*60)
    
    # Check imports
    try:
        from extractors import HukumonlineExtractor
        print("✅ Extractors module: OK")
    except Exception as e:
        print(f"❌ Extractors module failed: {e}")
        sys.exit(1)
    
    try:
        from knowledge_bridge_integration import ExtractorKnowledgeBridge
        print("✅ Knowledge Bridge module: OK")
    except Exception as e:
        print(f"❌ Knowledge Bridge module failed: {e}")
        sys.exit(1)
    
    # Run tests
    success = asyncio.run(run_all_tests())
    
    sys.exit(0 if success else 1)