#!/usr/bin/env python3
"""
Test Script untuk peraturan.go.id (JDIH)
URL: https://peraturan.go.id/
"""

import asyncio
import sys
import json
from datetime import datetime

# Add path untuk imports
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

from integrations.web_scraping import WebScrapingIngestor


async def test_jdih():
    """Test scraping dari peraturan.go.id"""
    
    # URL peraturan.go.id - Cari peraturan yang tersedia
    # Home page atau daftar peraturan
    JDIH_URL = "https://peraturan.go.id/"
    DOMAIN = "regulasi"
    TAGS = ["jdih", "peraturan_go_id", "uud_1945", "test"]
    
    print("🚀 JDIH (peraturan.go.id) Web Scraping Test")
    print("=" * 60)
    print()
    print(f"📋 Konfigurasi:")
    print(f"   URL: {JDIH_URL}")
    print(f"   Domain: {DOMAIN}")
    print(f"   Tags: {', '.join(TAGS)}")
    print()
    
    # Initialize ingestor
    print("⚙️  Initializing browser...")
    ingestor = WebScrapingIngestor()
    
    try:
        success = await ingestor.initialize()
        if not success:
            print("\n❌ Gagal initialize browser!")
            return
        
        print("✅ Browser ready")
        print()
        
        # Scrape
        print("🔍 Scraping JDIH page...")
        print("   ⏳ Ini akan memakan waktu 15-45 detik...")
        print("   ⏳ Mohon tunggu...")
        print()
        
        result = await ingestor.scrape_and_ingest(
            url=JDIH_URL,
            domain=DOMAIN,
            tags=TAGS,
        )
        
        # Display results
        print()
        print("=" * 60)
        print("📊 RESULTS")
        print("=" * 60)
        
        if result['success']:
            print()
            print("✅ SCRAPING BERHASIL!")
            print()
            print(f"📄 Title: {result.get('title', 'N/A')}")
            print(f"🆔 Doc ID: {result.get('doc_id', 'N/A')}")
            print(f"🔧 Extractor: {result.get('extractor', 'N/A')}")
            
            if result.get('validation_score'):
                score = result['validation_score']
                emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.7 else "🔴"
                status = "Bagus" if score >= 0.8 else "Cukup" if score >= 0.7 else "Perlu Review"
                print()
                print(f"⭐ Quality Score: {emoji} {score:.2f}/1.0 ({status})")
            
            if result.get('requires_review'):
                print()
                print("⚠️  Status: Perlu review manual sebelum digunakan")
            
            print()
            print(f"⏱️  Waktu: {result.get('elapsed_seconds', 0):.1f} detik")
            
            # Save to file
            filename = f"jdih_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, default=str, ensure_ascii=False)
                print()
                print(f"💾 Hasil disimpan ke: {filename}")
            except Exception as e:
                print(f"\n⚠️  Gagal menyimpan file: {e}")
            
            print()
            print("📝 Konten Preview (500 chars):")
            print("-" * 60)
            if result.get('content'):
                content = result['content']
                print(content[:500] + "..." if len(content) > 500 else content)
            print("-" * 60)
            
        else:
            print()
            print("❌ SCRAPING GAGAL!")
            print()
            print(f"🔴 Error: {result.get('error', 'Unknown error')}")
            
            if result.get('elapsed_seconds'):
                print(f"⏱️  Waktu: {result['elapsed_seconds']:.1f} detik")
            
            print()
            print("📝 Troubleshooting:")
            print("   1. Cek apakah URL bisa diakses di browser")
            print("   2. Website mungkin memiliki proteksi anti-bot")
            print("   3. Coba dengan URL yang berbeda")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test dihentikan oleh user")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print()
        import traceback
        traceback.print_exc()
    
    finally:
        print()
        print("🧹 Cleanup...")
        await ingestor.close()
        print("✅ Selesai!")


if __name__ == "__main__":
    try:
        asyncio.run(test_jdih())
    except KeyboardInterrupt:
        print("\n\n👋 Test dihentikan. Sampai jumpa!")
        sys.exit(0)