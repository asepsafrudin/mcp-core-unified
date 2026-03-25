"""Telegram Bot Server - Modular Version (Lightweight).

Refactored from monolithic bot_server.py to modular architecture.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

from core.config import TelegramConfig
from core.ai_providers import GroqAI, GeminiAI, GROQ_AVAILABLE, GEMINI_AVAILABLE
from core.mcp_integration import MCPIntegration
from core import ui_text as UI
from file_storage import storage as file_storage

# Import KnowledgeService directly to avoid package import issues
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "services"))
from knowledge_service import KnowledgeService
from text_to_sql_service import TextToSQLService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModularBotServer:
    """Lightweight Telegram Bot Server with MCP integration."""
    
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.app: Optional[Application] = None
        self.sessions: Dict[int, Dict] = {}
        self.ai = None
        self.mcp = MCPIntegration()
        self.knowledge = KnowledgeService()
        self.text_to_sql = None
        self.ai_type = "none"
        self._init_ai()
        self._init_text_to_sql()
    
    def _init_text_to_sql(self):
        """Initialize Text-to-SQL service."""
        try:
            if self.ai:
                self.text_to_sql = TextToSQLService(ai_service=self.ai)
                logger.info("✅ Text-to-SQL service initialized")
            else:
                logger.warning("⚠️ Text-to-SQL service not initialized - AI not available")
        except Exception as e:
            logger.error(f"❌ Text-to-SQL init failed: {e}")
    
    def _init_ai(self):
        """Initialize AI provider."""
        if self.config.ai_provider == "groq" and GROQ_AVAILABLE and self.config.groq_api_key:
            try:
                self.ai = GroqAI(self.config.groq_api_key, self.config.groq_model)
                self.ai_type = "groq"
                logger.info(f"✅ Groq AI: {self.config.groq_model}")
            except Exception as e:
                logger.error(f"❌ Groq init failed: {e}")
        elif self.config.ai_provider == "gemini" and GEMINI_AVAILABLE and self.config.gemini_api_key:
            try:
                self.ai = GeminiAI(self.config.gemini_api_key, self.config.gemini_model)
                self.ai_type = "gemini"
                logger.info(f"✅ Gemini AI: {self.config.gemini_model}")
            except Exception as e:
                logger.error(f"❌ Gemini init failed: {e}")
    
    def is_allowed(self, user_id: int) -> bool:
        """Check user authorization."""
        return not self.config.allowed_users or user_id in self.config.allowed_users
    
    def _build_keyboard(self, buttons: list) -> InlineKeyboardMarkup:
        """Build inline keyboard from button list."""
        keyboard = []
        for row in buttons:
            keyboard.append([InlineKeyboardButton(text, callback_data=data) for text, data in row])
        return InlineKeyboardMarkup(keyboard)
    
    # ═══════════════════════════════════════════════════════════
    # COMMAND HANDLERS
    # ═══════════════════════════════════════════════════════════
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        if not self.is_allowed(user.id):
            await update.message.reply_text("⛔ *Akses Ditolak*", parse_mode="Markdown")
            return
        
        self.sessions[user.id] = {"started_at": datetime.now().isoformat(), "count": 0}
        
        text = UI.WELCOME_TEXT.format(name=user.first_name)
        keyboard = self._build_keyboard(UI.MAIN_MENU_KEYBOARD)
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        import platform
        ai_status = "🟢" if self.ai else "🔴"
        mcp_status = "🟢" if self.mcp.is_available else "🔴"
        kb_status = "🟢" if self.knowledge.is_available else "🔴"
        
        # Get knowledge stats if available
        kb_info = ""
        if self.knowledge.is_available:
            try:
                stats = await self.knowledge.get_stats()
                total_docs = stats.get('total_documents', 0)
                kb_info = f" ({total_docs} docs)"
            except:
                pass
        
        text = (
            f"*Status Sistem*\n\n"
            f"🟢 Bot: Online\n"
            f"{ai_status} AI: {self.ai_type.upper()}\n"
            f"{mcp_status} MCP: Connected\n"
            f"{kb_status} Knowledge DB:{kb_info}\n"
            f"🖥 OS: {platform.system()} {platform.release()}\n"
            f"🐍 Python: {platform.python_version()}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command."""
        user = update.effective_user
        if self.ai:
            self.ai.reset(user.id)
        await update.message.reply_text("🧹 *Konteks direset*", parse_mode="Markdown")
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        text = (
            "📖 *Bantuan*\n\n"
            "*Commands Umum:*\n"
            "`/start` - Menu utama\n"
            "`/status` - Cek status sistem\n"
            "`/clear` - Reset chat context\n"
            "`/help` - Bantuan ini\n\n"
            "*Knowledge Base:*\n"
            "`/ask <pertanyaan>` - Semantic search RAG\n"
            "`/sql <query>` - Query database SQL (manual)\n"
            "`/query <pertanyaan>` - Query dengan bahasa natural\n"
            "`/knowledge` - Info knowledge base\n\n"
            "*Cline Bridge:*\n"
            "`/cline <pesan>` - Kirim ke Cline\n\n"
            "*Chat AI:*\n"
            "💬 Kirim pesan langsung untuk chat dengan AI Groq\n"
            "🤖 AI akan otomatis mencari di knowledge base untuk konteks"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ask command - Semantic search di knowledge base."""
        user = update.effective_user
        
        if not self.is_allowed(user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "🔍 *Knowledge Search*\n\n"
                "Cari informasi di knowledge base menggunakan semantic search.\n\n"
                "*Penggunaan:* `/ask <pertanyaan>`\n"
                "*Contoh:*\n"
                "`/ask apa itu RPJPD?`\n"
                "`/ask prosedur pengadaan barang`\n\n"
                "💡 Bot akan mencari dokumen yang relevan di knowledge base.",
                parse_mode="Markdown"
            )
            return
        
        query = " ".join(args)
        
        if not self.knowledge.is_available:
            await update.message.reply_text(
                "⚠️ *Knowledge Service tidak tersedia*\n\n"
                "Pastikan PostgreSQL dan RAG Engine sudah running.",
                parse_mode="Markdown"
            )
            return
        
        # Send processing message
        thinking = await update.message.reply_text(
            f"🔍 Mencari: *{query}*...",
            parse_mode="Markdown"
        )
        
        try:
            # Perform semantic search
            results = await self.knowledge.semantic_search(
                query=query,
                top_k=5,
                min_similarity=0.7
            )
            
            if not results:
                await thinking.edit_text(
                    "❌ *Tidak menemukan informasi yang relevan.*\n\n"
                    "Coba gunakan kata kunci yang berbeda.",
                    parse_mode="Markdown"
                )
                return
            
            # Format response
            response = f"🔍 *Hasil untuk:* _{query}_\n\n"
            
            for i, r in enumerate(results[:5], 1):
                source_name = r.source if r.source != "Unknown" else "Knowledge Base"
                similarity = r.similarity * 100
                content = r.content[:200] if len(r.content) > 200 else r.content
                
                response += (
                    f"*{i}. {source_name}*\n"
                    f"⭐ Relevansi: {similarity:.1f}%\n"
                    f"_{content}_\n\n"
                )
            
            await thinking.edit_text(response, parse_mode="Markdown")
            logger.info(f"✅ Knowledge search completed for: {query[:50]}")
            
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            await thinking.edit_text(
                f"❌ *Error:* `{str(e)}`",
                parse_mode="Markdown"
            )
    
    async def cmd_sql(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sql command - Query database SQL."""
        user = update.effective_user
        
        if not self.is_allowed(user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "📊 *SQL Query*\n\n"
                "Query knowledge database menggunakan SQL.\n\n"
                "*Penggunaan:* `/sql <query>`\n"
                "*Contoh:*\n"
                "`/sql SELECT * FROM knowledge_documents LIMIT 5`\n"
                "`/sql SELECT namespace, COUNT(*) FROM knowledge_documents GROUP BY namespace`\n\n"
                "⚠️ *Hanya SELECT query yang diizinkan*",
                parse_mode="Markdown"
            )
            return
        
        query = " ".join(args)
        
        if not self.knowledge.is_available:
            await update.message.reply_text(
                "⚠️ *Knowledge Service tidak tersedia*\n\n"
                "Pastikan PostgreSQL sudah running.",
                parse_mode="Markdown"
            )
            return
        
        # Send processing message
        thinking = await update.message.reply_text(
            "📊 *Menjalankan query...*",
            parse_mode="Markdown"
        )
        
        try:
            # Execute SQL query
            result = await self.knowledge.sql_query(query)
            
            if not result:
                await thinking.edit_text(
                    "❌ *Query gagal dieksekusi.*",
                    parse_mode="Markdown"
                )
                return
            
            if result.row_count == 0:
                await thinking.edit_text(
                    "📊 *Query berhasil*\n\n"
                    "Tidak ada data yang ditemukan.",
                    parse_mode="Markdown"
                )
                return
            
            # Format response
            response = f"📊 *Hasil Query*\n"
            response += f"```sql\n{result.query[:100]}\n```\n\n"
            
            # Format as table
            if result.row_count <= 10:
                # Header
                header = " | ".join(result.columns)
                response += f"*{header}*\n"
                response += "—" * len(header) + "\n"
                
                # Rows
                for row in result.rows:
                    row_str = " | ".join(str(cell)[:30] for cell in row)
                    response += f"`{row_str}`\n"
                
                response += f"\n_Total: {result.row_count} rows_"
            else:
                response += f"_Total: {result.row_count} rows_\n"
                response += "_(Hasil terlalu banyak, ditampilkan 10 pertama)_\n\n"
                
                # Header
                header = " | ".join(result.columns)
                response += f"*{header}*\n"
                
                # First 10 rows
                for row in result.rows[:10]:
                    row_str = " | ".join(str(cell)[:30] for cell in row)
                    response += f"`{row_str}`\n"
            
            await thinking.edit_text(response, parse_mode="Markdown")
            logger.info(f"✅ SQL query completed: {result.row_count} rows")
            
        except Exception as e:
            logger.error(f"SQL query failed: {e}")
            await thinking.edit_text(
                f"❌ *Error:* `{str(e)}`",
                parse_mode="Markdown"
            )
    
    async def cmd_knowledge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /knowledge command - Knowledge base info."""
        user = update.effective_user
        
        if not self.is_allowed(user.id):
            return
        
        if not self.knowledge.is_available:
            await update.message.reply_text(
                "⚠️ *Knowledge Service tidak tersedia*\n\n"
                "Pastikan PostgreSQL sudah running.",
                parse_mode="Markdown"
            )
            return
        
        try:
            stats = await self.knowledge.get_stats()
            namespaces = await self.knowledge.list_namespaces()
            
            response = (
                "📚 *Knowledge Base Info*\n\n"
                f"📄 Total Dokumen: `{stats.get('total_documents', 0)}`\n"
                f"🔍 RAG Available: `{'✅' if stats.get('rag_available') else '❌'}`\n\n"
                "*Namespaces:*\n"
            )
            
            for ns in namespaces[:10]:
                response += f"— `{ns['name']}`: {ns['document_count']} docs\n"
            
            response += "\n*Commands:*\n"
            response += "`/ask <query>` - Semantic search\n"
            response += "`/sql <query>` - SQL query (manual)\n"
            response += "`/query <question>` - SQL dengan bahasa natural\n"
            response += "`/knowledge` - Info ini"
            
            await update.message.reply_text(response, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Knowledge info failed: {e}")
            await update.message.reply_text(
                f"❌ *Error:* `{str(e)}`",
                parse_mode="Markdown"
            )
    
    async def cmd_cline(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cline command - Forward to Cline Agent."""
        user = update.effective_user
        
        if not self.is_allowed(user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "👤 *Cline Bridge*\n\n"
                "Kirim pesan ke Cline Agent untuk diproses.\n\n"
                "*Penggunaan:* `/cline <pesan>`\n"
                "*Contoh:* `/cline Tolong fix bug di main.py`\n\n"
                "💡 Pesan akan diteruskan ke Cline dan ditampilkan di VS Code.",
                parse_mode="Markdown"
            )
            return
        
        message_text = " ".join(args)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        message_key = f"telegram_cline_{user.id}_{timestamp}"
        
        # Confirm to user
        confirm_msg = await update.message.reply_text(
            "👤 *Pesan Diteruskan ke Cline*\n\n"
            f"💬 _{message_text[:100]}{'...' if len(message_text) > 100 else ''}_\n\n"
            "⏳ Menunggu respon dari Cline...",
            parse_mode="Markdown"
        )
        
        # Save to file storage (primary) dan MCP (backup jika available)
        try:
            # Save ke file storage
            file_storage.save_message(
                key=message_key,
                content=message_text,
                metadata={
                    "user_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "chat_id": update.message.chat_id,
                    "message_id": confirm_msg.message_id,
                    "type": "telegram_bridge_to_cline",
                    "status": "pending",
                    "needs_human_response": True,
                    "timestamp": datetime.now().isoformat()
                }
            )
            logger.info(f"📨 Cline message saved to file: {message_text[:50]}... (key: {message_key})")
            
            # Backup ke MCP jika available
            if self.mcp.is_available:
                try:
                    await self.mcp.save_memory(
                        key=message_key,
                        content=message_text,
                        metadata={
                            "user_id": user.id,
                            "username": user.username,
                            "first_name": user.first_name,
                            "chat_id": update.message.chat_id,
                            "message_id": confirm_msg.message_id,
                            "type": "telegram_bridge_to_cline",
                            "status": "pending",
                            "needs_human_response": True,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    logger.info(f"📨 Cline message backup to MCP: {message_key}")
                except Exception as mcp_err:
                    logger.warning(f"⚠️ Failed to backup to MCP: {mcp_err}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save cline message: {e}")
            await update.message.reply_text(
                "❌ Gagal menyimpan pesan. Silakan coba lagi.",
                parse_mode="Markdown"
            )
    
    async def cmd_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /query command - Text-to-SQL natural language query."""
        user = update.effective_user
        
        if not self.is_allowed(user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "📊 *Query Database dengan Bahasa Natural*\n\n"
                "Kirim pertanyaan dalam Bahasa Indonesia/Inggris,\n"
                "saya akan konversi ke SQL dan eksekusi.\n\n"
                "*Penggunaan:* `/query <pertanyaan>`\n\n"
                "*Contoh:*\n"
                "— `/query berapa dokumen PUU 2026?`\n"
                "— `/query list semua task yang pending`\n"
                "— `/query total telegram messages hari ini`",
                parse_mode="Markdown"
            )
            return
        
        question = " ".join(args)
        
        # Check if text_to_sql service is available
        if not self.text_to_sql:
            await update.message.reply_text(
                "⚠️ *Text-to-SQL Service tidak tersedia*\n\n"
                "Service belum diinisialisasi. Hubungi administrator.",
                parse_mode="Markdown"
            )
            return
        
        # Check if knowledge service is available
        if not self.knowledge.is_available:
            await update.message.reply_text(
                "⚠️ *Knowledge Service tidak tersedia*\n\n"
                "Database belum terhubung. Hubungi administrator.",
                parse_mode="Markdown"
            )
            return
        
        # Send thinking message
        thinking_msg = await update.message.reply_text(
            "🤔 *Menganalisis pertanyaan...*",
            parse_mode="Markdown"
        )
        
        try:
            # Execute natural language query
            result = await self.text_to_sql.execute_natural_query(
                question=question,
                knowledge_service=self.knowledge
            )
            
            # Format result
            formatted_text = self.text_to_sql.format_result_as_text(result)
            
            # Send result
            await thinking_msg.edit_text(
                formatted_text,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Query command error: {e}")
            await thinking_msg.edit_text(
                f"❌ *Terjadi kesalahan*\n\n"
                f"```{str(e)[:200]}```",
                parse_mode="Markdown"
            )
    
    async def _notify_cline_new_message(self, user, message_text: str, message_key: str):
        """Buat notifikasi untuk Cline agent."""
        try:
            # Simpan notifikasi khusus untuk Cline
            await self.mcp.save_memory(
                key=f"cline_notification_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                content=f"📨 Pesan baru dari Telegram:\n\nUser: {user.first_name} (@{user.username})\nPesan: {message_text}",
                metadata={
                    "notification_type": "telegram_to_cline",
                    "original_key": message_key,
                    "user_id": user.id,
                    "username": user.username,
                    "priority": "high",
                    "timestamp": datetime.now().isoformat()
                }
            )
            logger.info(f"🔔 Cline notification created for message: {message_key}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to create Cline notification: {e}")
    
    async def _save_chat_to_knowledge(self, user, message: str, response: str):
        """Save chat interaction to knowledge base for future context."""
        try:
            # Only save if it's a meaningful interaction
            if len(message) < 10 or len(response) < 20:
                return
            
            # Generate embedding for the chat
            query_embedding = await self.knowledge._generate_embedding(
                f"User: {message}\nAI: {response[:200]}"
            )
            
            if query_embedding:
                async with self.knowledge.db_pool.acquire() as conn:
                    embedding_str = "[" + ",".join(str(f) for f in query_embedding) + "]"
                    await conn.execute("""
                        INSERT INTO knowledge_documents (id, content, embedding, metadata, namespace)
                        VALUES ($1, $2, $3::vector, $4, $5)
                    """, 
                        f"chat_{user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        f"Q: {message}\nA: {response}",
                        embedding_str,
                        json.dumps({
                            "user_id": user.id,
                            "username": user.username,
                            "type": "chat_history",
                            "source": "telegram_bot"
                        }),
                        "chat_history"
                    )
                    logger.info(f"💾 Chat saved to Knowledge Base for RAG")
        except Exception as e:
            logger.debug(f"Knowledge base save skipped: {e}")
    
    # ═══════════════════════════════════════════════════════════
    # CALLBACK HANDLERS
    # ═══════════════════════════════════════════════════════════
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries with modern UI."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user = update.effective_user
        
        if not self.is_allowed(user.id):
            return
        
        # Menu callbacks dengan UI modern dari ui_handlers
        menu_configs = {
            'menu_knowledge': {
                'text': UI.MENU_KNOWLEDGE,
                'buttons': [[("🔍 Search", "action_knowledge_search")], [("⬅️ Back", "back_home")]]
            },
            'menu_vision': {
                'text': UI.MENU_VISION,
                'buttons': [[("🖼️ History", "action_vision_history")], [("⬅️ Back", "back_home")]]
            },
            'menu_office': {
                'text': UI.MENU_OFFICE,
                'buttons': [[("📖 Read", "action_office_read")], [("⬅️ Back", "back_home")]]
            },
            'menu_code': {
                'text': UI.MENU_CODE,
                'buttons': [[("🔍 Analyze", "action_code_analyze")], [("⬅️ Back", "back_home")]]
            },
            'menu_notify': {
                'text': UI.MENU_NOTIFY,
                'buttons': [[("👤 Cline", "action_cline_send")], [("⬅️ Back", "back_home")]]
            },
            'menu_chat': {
                'text': UI.MENU_CHAT,
                'buttons': [[("🏠 Home", "menu_home")]]
            },
            'menu_cline': {
                'text': UI.MENU_CLINE,
                'buttons': [[("✉️ Kirim", "action_cline_send")], [("⬅️ Back", "back_home")]]
            },
        }
        
        if data in menu_configs:
            config = menu_configs[data]
            keyboard = self._build_keyboard(config['buttons'])
            await query.edit_message_text(config['text'], parse_mode="Markdown", reply_markup=keyboard)
        
        elif data == 'menu_system':
            await self.cmd_status(update, context)
        
        elif data == 'menu_home' or data == 'back_home':
            text = UI.WELCOME_TEXT.format(name=user.first_name)
            keyboard = self._build_keyboard(UI.MAIN_MENU_KEYBOARD)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        
        # Action callbacks - eksekusi langsung
        elif data == 'action_cline_send':
            # Simulasi kirim ke Cline
            await query.edit_message_text(
                "👤 *Cline Bridge*\n\n"
                "Kirim pesan ke Cline:\n\n"
                "💡 Ketik: `/cline <pesan>`\n\n"
                "atau balas pesan ini dengan pesan Anda.",
                parse_mode="Markdown",
                reply_markup=self._build_keyboard(UI.BACK_KEYBOARD)
            )
        
        elif data == 'action_knowledge_search':
            await query.edit_message_text(
                "🔍 *Knowledge Search*\n\n"
                "💡 Ketik: `/ask <pertanyaan>`\n\n"
                "Contoh: `/ask prosedur pengadaan`",
                parse_mode="Markdown",
                reply_markup=self._build_keyboard(UI.BACK_KEYBOARD)
            )
        
        elif data == 'action_vision_history':
            await query.edit_message_text(
                "🖼️ *Vision History*\n\n"
                "_Riwayat analisis gambar akan ditampilkan di sini._\n\n"
                "💡 Kirim foto untuk analisis baru.",
                parse_mode="Markdown",
                reply_markup=self._build_keyboard(UI.BACK_KEYBOARD)
            )
        
        elif data == 'action_office_read':
            await query.edit_message_text(
                "📖 *Office Read*\n\n"
                "_Kirim file (PDF/DOCX/XLSX) untuk dibaca._\n\n"
                "💡 Maksimum file: 20MB",
                parse_mode="Markdown",
                reply_markup=self._build_keyboard(UI.BACK_KEYBOARD)
            )
        
        elif data == 'action_code_analyze':
            await query.edit_message_text(
                "🔍 *Code Analyzer*\n\n"
                "💡 Ketik: `/analyze <filepath>`\n\n"
                "Contoh: `/analyze /home/project/main.py`",
                parse_mode="Markdown",
                reply_markup=self._build_keyboard(UI.BACK_KEYBOARD)
            )
    
    # ═══════════════════════════════════════════════════════════
    # MESSAGE HANDLERS
    # ═══════════════════════════════════════════════════════════
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages with AI streaming."""
        user = update.effective_user
        message = update.message.text
        
        # Log received message
        logger.info(f"📩 Message from {user.id} ({user.username or user.first_name}): {message[:50]}...")
        
        if not self.is_allowed(user.id):
            logger.warning(f"⛔ User {user.id} not allowed")
            await update.message.reply_text("⛔ *Akses Ditolak*\n\nAnda tidak memiliki izin untuk menggunakan bot ini.", parse_mode="Markdown")
            return
        
        if not self.ai:
            logger.error("❌ AI not configured")
            await update.message.reply_text("⚠️ *AI Not Configured*\n\nBot belum terhubung ke AI provider.", parse_mode="Markdown")
            return
        
        # Update session
        self.sessions[user.id] = self.sessions.get(user.id, {})
        self.sessions[user.id]["count"] = self.sessions[user.id].get("count", 0) + 1
        
        # Send thinking message
        thinking = await update.message.reply_text("🤔 *Sedang memproses...*", parse_mode="Markdown")
        
        try:
            # Get context from Knowledge Base + MCP
            context_parts = []
            
            # 1. Search Knowledge Base
            if self.knowledge.is_available:
                try:
                    kb_context = await self.knowledge.get_context_for_query(message)
                    if kb_context:
                        context_parts.append(kb_context)
                        logger.info(f"📚 Found KB context for query")
                except Exception as kb_err:
                    logger.warning(f"⚠️ KB context search failed: {kb_err}")
            
            # 2. Search MCP Memory
            if self.mcp.is_available:
                try:
                    memories = await self.mcp.search_context(message, limit=3)
                    if memories:
                        mcp_context = "\n\n".join([m.get("content", "") for m in memories])
                        context_parts.append(f"## Konteks dari Memory:\n{mcp_context}")
                        logger.info(f"📚 Found {len(memories)} context memories")
                except Exception as ctx_err:
                    logger.warning(f"⚠️ Context search failed: {ctx_err}")
            
            context = "\n\n".join(context_parts) if context_parts else ""
            
            # Stream response dengan rate limiting
            full = ""
            last = ""
            chunk_count = 0
            edit_count = 0
            
            async for chunk in self.ai.generate_stream(user.id, message, context):
                full += chunk
                chunk_count += 1
                
                # Rate limiting: update setiap 15 chunks atau 100 karakter
                if chunk_count >= 15 or len(full) - len(last) >= 100:
                    if full != last and len(full) > len(last):
                        try:
                            await thinking.edit_text(full[:4096])
                            last = full
                            chunk_count = 0
                            edit_count += 1
                            
                            # Delay untuk mencegah flood control (setiap 5 edits)
                            if edit_count % 5 == 0:
                                await asyncio.sleep(0.5)
                        except Exception as edit_err:
                            logger.warning(f"⚠️ Edit message failed: {edit_err}")
                            pass
            
            # Final update
            if full != last:
                try:
                    await thinking.edit_text(full[:4096])
                except Exception:
                    # Jika edit gagal, kirim sebagai pesan baru
                    await update.message.reply_text(full[:4096])
            
            # Save to MCP Memory (LTM)
            if self.mcp.is_available:
                try:
                    memory_key = f"telegram_chat_{user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    await self.mcp.save_memory(
                        key=memory_key,
                        content=f"User: {message}\nAI: {full}",
                        metadata={
                            "user_id": user.id,
                            "username": user.username,
                            "first_name": user.first_name,
                            "type": "telegram_chat",
                            "source": "telegram_bot",
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    logger.info(f"💾 Chat auto-saved to LTM: {memory_key}")
                except Exception as mem_err:
                    logger.warning(f"⚠️ Failed to save to LTM: {mem_err}")
            
            # Also save to Knowledge Base if enabled
            if self.knowledge.is_available:
                try:
                    # Save chat summary to knowledge base for future RAG
                    await self._save_chat_to_knowledge(user, message, full)
                except Exception as kb_err:
                    logger.debug(f"Could not save to knowledge base: {kb_err}")
            
            logger.info(f"✅ Response sent to {user.id} ({len(full)} chars, {edit_count} edits)")
        
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}", exc_info=True)
            try:
                await thinking.edit_text(
                    "❌ *Maaf, terjadi kesalahan*\n\n"
                    "Silakan coba lagi dalam beberapa saat.",
                    parse_mode="Markdown"
                )
            except Exception:
                # Jika edit juga gagal, coba kirim pesan baru
                try:
                    await update.message.reply_text(
                        "❌ Maaf, terjadi kesalahan saat memproses pesan.",
                        parse_mode="Markdown"
                    )
                except Exception:
                    logger.error("❌ Failed to send error message")
    
    # ═══════════════════════════════════════════════════════════
    # SETUP & RUN
    # ═══════════════════════════════════════════════════════════
    
    def setup(self):
        """Setup handlers."""
        self.app = Application.builder().token(self.config.bot_token).build()
        
        # Commands
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("clear", self.cmd_clear))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("cline", self.cmd_cline))
        
        # Knowledge commands
        self.app.add_handler(CommandHandler("ask", self.cmd_ask))
        self.app.add_handler(CommandHandler("sql", self.cmd_sql))
        self.app.add_handler(CommandHandler("query", self.cmd_query))
        self.app.add_handler(CommandHandler("knowledge", self.cmd_knowledge))
        
        # Callbacks
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Messages
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info("✅ Handlers registered")
    
    async def run(self):
        """Run the bot."""
        self.setup()
        
        # Initialize Knowledge Service
        logger.info("🔄 Initializing Knowledge Service...")
        kb_initialized = await self.knowledge.initialize()
        if kb_initialized:
            logger.info("✅ Knowledge Service ready")
        else:
            logger.warning("⚠️ Knowledge Service not available (RAG/SQL disabled)")
        
        await self.app.initialize()
        await self.app.start()
        
        if self.config.mode == "webhook":
            await self.app.updater.start_webhook(
                listen="0.0.0.0",
                port=self.config.webhook_port,
                webhook_url=self.config.webhook_url
            )
        else:
            await self.app.updater.start_polling(drop_pending_updates=True)
        
        logger.info("🚀 Bot is running!")
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Stopping...")
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()


async def main():
    """Main entry point."""
    config = TelegramConfig.from_env()
    bot = ModularBotServer(config)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
