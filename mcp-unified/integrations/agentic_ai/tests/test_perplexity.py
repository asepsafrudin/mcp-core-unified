#!/usr/bin/env python3
"""
Test Script untuk Perplexity.ai Web Scraping

Cara penggunaan:
1. Jalankan script: python test_perplexity.py
2. Masukkan URL Perplexity ketika diminta
3. Lihat hasil scraping

Contoh URL:
- https://www.perplexity.ai/search/jelaskan-undang-undang-cipta-kerja
- https://www.perplexity.ai/search/perbedaan-uu-23-2014-dan-uu-11
"""

import asyncio
import sys
import json
from datetime import datetime

# Add path untuk imports
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

from integrations.web_scraping import WebScrapingIngestor


async def test_perplexity():
    """Test scraping dari Perplexity.ai"""
    
    print("🚀 Perplexity.ai Web Scraping Test")
    print("=" * 60)
    print()
    print("📋 Panduan:")
    print("   1. Buka https://www.perplexity.ai/")
    print("   2. Chat dengan AI (tanya tentang topik hukum)")
    print("   3. Copy URL hasil chat (contoh: https://www.perplexity.ai/search/...)")
    print("   4. Paste URL di bawah")
    print()
    
    # URL Perplexity
    PERPLEXITY_URL = input("🔗 Masukkan URL Perplexity: ").strip()
    
    if not PERPLEXITY_URL:
        print("\n❌ URL tidak boleh kosong!")
        print("   Tips: URL harus dimulai dengan https://www.perplexity.ai/search/")
        return
    
    if not PERPLEXITY_URL.startswith("https://www.perplexity.ai/"):
        print("\n⚠️  Peringatan: URL tidak terlihat seperti URL Perplexity")
        confirm = input("   Tetap lanjutkan? (y/n): ").strip().lower()
        if confirm != 'y':
            return
    
    # Domain dan tags
    print()
    DOMAIN = input("🏷️ Domain (default: hukum_perdata): ").strip() or "hukum_perdata"
    TAGS_INPUT = input("🏷️ Tags (pisahkan dengan koma, default: perplexity,test): ").strip()
    TAGS = [t.strip() for t in TAGS_INPUT.split(",") if t.strip()] or ["perplexity", "test"]
    
    print()
    print("📋 Konfigurasi:")
    print(f"   URL: {PERPLEXITY_URL}")
    print(f"   Domain: {DOMAIN}")
    print(f"   Tags: {', '.join(TAGS)}")
    print()
    
    # Initialize ingestor
    print("⚙️  Initializing browser...")
    print("   (Ini akan menginstall browser jika pertama kali)")
    ingestor = WebScrapingIngestor()
    
    try:
        success = await ingestor.initialize()
        if not success:
            print("\n❌ Gagal initialize browser!")
            print("   Tips: Cek apakah playwright sudah terinstall:")
            print("   pip install playwright")
            print("   playwright install chromium")
            return
        
        print("✅ Browser ready")
        print()
        
        # Scrape
        print("🔍 Scraping Perplexity thread...")
        print("   ⏳ Ini akan memakan waktu 15-45 detik...")
        print("   ⏳ Mohon tunggu...")
        print()
        
        result = await ingestor.scrape_and_ingest(
            url=PERPLEXITY_URL,
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
            filename = f"perplexity_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, default=str, ensure_ascii=False)
                print()
                print(f"💾 Hasil disimpan ke: {filename}")
            except Exception as e:
                print(f"\n⚠️  Gagal menyimpan file: {e}")
            
            print()
            print("📝 Tips Selanjutnya:")
            print("   1. Cek file JSON untuk melihat detail lengkap")
            print("   2. Jika quality score < 0.75, pertimbangkan untuk review manual")
            print("   3. Data sudah tersimpan di knowledge base (jika knowledge_bridge aktif)")
            
        else:
            print()
            print("❌ SCRAPING GAGAL!")
            print()
            print(f"🔴 Error: {result.get('error', 'Unknown error')}")
            
            if result.get('elapsed_seconds'):
                print(f"⏱️  Waktu: {result['elapsed_seconds']:.1f} detik")
            
            print()
            print("📝 Tips Troubleshooting:")
            print("   1. Cek apakah URL bisa diakses di browser")
            print("   2. Coba dengan URL Perplexity yang berbeda")
            print("   3. Cek koneksi internet")
            print("   4. Coba gunakan /scrape command di Telegram bot")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test dihentikan oleh user")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print()
        print("🔍 Detail error:")
        import traceback
        traceback.print_exc()
    
    finally:
        print()
        print("🧹 Cleanup...")
        await ingestor.close()
        print("✅ Selesai!")


if __name__ == "__main__":
    try:
        asyncio.run(test_perplexity())
    except KeyboardInterrupt:
        print("\n\n👋 Test dihentikan. Sampai jumpa!")
        sys.exit(0)