"""
Telegram Commands untuk Web Scraping Knowledge Bridge.

Commands:
- /scrape: Scrape single URL
- /scrape_batch: Scrape multiple URLs
- /scrape_help: Show help
"""

import asyncio
from typing import Optional

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from ..ingestors.knowledge_ingestor import WebScrapingIngestor

router = Router()

# Global ingestor instance
_ingestor: Optional[WebScrapingIngestor] = None


def get_ingestor() -> WebScrapingIngestor:
    """Get or create ingestor instance."""
    global _ingestor
    if _ingestor is None:
        _ingestor = WebScrapingIngestor()
    return _ingestor


@router.message(Command("scrape"))
async def cmd_scrape(message: types.Message):
    """
    /scrape <URL> [domain] [tags]
    
    Scrape single URL dan simpan ke knowledge base.
    
    Contoh:
        /scrape https://www.perplexity.ai/search/abc123 hukum_perdata uu,perplexity
        /scrape https://jdih.kemendagri.go.id/peraturan/xyz789 regulasi jdih
    """
    args = message.text.split(maxsplit=3)[1:]  # Skip command
    
    if not args:
        await message.reply(
            "❌ <b>URL diperlukan</b>\n\n"
            "<b>Penggunaan:</b>\n"
            "/scrape <URL> [domain] [tags]\n\n"
            "<b>Contoh:</b>\n"
            "/scrape https://www.perplexity.ai/search/abc123 hukum_perdata uu,perplexity\n"
            "/scrape https://news.kompas.com/read/123 berita_hukum kompas",
            parse_mode="HTML"
        )
        return
    
    url = args[0]
    domain = args[1] if len(args) > 1 else "general"
    tags = args[2].split(",") if len(args) > 2 else []
    
    # Send initial message
    status_msg = await message.reply(
        f"🔍 <b>Memulai scraping...</b>\n\n"
        f"📎 URL: <code>{url}</code>\n"
        f"🏷️ Domain: <code>{domain}</code>\n"
        f"🏷️ Tags: {', '.join(tags) if tags else 'None'}",
        parse_mode="HTML"
    )
    
    try:
        # Initialize ingestor
        ingestor = get_ingestor()
        if not ingestor._initialized:
            await status_msg.edit_text(
                f"🔍 <b>Memulai scraping...</b>\n"
                f"⚙️ Inisialisasi browser...",
                parse_mode="HTML"
            )
            await ingestor.initialize()
        
        # Scrape
        await status_msg.edit_text(
            f"🔍 <b>Scraping...</b>\n"
            f"📎 <code>{url}</code>\n"
            f"🔄 Extracting content...",
            parse_mode="HTML"
        )
        
        result = await ingestor.scrape_and_ingest(
            url=url,
            domain=domain,
            tags=tags,
        )
        
        if result['success']:
            # Build success message
            success_text = (
                f"✅ <b>Scraping Berhasil!</b>\n\n"
                f"📄 <b>{result['title'][:100]}...</b>\n\n"
                f"📎 URL: <code>{url}</code>\n"
                f"🔧 Extractor: <code>{result['extractor']}</code>\n"
                f"🏷️ Domain: <code>{domain}</code>\n"
            )
            
            if result.get('validation_score'):
                score = result['validation_score']
                emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.7 else "🔴"
                success_text += f"\n⭐ Quality Score: {emoji} <code>{score:.2f}</code>\n"
            
            if result.get('requires_review'):
                success_text += f"⚠️ <b>Perlu review manual</b>\n"
            
            if result.get('doc_id'):
                success_text += f"\n🆔 Doc ID: <code>{result['doc_id']}</code>\n"
            
            if result.get('elapsed_seconds'):
                success_text += f"⏱️ Waktu: <code>{result['elapsed_seconds']:.1f}s</code>\n"
            
            # Add action buttons
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Buka URL",
                        url=url
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🗑️ Hapus",
                        callback_data=f"delete_doc:{result.get('doc_id', '')}"
                    )
                ]
            ])
            
            await status_msg.edit_text(
                success_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            # Build error message
            error_text = (
                f"❌ <b>Scraping Gagal</b>\n\n"
                f"📎 URL: <code>{url}</code>\n"
                f"🔴 Error: <code>{result.get('error', 'Unknown error')}</code>\n"
            )
            
            if result.get('elapsed_seconds'):
                error_text += f"\n⏱️ Waktu: <code>{result['elapsed_seconds']:.1f}s</code>\n"
            
            await status_msg.edit_text(
                error_text,
                parse_mode="HTML"
            )
            
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Error</b>\n\n"
            f"📎 URL: <code>{url}</code>\n"
            f"🔴 Exception: <code>{str(e)}</code>",
            parse_mode="HTML"
        )


@router.message(Command("scrape_batch"))
async def cmd_scrape_batch(message: types.Message):
    """
    /scrape_batch <URL1> <URL2> ... [domain]
    
    Scrape multiple URLs sekaligus.
    
    Contoh:
        /scrape_batch https://url1.com https://url2.com hukum_perdata
    """
    args = message.text.split()[1:]
    
    if len(args) < 2:
        await message.reply(
            "❌ <b>Minimal 2 URL diperlukan</b>\n\n"
            "<b>Penggunaan:</b>\n"
            "/scrape_batch <URL1> <URL2> ... [domain]\n\n"
            "<b>Contoh:</b>\n"
            "/scrape_batch https://url1.com https://url2.com hukum_perdata",
            parse_mode="HTML"
        )
        return
    
    # Last arg mungkin domain jika tidak mengandung http
    if args[-1].startswith('http'):
        urls = args
        domain = "general"
    else:
        urls = args[:-1]
        domain = args[-1]
    
    # Send initial message
    total = len(urls)
    status_msg = await message.reply(
        f"🔍 <b>Batch Scraping</b>\n\n"
        f"📊 Total URL: <code>{total}</code>\n"
        f"🏷️ Domain: <code>{domain}</code>\n"
        f"⏳ Memulai...",
        parse_mode="HTML"
    )
    
    try:
        # Initialize ingestor
        ingestor = get_ingestor()
        if not ingestor._initialized:
            await ingestor.initialize()
        
        results = []
        for i, url in enumerate(urls, 1):
            await status_msg.edit_text(
                f"🔍 <b>Batch Scraping</b>\n\n"
                f"📊 Progress: <code>{i}/{total}</code>\n"
                f"📎 Current: <code>{url[:50]}...</code>",
                parse_mode="HTML"
            )
            
            result = await ingestor.scrape_and_ingest(
                url=url,
                domain=domain,
            )
            results.append(result)
            
            # Small delay antar requests
            await asyncio.sleep(1)
        
        # Summary
        successful = sum(1 for r in results if r.get('success'))
        failed = total - successful
        
        summary_text = (
            f"✅ <b>Batch Scraping Selesai</b>\n\n"
            f"📊 Total: <code>{total}</code>\n"
            f"🟢 Berhasil: <code>{successful}</code>\n"
            f"🔴 Gagal: <code>{failed}</code>\n"
            f"🏷️ Domain: <code>{domain}</code>\n\n"
            f"<b>Details:</b>\n"
        )
        
        for i, result in enumerate(results, 1):
            status = "🟢" if result.get('success') else "🔴"
            title = result.get('title', 'Unknown')[:40]
            summary_text += f"{i}. {status} {title}...\n"
        
        await status_msg.edit_text(
            summary_text,
            parse_mode="HTML"
        )
        
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Batch Error</b>\n\n"
            f"🔴 Exception: <code>{str(e)}</code>",
            parse_mode="HTML"
        )


@router.message(Command("scrape_help"))
async def cmd_scrape_help(message: types.Message):
    """Show scrape help."""
    help_text = """<b>🌐 Web Scraping Knowledge Bridge</b>

<b>Commands:</b>

<b>/scrape <URL> [domain] [tags]</b>
Scrape single URL ke knowledge base.
<i>Contoh:</i> <code>/scrape https://perplexity.ai/search/abc123 hukum_perdata uu,perplexity</code>

<b>/scrape_batch <URL1> <URL2> ... [domain]</b>
Scrape multiple URLs sekaligus.
<i>Contoh:</i> <code>/scrape_batch https://url1.com https://url2.com hukum_perdata</code>

<b>/scrape_help</b>
Show this help message.

<b>Supported Sites:</b>
• Perplexity.ai - AI conversation threads
• JDIH (jdih.kemendagri.go.id) - Peraturan hukum
• News sites (Kompas, Detik, CNN Indonesia, etc.)
• Generic websites - Fallback extraction

<b>Features:</b>
✅ 4-Level validation untuk quality assurance
✅ Automatic extractor selection
✅ Metadata extraction
✅ Quality scoring
✅ Provenance tracking

<b>Tips:</b>
• Gunakan domain spesifik untuk kategorisasi
• Tambahkan tags untuk filtering
• Hasil dengan score < 0.75 perlu review manual"""

    await message.reply(help_text, parse_mode="HTML")


@router.message(Command("scrape_status"))
async def cmd_scrape_status(message: types.Message):
    """Show scraping status/statistics."""
    # This would show statistics from database
    # For now, show basic info
    
    status_text = (
        f"<b>📊 Web Scraping Status</b>\n\n"
        f"🟢 System: <code>Operational</code>\n"
        f"🔧 Extractors: <code>4 active</code>\n"
        f"✅ Validator: <code>4-Level</code>\n\n"
        f"<b>Supported Extractors:</b>\n"
        f"• PerplexityExtractor\n"
        f"• JDIHExtractor\n"
        f"• NewsExtractor\n"
        f"• GenericExtractor\n\n"
        f"<i>Gunakan /scrape_help untuk bantuan</i>"
    )
    
    await message.reply(status_text, parse_mode="HTML")


def register_handlers(dp):
    """Register handlers ke dispatcher."""
    dp.include_router(router)
    print("[INFO] Web scraping handlers registered")