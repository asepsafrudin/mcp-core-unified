"""
WhatsApp Bot Server - Bringing Intelligence to WhatsApp.
Uses WAHA Webhooks to receive messages and AI Service/Knowledge Service to respond.
"""

import os
import sys
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
import mimetypes

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from core.secrets import load_runtime_secrets

load_runtime_secrets()

# Import services (reusing from telegram for intelligence)
sys.path.insert(0, str(project_root / "integrations" / "telegram" / "services"))
from ai_service import GroqAI, GeminiAI
from knowledge_service import KnowledgeService

# Import long-term memory functions
sys.path.insert(0, str(project_root / "memory"))
import longterm

# Import WhatsApp client
from integrations.whatsapp.client import get_whatsapp_client

# Import Dashboard and formatting
from services.correspondence_dashboard import CorrespondenceDashboard, format_search_results

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp-bot")

app = FastAPI(title="WhatsApp Bot Server")

class WhatsAppBot:
    def __init__(self):
        self.ai = None
        self.knowledge = KnowledgeService()
        self.client = get_whatsapp_client()
        self.session = os.getenv("WHATSAPP_SESSION", "default")
        self.dashboard = CorrespondenceDashboard()
        self._init_ai()
        
    def _init_ai(self):
        # Prefer Groq for speed, Gemini as fallback
        groq_key = os.getenv("GROQ_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")
        
        if groq_key:
            self.ai = GroqAI(groq_key, os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"))
            logger.info("✅ Groq AI initialized for WhatsApp")
        elif gemini_key:
            self.ai = GeminiAI(gemini_key, os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
            logger.info("✅ Gemini AI initialized for WhatsApp")

    async def initialize(self):
        await self.knowledge.initialize()
        await longterm.initialize_db()
        # Start polling in the background
        asyncio.create_task(self.polling_loop())
        logger.info("👋 Polling loop started")

    async def polling_loop(self):
        """Poll for new messages if webhooks are not working."""
        # Map of chat_id -> last_processed_msg_id
        last_msg_ids = {}
        
        while True:
            try:
                # 1. Get chats to poll
                chats = await self.client.get_chats(self.session)
                chat_ids = []
                for chat in chats[:15]: # Increase to top 15
                    if not isinstance(chat, dict): continue
                    raw_id = chat.get("id")
                    cid = raw_id.get("_serialized") or raw_id.get("id") if isinstance(raw_id, dict) else raw_id
                    if cid: chat_ids.append(cid)
                
                # 2. Poll each chat
                for chat_id in chat_ids:
                    try:
                        messages = await self.client.get_messages(chat_id, limit=5, session_name=self.session)
                        if not isinstance(messages, list) or not messages:
                            continue

                        # Initialize last_msg_id for this chat if not present
                        if chat_id not in last_msg_ids:
                            raw_mid = messages[0].get("id")
                            last_msg_ids[chat_id] = raw_mid.get("_serialized") or raw_mid.get("id") if isinstance(raw_mid, dict) else raw_mid
                            continue

                        new_messages = []
                        for msg in reversed(messages):
                            if not isinstance(msg, dict): continue
                            
                            raw_mid = msg.get("id")
                            msg_id = raw_mid.get("_serialized") or raw_mid.get("id") if isinstance(raw_mid, dict) else raw_mid
                            
                            if msg_id == last_msg_ids[chat_id]:
                                break
                            
                            # Skip if too old
                            msg_ts = msg.get("timestamp", 0)
                            if datetime.now().timestamp() - msg_ts > 120:
                                continue
                                
                            new_messages.append(msg)
                        
                        # Process new messages
                        for msg in new_messages:
                            if not msg.get("fromMe"):
                                await self.handle_message(msg)
                        
                        # Update last seen
                        raw_mid = messages[0].get("id")
                        last_msg_ids[chat_id] = raw_mid.get("_serialized") or raw_mid.get("id") if isinstance(raw_mid, dict) else raw_mid
                        
                    except Exception as chat_err:
                        logger.error(f"Error polling chat {chat_id}: {chat_err}")
                
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Polling loop crash: {e}")
                await asyncio.sleep(10)

    async def handle_message(self, message_data: Dict[str, Any]):
        """Process incoming WhatsApp message."""
        try:
            # Extract data from WAHA webhook/polling format
            body = message_data.get("body", "")
            from_chat = message_data.get("from", "")
            author = message_data.get("author", "") # Sender in groups
            from_me = message_data.get("fromMe", False)
            message_type = message_data.get("type", "chat")
            has_media = message_data.get("hasMedia", False)

            # Skip self and non-standard messages (unless it has media)
            if from_me:
                return
            
            # Typical text types are 'chat' or 'text'
            if not has_media and message_type not in ["chat", "text"]:
                return

            is_group = from_chat.endswith("@g.us")
            
            # For groups, we require a "!" prefix for AI/Commands, 
            # BUT we allow ALL media for backup purposes (Phase 3 request)
            if is_group and not body.startswith("!") and not has_media:
                return

            logger.info(f"📩 WhatsApp {'Group ' if is_group else ''}Message from {from_chat}: {body[:50]}")
            
            # Process media (Automatic Backup)
            if has_media:
                await self.process_media(from_chat, message_data, author)
                # If it's just a file without a command prefix, we stop here
                if is_group and not body.startswith("!"):
                    return
            
            # Simple command handling
            if body.lower().startswith("!status"):
                await self.send_response(from_chat, "🤖 *Status MCP Unified WhatsApp*\n\n✅ Bot: Online\n✅ AI: Aktif\n✅ Knowledge: Aktif")
                return
            
            # Archive documentation if starting with !save
            if body.lower().startswith("!save "):
                content_to_save = body[6:].strip()
                await self.process_save(from_chat, content_to_save, sender=author)
                return

            # Search archived documentation if starting with !find
            if body.lower().startswith("!find "):
                query = body[6:].strip()
                await self.process_find(from_chat, query)
                return

            # Semantic search if starting with !ask
            if body.lower().startswith("!ask "):
                query = body[5:].strip()
                await self.process_ask(from_chat, query)
                return

            # Register/Update profile if starting with !profile
            if body.lower().startswith("!profile "):
                args = body[9:].strip()
                await self.process_profile(from_chat, author, args)
                return

            # Correspondence Dashboard
            if body.lower().startswith("!dashboard"):
                summary = self.dashboard.get_recent_summary()
                await self.send_response(from_chat, summary)
                return

            # Search letters
            if body.lower().startswith("!cari "):
                query = body[6:].strip()
                results = self.dashboard.search_letters(query)
                formatted_text = format_search_results(results, query)
                await self.send_response(from_chat, formatted_text)
                return

            # Default: AI Chat (Stripping '!' for AI if it survived the is_group check)
            ai_query = body[1:] if body.startswith("!") else body
            await self.process_ai_chat(from_chat, ai_query, sender=author)
            
        except Exception as e:
            logger.error(f"Error handling WhatsApp message: {e}")

    async def process_ask(self, chat_id: str, query: str):
        """Handle semantic search query."""
        try:
            results = await self.knowledge.semantic_search(query, top_k=3)
            if not results:
                await self.send_response(chat_id, "❌ Tidak menemukan informasi relevan di knowledge base.")
                return
                
            response = f"🔍 *Hasil Knowledge Base untuk:* _{query}_\n\n"
            for i, r in enumerate(results, 1):
                response += f"*{i}. {r.source}*\n_{r.content}_\n\n"
            
            await self.send_response(chat_id, response)
        except Exception as e:
            await self.send_response(chat_id, f"❌ Error: {e}")

    async def process_save(self, chat_id: str, content: str, sender: str = ""):
        """Archive content to database."""
        try:
            # Determin type (link or text)
            doc_type = "text"
            if "http://" in content or "https://" in content:
                doc_type = "link"
            
            # Use AI to generate a brief summary for better indexing
            summary = content[:100]
            if self.ai:
                prompt = f"Berikan ringkasan sangat singkat (maks 10 kata) untuk konten berikut agar mudah dicari nanti:\n\n{content}"
                ai_res = await self.ai.generate_response(hash(chat_id), prompt)
                summary = ai_res.text
            
            res = await longterm.doc_save(
                group_id=chat_id,
                doc_type=doc_type,
                content=content,
                sender_id=sender,
                summary=summary
            )
            
            if res.get("success"):
                await self.send_response(chat_id, f"✅ *Tersimpan!* \n📌 Tipe: {doc_type}\n📝 Ringkasan: {summary}")
            else:
                await self.send_response(chat_id, f"❌ Gagal menyimpan: {res.get('error')}")
                
        except Exception as e:
            logger.error(f"Save error: {e}")
            await self.send_response(chat_id, f"❌ Error saat menyimpan: {e}")

    async def process_media(self, chat_id: str, msg: Dict[str, Any], sender: str = ""):
        """Download and archive media."""
        try:
            raw_id = msg.get("id")
            msg_id = raw_id.get("_serialized") or raw_id.get("id") if isinstance(raw_id, dict) else raw_id
            
            # Download
            media_res = await self.client.download_media(msg_id, session_name=self.session)
            if not media_res:
                return
                
            content, content_type = media_res
            
            # Generate filename
            ext = mimetypes.guess_extension(content_type) or ".bin"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{msg_id[:8]}{ext}"
            
            # Use 2026 folder as requested
            storage_path = Path(f"/home/aseps/MCP/storage/whatsapp_media/2026/{filename}")
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(storage_path, "wb") as f:
                f.write(content)
                
            logger.info(f"💾 Media saved: {storage_path}")
            
            # Save to documentation table
            await longterm.doc_save(
                group_id=chat_id,
                doc_type="file",
                content=str(storage_path),
                sender_id=sender,
                summary=f"[AUTO-BACKUP] {msg.get('body', 'File attachment')}",
                metadata={
                    "msg_id": msg_id,
                    "content_type": content_type,
                    "filename": filename,
                    "original_body": msg.get("body")
                }
            )
        except Exception as e:
            logger.error(f"Media process error: {e}")

    async def process_find(self, chat_id: str, query: str):
        """Search archived documentation."""
        try:
            res = await longterm.doc_search(query, group_id=chat_id)
            if not res.get("success") or not res.get("results"):
                await self.send_response(chat_id, "🔍 Tidak ditemukan dokumen yang relevan di arsip grup ini.")
                return
            
            response = f"🔍 *Arsip Ditemukan untuk:* _{query}_\n\n"
            for i, r in enumerate(res["results"], 1):
                timestamp = r['created_at'].split('T')[0]
                response += f"*{i}. [{r['type'].upper()}]* ({timestamp})\n"
                response += f"📝 {r['summary'] or r['content'][:100]}\n"
                response += f"🔗 {r['content'] if r['type'] == 'link' else 'Teks diarsipkan'}\n\n"
            
            await self.send_response(chat_id, response)
        except Exception as e:
            logger.error(f"Find error: {e}")
            await self.send_response(chat_id, f"❌ Error saat mencari arsip: {e}")

    async def process_profile(self, chat_id: str, author_id: str, args: str):
        """Update/View member profile."""
        try:
            if not args or args.lower() == "me":
                profile = await longterm.get_member_profile(author_id)
                if not profile:
                    await self.send_response(chat_id, "ℹ️ Profil Anda belum terdaftar. Gunakan: `!profile nama=... role=... ethics=...`")
                else:
                    msg = f"👤 *Profil Anda:*\n\n"
                    msg += f"📛 Nama: {profile['name'] or '-'}\n"
                    msg += f"💼 Peran: {profile['role'] or '-'}\n"
                    msg += f"📜 Etika: {profile['ethics_notes'] or '-'}"
                    await self.send_response(chat_id, msg)
                return

            # Parse simple key-value args: nama=Asep role=Admin
            updates = {}
            for part in args.split():
                if "=" in part:
                    k, v = part.split("=", 1)
                    updates[k.lower()] = v.replace("_", " ") # Allow underscore for spaces in one word args or just use quotes later

            res = await longterm.upsert_member_profile(
                whatsapp_id=author_id,
                name=updates.get("nama") or updates.get("name"),
                role=updates.get("role"),
                ethics_notes=updates.get("ethics") or updates.get("etika")
            )
            
            if res.get("success"):
                await self.send_response(chat_id, "✅ Profil berhasil diperbarui! Saya akan mengingat data ini saat berbicara dengan Anda.")
            else:
                await self.send_response(chat_id, f"❌ Gagal update profil: {res.get('error')}")

        except Exception as e:
            logger.error(f"Profile error: {e}")
            await self.send_response(chat_id, f"❌ Error profile: {e}")

    async def process_ai_chat(self, chat_id: str, message: str, sender: str = ""):
        """Handle AI chat with RAG context."""
        if not self.ai:
            return
            
        try:
            # 1. Get Group Context/Config
            group_cfg = await longterm.get_group_config(chat_id)
            system_overlay = ""
            if group_cfg:
                system_overlay = f"\n\nContext Grup: {group_cfg['group_name']}\nPrompt Khusus: {group_cfg['system_prompt']}"

            # 2. Get User Profile Context
            user_profile = await longterm.get_member_profile(sender)
            user_overlay = ""
            if user_profile:
                user_overlay = f"\n\nLawan Bicara (User): {user_profile['name']}\nPeran: {user_profile['role']}\nCatatan Etika: {user_profile['ethics_notes']}\nAdaptasikan gaya bicara sesuai etika tersebut."
            else:
                user_overlay = f"\n\nLawan Bicara ID: {sender} (Profil tidak dikenal, gunakan gaya formal umum)."

            # 3. Get Knowledge Context
            kb_context = await self.knowledge.get_context_for_query(message)
            
            # Combine all context
            full_context = f"{system_overlay}{user_overlay}\n\nPengetahuan Relevan:\n{kb_context}"
            
            # Use user_id for session tracking (simplified)
            user_id = hash(chat_id) % (10**8)
            
            ai_res = await self.ai.generate_response(user_id, message, context=full_context)
            response_text = ai_res.text
            
            await self.send_response(chat_id, response_text)
        except Exception as e:
            logger.error(f"AI error: {e}")

    async def send_response(self, chat_id: str, text: str):
        """Helper to send text back to WhatsApp."""
        try:
            await self.client.send_message(chat_id=chat_id, text=text, session_name=self.session)
        except Exception as e:
            logger.error(f"Failed to send WhatsApp response: {e}")

bot = WhatsAppBot()

@app.on_event("startup")
async def startup_event():
    await bot.initialize()

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """
    WAHA Webhook endpoint.
    Reference: https://waha.devv.com/docs/how-to/webhooks/
    """
    try:
        data = await request.json()
        event_type = data.get("event")
        
        # WAHA sends event 'message' for new messages
        if event_type == "message":
            payload = data.get("payload", {})
            background_tasks.add_task(bot.handle_message, payload)
            
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    port = int(os.getenv("WHATSAPP_BOT_PORT", "8008"))
    uvicorn.run(app, host="0.0.0.0", port=port)
