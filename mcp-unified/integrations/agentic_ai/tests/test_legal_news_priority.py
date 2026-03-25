#!/usr/bin/env python3
"""
Test Script untuk Website Berita Hukum Indonesia - Prioritas
Daftar sesuai prioritas user:

Situs Resmi Pemerintah:
1. MARINews (marinews.mahkamahagung.go.id)
2. JDIHN (jdihn.go.id)
3. Rechtsvinding (rechtsvinding.bphn.go.id)

Portal Berita Hukum Swasta:
4. Hukumonline (hukumonline.com/berita)
5. Law-Justice (law-justice.co)
6. Beritahukum (beritahukum.id)

Media Umum dengan Kanal Hukum:
7. ANTARA Hukum (antaranews.com/hukum)
8. detikHukum (news.detik.com/hukum)
9. Kompas Hukum (news.kompas.com)
"""

import asyncio
import sys
import json
from datetime import datetime

# Add path untuk imports
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

from integrations.web_scraping import WebScrapingIngestor


# Daftar URL prioritas
LEGAL_NEWS_SITES = [
    # Situs Resmi Pemerintah (Prioritas 1)
    {
        "name": "MARINews",
        "url": "https://marinews.mahkamahagung.go.id",
        "domain": "hukum",
        "tags": ["marinews", "mahkamah_agung", "peradilan", "prioritas_1"],
        "category": "Situs Resmi Pemerintah"
    },
    {
        "name": "JDIHN",
        "url": "https://jdihn.go.id",
        "domain": "regulasi",
        "tags": ["jdihn", "dokumentasi_hukum", "nasional", "prioritas_1"],
        "category": "Situs Resmi Pemerintah"
    },
    {
        "name": "Rechtsvinding BPHN",
        "url": "https://rechtsvinding.bphn.go.id",
        "domain": "hukum",
        "tags": ["rechtsvinding", "bphn", "pengetahuan_hukum", "prioritas_1"],
        "category": "Situs Resmi Pemerintah"
    },
    
    # Portal Berita Hukum Swasta (Prioritas 2)
    {
        "name": "Hukumonline",
        "url": "https://www.hukumonline.com/berita",
        "domain": "hukum",
        "tags": ["hukumonline", "berita_hukum", "analisis", "prioritas_2"],
        "category": "Portal Berita Hukum Swasta"
    },
    {
        "name": "Law-Justice",
        "url": "https://law-justice.co",
        "domain": "hukum",
        "tags": ["law_justice", "investigasi", "imparsial", "prioritas_2"],
        "category": "Portal Berita Hukum Swasta"
    },
    {
        "name": "Beritahukum",
        "url": "https://beritahukum.id",
        "domain": "hukum",
        "tags": ["beritahukum", "update_hukum", "nasional", "prioritas_2"],
        "category": "Portal Berita Hukum Swasta"
    },
    
    # Media Umum dengan Kanal Hukum (Prioritas 3)
    {
        "name": "ANTARA Hukum",
        "url": "https://www.antaranews.com/hukum",
        "domain": "berita",
        "tags": ["antara", "hukum", "penegakan_hukum", "prioritas_3"],
        "category": "Media Umum dengan Kanal Hukum"
    },
    {
        "name": "detikHukum",
        "url": "https://news.detik.com/hukum",
        "domain": "berita",
        "tags": ["detik", "hukum", "kasus_pidana", "prioritas_3"],
        "category": "Media Umum dengan Kanal Hukum"
    },
    {
        "name": "Kompas Hukum",
        "url": "https://news.kompas.com",
        "domain": "berita",
        "tags": ["kompas", "hukum", "politik", "prioritas_3"],
        "category": "Media Umum dengan Kanal Hukum"
    },
]


async def test_single_site(ingestor, site, index):
    """Test scraping untuk satu website"""
    print(f"\n{'='*70}")
    print(f"📌 [{index}] {site['name']}")
    print(f"   Category: {site['category']}")
    print(f"   URL: {site['url']}")
    print(f"   Domain: {site['domain']}")
    print(f"   Tags: {', '.join(site['tags'])}")
    print("-"*70)
    
    try:
        result = await ingestor.scrape_and_ingest(
            url=site['url'],
            domain=site['domain'],
            tags=site['tags'],
        )
        
        if result['success']:
            score = result.get('validation_score', 0)
            emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.7 else "🔴"
            status = "✅ BERHASIL"
            
            print(f"\n{status}!")
            print(f"⭐ Quality Score: {emoji} {score:.2f}/1.0")
            print(f"🔧 Extractor: {result.get('extractor', 'N/A')}")
            print(f"⏱️  Waktu: {result.get('elapsed_seconds', 0):.1f} detik")
            
            return {
                "site": site['name'],
                "success": True,
                "score": score,
                "url": site['url'],
                "category": site['category']
            }
        else:
            print(f"\n❌ GAGAL!")
            print(f"🔴 Error: {result.get('error', 'Unknown error')}")
            
            return {
                "site": site['name'],
                "success": False,
                "error": result.get('error', 'Unknown'),
                "url": site['url'],
                "category": site['category']
            }
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return {
            "site": site['name'],
            "success": False,
            "error": str(e),
            "url": site['url'],
            "category": site['category']
        }


async def test_all_sites():
    """Test semua website prioritas"""
    print("🚀 Legal News Indonesia - Priority Testing")
    print("="*70)
    print(f"📊 Total Sites: {len(LEGAL_NEWS_SITES)}")
    print()
    
    # Initialize ingestor
    print("⚙️  Initializing browser...")
    ingestor = WebScrapingIngestor()
    
    try:
        success = await ingestor.initialize()
        if not success:
            print("\n❌ Gagal initialize browser!")
            return
        
        print("✅ Browser ready\n")
        
        # Test semua sites
        results = []
        for i, site in enumerate(LEGAL_NEWS_SITES, 1):
            result = await test_single_site(ingestor, site, i)
            results.append(result)
            
            # Delay antar request (2 detik)
            if i < len(LEGAL_NEWS_SITES):
                print(f"\n⏳ Menunggu 2 detik sebelum site berikutnya...")
                await asyncio.sleep(2)
        
        # Summary
        print("\n" + "="*70)
        print("📊 TESTING SUMMARY")
        print("="*70)
        
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        print(f"\n✅ Berhasil: {len(successful)}/{len(results)} sites")
        print(f"❌ Gagal: {len(failed)}/{len(results)} sites")
        
        if successful:
            print("\n🟢 Sites Berhasil:")
            for r in successful:
                score_emoji = "🟢" if r['score'] >= 0.8 else "🟡" if r['score'] >= 0.7 else "🔴"
                print(f"   {score_emoji} {r['site']} ({r['category']}) - Score: {r['score']:.2f}")
        
        if failed:
            print("\n🔴 Sites Gagal:")
            for r in failed:
                print(f"   ❌ {r['site']} ({r['category']})")
                print(f"      Error: {r.get('error', 'Unknown')[:50]}...")
        
        # Save results
        filename = f"legal_news_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_sites": len(LEGAL_NEWS_SITES),
                "successful": len(successful),
                "failed": len(failed),
                "results": results
            }, f, indent=2, default=str, ensure_ascii=False)
        
        print(f"\n💾 Hasil tersimpan di: {filename}")
        
    except Exception as e:
        print(f"\n❌ ERROR UTAMA: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n🧹 Cleanup...")
        await ingestor.close()
        print("✅ Selesai!")


if __name__ == "__main__":
    try:
        asyncio.run(test_all_sites())
    except KeyboardInterrupt:
        print("\n\n👋 Test dihentikan oleh user")
        sys.exit(0)
