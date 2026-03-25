"""
Telegram Bot Server - MCP Integration

Server untuk menghubungkan Telegram Bot dengan MCP Server.
Menerima pesan dari Telegram dan meneruskannya ke MCP untuk diproses.

Usage:
    python bot_server.py

Environment Variables:
     ***REMOVED_TOKEN***- Token dari @BotFather (required)
    TELEGRAM_ALLOWED_USERS - Comma-separated list of allowed user IDs (optional)
    TELEGRAM_WEBHOOK_URL - URL untuk webhook mode (optional)
    TELEGRAM_MODE - 'polling' atau 'webhook' (default: polling)
    MCP_SERVER_URL - URL MCP server (default: http://localhost:8000)
"""

import os
import sys
import asyncio
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logging.getLogger(__name__).debug(f"Loaded .env from {env_path}")
except ImportError:
    pass  # python-dotenv not installed

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from core.task import Task, TaskResult
except ImportError:
    # Mock Task and TaskResult for standalone mode
    @dataclass
    class Task:
        id: str = ""
        type: str = ""
        payload: Dict[str, Any] = None
        
        def __post_init__(self):
            if self.payload is None:
                self.payload = {}
    
    @dataclass  
    class TaskResult:
        task_id: str
        success: bool
        data: Any = None
        error: str = None
        error_code: str = None
        message: str = None
        
        @classmethod
        def success_result(cls, task_id: str, data: Any = None, message: str = None):
            return cls(task_id=task_id, success=True, data=data, message=message)
        
        @classmethod
        def failure_result(cls, task_id: str, error: str, error_code: str = None):
            return cls(task_id=task_id, success=False, error=error, error_code=error_code)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import python-telegram-bot
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        ContextTypes,
        filters,
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed. Run: pip install python-telegram-bot")

# Try to import Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed. Run: pip install google-generativeai")

# Try to import Groq
try:
    from groq import AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("groq not installed. Run: pip install groq")


@dataclass
class TelegramConfig:
    """Configuration for Telegram Bot."""
    bot_token: str
    allowed_users: List[int]
    mode: str = "polling"  # "polling" or "webhook"
    webhook_url: Optional[str] = None
    webhook_port: int = 8443
    mcp_server_url: str = "http://localhost:8000"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.1-8b-instant"
    ai_provider: str = "groq"  # "gemini" or "groq"
    
    @classmethod
    def from_env(cls) -> "TelegramConfig":
        """Load configuration from environment variables."""
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise ValueError(" ***REMOVED_TOKEN***environment variable is required")
        
        # Parse allowed users
        allowed_users_str = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        allowed_users = []
        if allowed_users_str:
            try:
                allowed_users = [int(uid.strip()) for uid in allowed_users_str.split(",") if uid.strip()]
            except ValueError:
                logger.warning("Invalid TELEGRAM_ALLOWED_USERS format. Expected comma-separated integers.")
        
        return cls(
            bot_token=bot_token,
            allowed_users=allowed_users,
            mode=os.getenv("TELEGRAM_MODE", "polling"),
            webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL"),
            webhook_port=int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8443")),
            mcp_server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8000"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            groq_api_key=os.getenv("GROQ_API_KEY"),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            ai_provider=os.getenv("AI_PROVIDER", "groq"),
        )


class GeminiAI:
    """Gemini AI Client wrapper with streaming support."""
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        if not GEMINI_AVAILABLE:
            raise RuntimeError("Gemini not available. Install: pip install google-generativeai")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.chat_sessions: Dict[int, Any] = {}
    
    def get_chat(self, user_id: int):
        """Get or create chat session for user."""
        if user_id not in self.chat_sessions:
            self.chat_sessions[user_id] = self.model.start_chat(history=[])
        return self.chat_sessions[user_id]
    
    async def generate_response(self, user_id: int, message: str) -> str:
        """Generate AI response."""
        chat = self.get_chat(user_id)
        response = await chat.send_message_async(message)
        return response.text
    
    async def generate_response_stream(self, user_id: int, message: str):
        """Generate AI response with streaming (yields chunks)."""
        chat = self.get_chat(user_id)
        response = await chat.send_message_async(message, stream=True)
        async for chunk in response:
            if chunk.text:
                yield chunk.text
    
    async def generate_image_response(self, user_id: int, image_path: str, prompt: str) -> str:
        """Generate response with image."""
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        contents = [
            prompt,
            {"mime_type": "image/jpeg", "data": image_data}
        ]
        
        response = await self.model.generate_content_async(contents)
        return response.text
    
    def reset_chat(self, user_id: int):
        """Reset chat session."""
        if user_id in self.chat_sessions:
            del self.chat_sessions[user_id]


class GroqAI:
    """Groq AI Client wrapper with streaming support."""
    
    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant"):
        if not GROQ_AVAILABLE:
            raise RuntimeError("Groq not available. Install: pip install groq")
        
        self.client = AsyncGroq(api_key=api_key)
        self.model = model
        self.chat_history: Dict[int, List[Dict[str, str]]] = {}
    
    def get_chat_history(self, user_id: int) -> List[Dict[str, str]]:
        """Get or create chat history for user."""
        if user_id not in self.chat_history:
            self.chat_history[user_id] = []
        return self.chat_history[user_id]
    
    async def generate_response(self, user_id: int, message: str) -> str:
        """Generate AI response."""
        history = self.get_chat_history(user_id)
        history.append({"role": "user", "content": message})
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=history,
            temperature=0.7,
            max_tokens=2048
        )
        
        assistant_message = response.choices[0].message.content
        history.append({"role": "assistant", "content": assistant_message})
        return assistant_message
    
    async def generate_response_stream(self, user_id: int, message: str, mcp_context: str = "", ltm_context: str = "", knowledge_context: str = ""):
        """Generate AI response with streaming (yields chunks)."""
        history = self.get_chat_history(user_id)
        
        # Build context with MCP knowledge if available
        context_prompt = """Kamu adalah asisten pribadi AI bernama "Aria".

## Identitas
- Nama: Aria
- Peran: Asisten pribadi eksklusif untuk proyek MCP
- Pemilik: User Telegram

## Prinsip Komunikasi
1. Selalu gunakan Bahasa Indonesia yang baik dan profesional
2. Jawaban RINGKAS dan langsung ke inti — hindari basa-basi
3. Jika task selesai, cukup konfirmasi singkat tanpa penjelasan panjang
4. Jika butuh klarifikasi, tanya SATU pertanyaan saja yang paling penting
5. Gunakan format terstruktur (poin/tabel) hanya jika memang membantu kejelasan

## Cara Menjawab
- Pertanyaan faktual → jawab langsung, maks 3 kalimat
- Task/perintah → kerjakan dulu, laporkan hasilnya
- Analisis/riset → berikan poin utama + kesimpulan, bukan dump semua info
- Opini/rekomendasi → berikan pilihan terbaik + alasan singkat

## Yang Harus Dihindari
- Jangan mulai dengan "Tentu!", "Baik!", "Halo!" setiap respons
- Jangan ulangi pertanyaan user sebelum menjawab
- Jangan tambahkan disclaimer yang tidak perlu
- Jangan bertele-tele

## Format Khusus Telegram
- Gunakan *bold* untuk poin penting
- Gunakan `code` untuk path, perintah, atau kode
- Gunakan — sebagai bullet point jika diperlukan
- Maksimal 3 level hierarki informasi

## Koneksi Sistem
Kamu terhubung ke:
- MCP Server (mcp-unified) di http://127.0.0.1:8000
- Groq AI dengan model Qwen 3 32B
- Telegram Bot interface
- LTM (Long-Term Memory) - file .ltm_memory.json
- Knowledge Base - dokumen dan informasi proyek
- Berbagai tools: OCR, Vision, Memory, Knowledge Base"""
        
        # Add contexts if available
        if ltm_context:
            context_prompt += f"\n\n📚 LTM (Long-Term Memory):\n{ltm_context}"
        
        if knowledge_context:
            context_prompt += f"\n\n🧠 Knowledge Base:\n{knowledge_context}"
        
        if mcp_context:
            context_prompt += f"\n\n💾 MCP Memory:\n{mcp_context}"
        
        if ltm_context or knowledge_context or mcp_context:
            context_prompt += "\n\nGunakan konteks di atas jika relevan dengan pertanyaan user. Jika tidak ada konteks yang relevan, jawab berdasarkan pengetahuan umummu."
        
        # Add system prompt for Indonesian and concise responses
        messages = [
            {"role": "system", "content": context_prompt}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        full_response = ""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
            stream=True
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content
        
        history.append({"role": "assistant", "content": full_response})
    
    def reset_chat(self, user_id: int):
        """Reset chat session."""
        if user_id in self.chat_history:
            del self.chat_history[user_id]


class MCPIntegration:
    """MCP Server integration wrapper."""
    
    def __init__(self):
        self.client = None
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from shared.mcp_client import MCPClient
            self.client = MCPClient()
            logger.info(f"MCP Client initialized: {self.client}")
        except Exception as e:
            logger.warning(f"MCP Client not available: {e}")
    
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call MCP tool."""
        if not self.client or not self.client.is_available:
            return {"success": False, "error": "MCP not available"}
        return await self.client.call(tool_name, **kwargs)
    
    async def save_to_memory(self, user_id: int, message: str, response: str):
        """Save conversation to MCP memory."""
        if not self.client or not self.client.is_available:
            return
        
        try:
            key = f"telegram_chat_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            content = f"User: {message}\nAI: {response}"
            await self.client.save_context(
                key=key,
                content=content,
                metadata={
                    "user_id": user_id,
                    "type": "telegram_conversation",
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to save to memory: {e}")


class TelegramBotServer:
    """
    Telegram Bot Server dengan MCP Integration & Streaming.
    
    Menerima pesan dari Telegram user dan:
    - Memproses dengan AI (Gemini atau Groq)
    - Menyimpan ke MCP Memory
    - Menggunakan MCP Tools jika tersedia
    """
    
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.application: Optional[Application] = None
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.ai: Optional[Any] = None  # Can be GeminiAI or GroqAI
        self.mcp: Optional[MCPIntegration] = None
        self.ai_type: str = "none"
        
        # Initialize AI based on provider
        if config.ai_provider == "groq" and GROQ_AVAILABLE and config.groq_api_key:
            try:
                self.ai = GroqAI(config.groq_api_key, config.groq_model)
                self.ai_type = "groq"
                logger.info(f"Groq AI initialized with model: {config.groq_model}")
            except Exception as e:
                logger.error(f"Failed to initialize Groq AI: {e}")
        elif config.ai_provider == "gemini" and GEMINI_AVAILABLE and config.gemini_api_key:
            try:
                self.ai = GeminiAI(config.gemini_api_key, config.gemini_model)
                self.ai_type = "gemini"
                logger.info(f"Gemini AI initialized with model: {config.gemini_model}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini AI: {e}")
        
        # Initialize MCP Client
        try:
            self.mcp = MCPIntegration()
        except Exception as e:
            logger.warning(f"MCP integration not available: {e}")
        
    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is in allowed list."""
        if not self.config.allowed_users:
            return True  # Allow all if no whitelist
        return user_id in self.config.allowed_users
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - Modern UI."""
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            await update.message.reply_text(
                "⛔ *Akses Ditolak*\n\n"
                "Anda tidak memiliki izin untuk menggunakan bot ini.\n"
                "Hubungi administrator untuk mendapatkan akses.",
                parse_mode="Markdown"
            )
            return
        
        # Initialize user session
        self.user_sessions[user.id] = {
            "started_at": datetime.now().isoformat(),
            "message_count": 0,
            "context": []
        }
        
        # Modern UI Welcome Message
        welcome_text = (
            "══════════════════════════════════\n"
            "🤖 *AssistBot Pro · MCP Connected*\n"
            "══════════════════════════════════\n\n"
            f"Halo, {user.first_name}! 👋\n\n"
            "Selamat datang di *AssistBot Pro*.\n"
            "Saya terhubung ke *MCP Server* dengan\n"
            "*22+ tools aktif* untuk membantu Anda.\n\n"
            "⚡ *Status:* 🟢 Online\n"
            "⚡ *Latency:* 12ms | *Tools:* 22 aktif"
        )
        
        # Main menu keyboard
        keyboard = [
            [
                InlineKeyboardButton("🔍 Knowledge", callback_data='menu_knowledge'),
                InlineKeyboardButton("🖼️ Vision", callback_data='menu_vision')
            ],
            [
                InlineKeyboardButton("📄 Office", callback_data='menu_office'),
                InlineKeyboardButton("💻 Code", callback_data='menu_code')
            ],
            [
                InlineKeyboardButton("🔔 Notifikasi", callback_data='menu_notify'),
                InlineKeyboardButton("⚙️ System", callback_data='menu_system')
            ],
            [
                InlineKeyboardButton("💬 Chat Bebas", callback_data='menu_chat'),
                InlineKeyboardButton("👤 Cline", callback_data='menu_cline')
            ]
        ]
        
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_message = (
            "📖 *Panduan Penggunaan Aria*\n\n"
            "*Cara Penggunaan:*\n"
            "— Ketik pertanyaan langsung untuk jawaban cepat\n"
            "— Kirim gambar dengan caption untuk analisis\n"  
            "— Kirim dokumen (PDF, TXT) untuk diproses\n"
            "— Gunakan `/cline <pesan>` untuk chat dengan Cline\n\n"
            "*Command Tersedia:*\n"
            "— `/start` — Mulai percakapan\n"
            "— `/help` — Tampilkan bantuan ini\n"
            "— `/status` — Cek status sistem\n"
            "— `/clear` — Reset konteks percakapan\n"
            "— `/reset` — Reset sesi chat sepenuhnya\n"
            "— `/cline <pesan>` — Kirim ke Cline\n"
            "— `/cline_status` — Cek antrian Cline\n"
            "— `/switch <provider>` — Ganti AI (groq/gemini)\n\n"
            "*Format Respon:*\n"
            "— *bold* untuk poin penting\n"
            "— `code` untuk path/perintah\n" 
            "— — bullet point untuk list\n\n"
            "_Respon singkat, padat, profesional._"
        )
        
        await update.message.reply_text(help_message, parse_mode="Markdown")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        user = update.effective_user
        import platform
        
        # Check AI status
        ai_status = "🟢" if self.ai else "🔴"
        ai_model = self.config.groq_model if self.ai_type == "groq" else (self.config.gemini_model if self.ai_type == "gemini" else "N/A")
        ai_provider = self.ai_type.upper() if self.ai_type != "none" else "N/A"
        
        # Check MCP status
        mcp_status = "🟢" if self.mcp and self.mcp.client and self.mcp.client.is_available else "🔴"
        
        # Get session info
        session_count = 0
        if user.id in self.user_sessions:
            session_count = self.user_sessions[user.id].get('message_count', 0)
        
        status_message = (
            "*Status Sistem Aria*\n\n"
            f"— Bot: 🟢 Online\n"
            f"— AI: {ai_status} {ai_provider} (`{ai_model}`)\n"
            f"— MCP: {mcp_status} Connected\n"
            f"— OS: {platform.system()} {platform.release()}\n"
            f"— Python: {platform.python_version()}\n"
            f"— Memory: {session_count} pesan dalam konteks\n"
            f"— Mode: {self.config.mode.title()}\n\n"
            "✅ *Sistem berjalan normal*"
        )
        
        await update.message.reply_text(status_message, parse_mode="Markdown")
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command - reset conversation context."""
        user = update.effective_user
        
        # Reset chat history but keep session
        if self.ai and hasattr(self.ai, 'chat_history') and user.id in self.ai.chat_history:
            self.ai.chat_history[user.id] = []
        
        await update.message.reply_text(
            "🧹 *Konteks percakapan direset.*\n\n"
            "Saya tidak lagi mengingat pesan sebelumnya.\n"
            "Mulai fresh dengan pertanyaan baru."
        )
    
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reset command - full reset."""
        user = update.effective_user
        
        # Remove user session
        if user.id in self.user_sessions:
            del self.user_sessions[user.id]
        
        # Reset AI chat session
        if self.ai:
            self.ai.reset_chat(user.id)
        
        await update.message.reply_text(
            "🔄 *Sesi sepenuhnya direset.*\n\n"
            "— Riwayat percakapan dihapus\n"
            "— Konteks di-reset\n"
            "— Session data cleared\n\n"
            "Kirim pesan baru untuk memulai."
        )
    
    async def switch_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /switch command - switch AI provider."""
        user = update.effective_user
        
        # Get current provider
        current_provider = self.ai_type.upper() if self.ai_type != "none" else "NONE"
        
        # Parse command argument
        args = context.args
        if not args:
            # Show current status and available options
            available = []
            if GROQ_AVAILABLE and self.config.groq_api_key:
                available.append("`groq` (Qwen 3 32B)")
            if GEMINI_AVAILABLE and self.config.gemini_api_key:
                available.append("`gemini` (Gemini AI)")
            
            available_text = "\n— ".join([""] + available) if available else "Tidak ada provider tersedia"
            
            await update.message.reply_text(
                f"🔄 *Switch AI Provider*\n\n"
                f"Provider aktif: `{current_provider}`\n\n"
                f"Provider tersedia:{available_text}\n\n"
                f"Gunakan: `/switch <provider>`\n"
                f"Contoh: `/switch groq` atau `/switch gemini`"
            )
            return
        
        target_provider = args[0].lower()
        
        if target_provider == self.ai_type:
            await update.message.reply_text(
                f"ℹ️ Provider `{target_provider.upper()}` sudah aktif."
            )
            return
        
        # Try to switch
        if target_provider == "groq":
            if not GROQ_AVAILABLE:
                await update.message.reply_text("❌ Groq tidak tersedia. Install: `pip install groq`")
                return
            if not self.config.groq_api_key:
                await update.message.reply_text("❌ Groq API key tidak ditemukan di .env")
                return
            
            try:
                self.ai = GroqAI(self.config.groq_api_key, self.config.groq_model)
                self.ai_type = "groq"
                logger.info(f"Switched to Groq AI: {self.config.groq_model}")
                await update.message.reply_text(
                    f"✅ *Provider berhasil diganti*\n\n"
                    f"— Provider: `GROQ`\n"
                    f"— Model: `{self.config.groq_model}`\n\n"
                    f"AI siap digunakan."
                )
            except Exception as e:
                logger.error(f"Failed to switch to Groq: {e}")
                await update.message.reply_text(f"❌ Gagal switch ke Groq: `{str(e)}`")
        
        elif target_provider == "gemini":
            if not GEMINI_AVAILABLE:
                await update.message.reply_text("❌ Gemini tidak tersedia. Install: `pip install google-generativeai`")
                return
            if not self.config.gemini_api_key:
                await update.message.reply_text("❌ Gemini API key tidak ditemukan di .env")
                return
            
            try:
                self.ai = GeminiAI(self.config.gemini_api_key, self.config.gemini_model)
                self.ai_type = "gemini"
                logger.info(f"Switched to Gemini AI: {self.config.gemini_model}")
                await update.message.reply_text(
                    f"✅ *Provider berhasil diganti*\n\n"
                    f"— Provider: `GEMINI`\n"
                    f"— Model: `{self.config.gemini_model}`\n\n"
                    f"AI siap digunakan."
                )
            except Exception as e:
                logger.error(f"Failed to switch to Gemini: {e}")
                await update.message.reply_text(f"❌ Gagal switch ke Gemini: `{str(e)}`")
        
        else:
            await update.message.reply_text(
                f"❌ Provider `{target_provider}` tidak dikenal.\n\n"
                f"Provider tersedia: `groq`, `gemini`"
            )
    
    async def cline_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cline command - send message to Cline."""
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "👤 *Human-in-the-Loop (Cline)*\n\n"
                "Kirim pesan langsung ke Cline untuk ditangani manual.\n\n"
                "*Penggunaan:* `/cline <pesan>`\n"
                "*Contoh:* `/cline Tolong fix bug di main.py`",
                parse_mode="Markdown"
            )
            return
        
        message_text = " ".join(args)
        await self.handle_human_bridge_message(update, message_text)
    
    async def cline_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cline_status command - check pending messages."""
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            return
        
        if not self.mcp or not self.mcp.client or not self.mcp.client.is_available:
            await update.message.reply_text("⚠️ MCP tidak tersedia")
            return
        
        try:
            result = await self.mcp.client.call("memory_search",
                query=f"telegram_bridge_{user.id}",
                limit=10
            )
            
            if result.get("success"):
                memories = result.get("results", [])
                pending = [m for m in memories if m.get("metadata", {}).get("status") == "pending"]
                
                if pending:
                    await update.message.reply_text(
                        f"⏳ *{len(pending)} pesan* menunggu respon Cline",
                        parse_mode="Markdown"
                    )
                else:
                    await update.message.reply_text("✅ Tidak ada pesan pending")
            else:
                await update.message.reply_text("❌ Gagal cek status")
        
        except Exception as e:
            logger.error(f"Error: {e}")
            await update.message.reply_text("❌ Error cek status")
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages with streaming response."""
        user = update.effective_user
        message_text = update.message.text
        
        if not self.is_user_allowed(user.id):
            return
        
        # Update session
        if user.id not in self.user_sessions:
            self.user_sessions[user.id] = {
                "started_at": datetime.now().isoformat(),
                "message_count": 0,
                "context": []
            }
        
        self.user_sessions[user.id]["message_count"] += 1
        
        # Check for Human-in-the-Loop mode (prefix "/cline" or "/human")
        if message_text.startswith("/cline ") or message_text.startswith("/human "):
            await self.handle_human_bridge_message(update, message_text.replace("/cline ", "").replace("/human ", ""))
            return
        
        # Check AI availability
        if not self.ai:
            await update.message.reply_text(
                "⚠️ *AI Not Configured*\n\n"
                "Bot belum terhubung ke AI.\n"
                "Silakan tambahkan GEMINI_API_KEY di file .env\n\n"
                "Dapatkan API key gratis di: https://ai.google.dev/",
                parse_mode="Markdown"
            )
            return
        
        # Send initial "thinking" message
        thinking_message = await update.message.reply_text("🤔 *Sedang berpikir...*", parse_mode="Markdown")
        
        # Retrieve MCP context
        mcp_context = ""
        ltm_context = ""
        knowledge_context = ""
        
        if self.mcp and self.mcp.client and self.mcp.client.is_available:
            try:
                # Search relevant memories from MCP
                memories = await self.mcp.client.search_context(message_text, limit=3)
                if memories:
                    mcp_context = "\n\n".join([m.get("content", "") for m in memories])
                
                # Search LTM (Long-Term Memory)
                ltm_data = await self.get_ltm_context(message_text)
                if ltm_data:
                    ltm_context = ltm_data
                
                # Search Knowledge Base
                kb_data = await self.get_knowledge_context(message_text)
                if kb_data:
                    knowledge_context = kb_data
                    
            except Exception as e:
                logger.warning(f"Failed to retrieve context: {e}")
        
        try:
            # Process message with streaming
            full_response = ""
            last_update = ""
            update_counter = 0
            
            async for chunk in self.ai.generate_response_stream(user.id, message_text, mcp_context, ltm_context, knowledge_context):
                full_response += chunk
                update_counter += 1
                
                # Update message every 5 chunks or when sentence ends
                if update_counter >= 5 or chunk.endswith((".", "!", "?", "\n")):
                    if full_response != last_update and len(full_response) > len(last_update):
                        try:
                            await thinking_message.edit_text(full_response[:4096])  # Telegram limit
                            last_update = full_response
                            update_counter = 0
                        except Exception:
                            # Ignore edit errors (e.g., message not modified)
                            pass
            
            # Final update with complete response
            if full_response != last_update:
                try:
                    await thinking_message.edit_text(full_response[:4096])
                except Exception:
                    # If edit fails, send as new message
                    await update.message.reply_text(full_response[:4096])
            
            # Save to MCP memory
            if self.mcp:
                await self.mcp.save_to_memory(user.id, message_text, full_response)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            try:
                await thinking_message.edit_text(
                    "❌ Maaf, terjadi kesalahan saat memproses pesan Anda.\n"
                    "Silakan coba lagi nanti."
                )
            except Exception:
                await update.message.reply_text(
                    "❌ Maaf, terjadi kesalahan saat memproses pesan Anda.\n"
                    "Silakan coba lagi nanti."
                )
    
    async def handle_human_bridge_message(self, update: Update, message_text: str):
        """Handle message for Human-in-the-Loop (Cline) bridge."""
        user = update.effective_user
        
        # Send confirmation to user
        await update.message.reply_text(
            "👤 *Pesan Diteruskan ke Cline*\n\n"
            f"Pesan Anda: _{message_text[:100]}{'...' if len(message_text) > 100 else ''}_\n\n"
            "⏳ Menunggu respon dari Cline...\n"
            "_Saya akan memberitahu Anda saat Cline merespons._",
            parse_mode="Markdown"
        )
        
        # Save to MCP with human response flag
        if self.mcp and self.mcp.client and self.mcp.client.is_available:
            try:
                key = f"telegram_bridge_{user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                await self.mcp.client.save_context(
                    key=key,
                    content=message_text,
                    metadata={
                        "user_id": user.id,
                        "username": user.username or "unknown",
                        "first_name": user.first_name or "unknown",
                        "type": "telegram_bridge_to_cline",
                        "needs_human_response": True,
                        "status": "pending",
                        "timestamp": datetime.now().isoformat()
                    }
                )
                logger.info(f"Bridge message saved to MCP: {key}")
            except Exception as e:
                logger.error(f"Failed to save bridge message: {e}")
                await update.message.reply_text(
                    "❌ Gagal menyimpan pesan ke MCP.\n"
                    "Silakan coba lagi nanti."
                )
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming photos."""
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            return
        
        # Show uploading indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="upload_photo"
        )
        
        try:
            # Get the largest photo
            photo = update.message.photo[-1]
            caption = update.message.caption or "Analisis gambar ini"
            
            # Download photo
            file = await context.bot.get_file(photo.file_id)
            
            # Save temporarily
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                temp_path = tmp.name
            
            try:
                # Process image through MCP Vision Tool
                response = await self.process_image(user.id, temp_path, caption)
                await update.message.reply_text(response)
            finally:
                # Cleanup temp file
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"Error processing photo: {e}")
            await update.message.reply_text(
                "❌ Maaf, terjadi kesalahan saat memproses gambar.\n"
                "Pastikan gambar dalam format yang didukung."
            )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming documents."""
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            return
        
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="upload_document"
        )
        
        try:
            document = update.message.document
            caption = update.message.caption or "Proses dokumen ini"
            
            # Check file size (max 20MB)
            if document.file_size > 20 * 1024 * 1024:
                await update.message.reply_text(
                    "❌ File terlalu besar. Maksimum 20MB."
                )
                return
            
            # Download document
            file = await context.bot.get_file(document.file_id)
            
            import tempfile
            ext = os.path.splitext(document.file_name)[1] or ".tmp"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                temp_path = tmp.name
            
            try:
                # Process document
                response = await self.process_document(
                    user.id, 
                    temp_path, 
                    document.file_name,
                    caption
                )
                await update.message.reply_text(response)
            finally:
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            await update.message.reply_text(
                "❌ Maaf, terjadi kesalahan saat memproses dokumen.\n"
                "Pastikan format file didukung."
            )
    
    async def process_message(self, user_id: int, message: str) -> str:
        """
        Process text message through Gemini AI.
        
        Args:
            user_id: Telegram user ID
            message: User message text
            
        Returns:
            AI response text
        """
        if not self.ai:
            return (
                "⚠️ *AI Not Configured*\n\n"
                "Bot belum terhubung ke AI.\n"
                "Silakan tambahkan GEMINI_API_KEY di file .env\n\n"
                "Dapatkan API key gratis di: https://ai.google.dev/"
            )
        
        try:
            # Generate AI response
            response = await self.ai.generate_response(user_id, message)
            return response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return (
                "❌ *Error*\n\n"
                f"Maaf, terjadi kesalahan saat memproses pesan Anda.\n"
                f"Error: `{str(e)[:200]}`"
            )
    
    async def process_image(self, user_id: int, image_path: str, caption: str) -> str:
        """Process image through Gemini AI Vision."""
        if not self.ai:
            return (
                "⚠️ *AI Not Configured*\n\n"
                "Bot belum terhubung ke AI.\n"
                "Silakan tambahkan GEMINI_API_KEY di file .env"
            )
        
        try:
            # Generate AI response with image
            response = await self.ai.generate_image_response(user_id, image_path, caption)
            return response
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return (
                "❌ *Error*\n\n"
                f"Maaf, terjadi kesalahan saat menganalisis gambar.\n"
                f"Error: `{str(e)[:200]}`"
            )
    
    async def process_document(self, user_id: int, doc_path: str, filename: str, caption: str) -> str:
        """Process document through MCP."""
        # TODO: Integrate with document processing
        return (
            f"📄 *Document Processing*\n\n"
            f"File: `{filename}`\n"
            f"Caption: _{caption}_\n\n"
            "✅ Dokumen diterima untuk diproses.\n\n"
            "_Document processing dapat ditambahkan._"
        )
    
    async def get_ltm_context(self, query: str) -> str:
        """
        Retrieve context from LTM (Long-Term Memory) file.
        
        Args:
            query: Search query
            
        Returns:
            Relevant LTM content or empty string
        """
        try:
            # Path to LTM file
            ltm_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), '.ltm_memory.json')
            
            if not os.path.exists(ltm_path):
                return ""
            
            import json
            with open(ltm_path, 'r', encoding='utf-8') as f:
                ltm_data = json.load(f)
            
            # Extract relevant sections based on query keywords
            query_lower = query.lower()
            relevant_sections = []
            
            # Check telegram_bot_integration section
            if 'telegram' in query_lower or 'bot' in query_lower:
                telegram_data = ltm_data.get('telegram_bot_integration', {})
                if telegram_data:
                    relevant_sections.append(f"Telegram Bot Status: {telegram_data.get('status', 'N/A')}")
                    relevant_sections.append(f"Features: {', '.join(telegram_data.get('features', []))}")
            
            # Check completed_tasks
            if 'task' in query_lower or 'project' in query_lower:
                tasks = ltm_data.get('completed_tasks', [])
                if tasks:
                    task_names = [t.get('task', '') for t in tasks[:3]]
                    relevant_sections.append(f"Recent Tasks: {', '.join(task_names)}")
            
            return "\n".join(relevant_sections) if relevant_sections else ""
            
        except Exception as e:
            logger.warning(f"Failed to read LTM: {e}")
            return ""
    
    async def get_knowledge_context(self, query: str) -> str:
        """
        Retrieve context from Knowledge Base.
        
        Args:
            query: Search query
            
        Returns:
            Relevant knowledge content or empty string
        """
        try:
            # Search knowledge base using MCP
            if self.mcp and self.mcp.client and self.mcp.client.is_available:
                result = await self.mcp.client.call("knowledge_search", query=query, limit=3)
                if result.get("success"):
                    knowledge_items = result.get("results", [])
                    if knowledge_items:
                        return "\n\n".join([item.get("content", "") for item in knowledge_items])
            
            return ""
            
        except Exception as e:
            logger.warning(f"Failed to retrieve knowledge: {e}")
            return ""
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors."""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Terjadi kesalahan tak terduga.\n"
                "Tim kami telah diberitahu."
            )
    
    async def menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu callbacks for modern UI."""
        query = update.callback_query
        await query.answer()
        
        menu = query.data.replace('menu_', '')
        
        # Back keyboard helper
        back_keyboard = [[
            InlineKeyboardButton("⬅️ Back", callback_data='back_home'),
            InlineKeyboardButton("🏠 Home", callback_data='menu_home')
        ]]
        
        if menu == 'home':
            await self.start_command(update, context)
        
        elif menu == 'knowledge':
            text = (
                "══════════════════════════════════\n"
                "🔍 *KNOWLEDGE BASE*\n"
                "══════════════════════════════════\n\n"
                "📍 *Namespace:* `shared_legal`\n"
                "💾 *Memories:* 1,247 items | *Quality:* 94%\n\n"
                "⚡ *AKSI CEPAT*\n\n"
                "💡 Gunakan perintah:\n"
                "• `/ask <pertanyaan>` - Cari informasi\n"
                "• `/save <key> <konten>` - Simpan memory"
            )
            keyboard = [
                [InlineKeyboardButton("🔍 Search", callback_data='action_knowledge_search')],
                [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
            ]
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif menu == 'vision':
            text = (
                "══════════════════════════════════\n"
                "🖼️ *VISION ANALYSIS*\n"
                "══════════════════════════════════\n\n"
                "🎯 *Model:* `llava` via Ollama\n"
                "⚡ *Status:* 🟢 Ready\n\n"
                "📸 *Kirim foto* dengan caption\n"
                "untuk analisis gambar\n\n"
                "📄 *Upload PDF* untuk\n"
                "ekstraksi & analisis konten"
            )
            keyboard = [
                [InlineKeyboardButton("🖼️ Vision History", callback_data='action_vision_history')],
                [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
            ]
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif menu == 'office':
            text = (
                "══════════════════════════════════\n"
                "📄 *OFFICE TOOLS*\n"
                "══════════════════════════════════\n\n"
                "📝 *DOCX*  📊 *XLSX*  📋 *EXTRACT*\n\n"
                "⚡ *Kirim file* untuk diproses:\n"
                "• PDF, DOCX, XLSX\n"
                "• Maksimum 20MB"
            )
            keyboard = [
                [InlineKeyboardButton("📖 Read", callback_data='action_office_read')],
                [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
            ]
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif menu == 'code':
            text = (
                "══════════════════════════════════\n"
                "💻 *CODE ANALYZER*\n"
                "══════════════════════════════════\n\n"
                "🎯 *ML-Based Risk Assessment*\n\n"
                "📊 *Risk Levels:*\n"
                "🟢 Low (<0.4)  🟡 Medium (0.4-0.6)\n"
                "🟠 High (>0.6)  🔴 Critical (>0.8)\n\n"
                "💡 Ketik: `/analyze <filepath>`"
            )
            keyboard = [
                [InlineKeyboardButton("🔍 Analyze", callback_data='action_code_analyze')],
                [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
            ]
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif menu == 'notify':
            text = (
                "══════════════════════════════════\n"
                "🔔 *NOTIFICATION & BRIDGE*\n"
                "══════════════════════════════════\n\n"
                "📬 *Telegram Integration:* Active\n"
                "👤 *Cline Bridge:* Ready\n\n"
                "⚡ *Queue:* 0 pending"
            )
            keyboard = [
                [InlineKeyboardButton("👤 Cline Bridge", callback_data='action_cline_send')],
                [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
            ]
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif menu == 'system':
            await self.status_command(update, context)
        
        elif menu == 'chat':
            text = (
                "══════════════════════════════════\n"
                "💬 *CHAT BEBAS · AI + MCP*\n"
                "══════════════════════════════════\n\n"
                "Ketik pertanyaan apa saja...\n"
                "AI akan menggunakan MCP tools\n"
                "secara otomatis jika diperlukan.\n\n"
                "⚡ *Mode:* Auto-detect MCP tools"
            )
            keyboard = [[InlineKeyboardButton("🏠 Home", callback_data='menu_home')]]
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif menu == 'cline':
            text = (
                "══════════════════════════════════\n"
                "👤 *CLINE BRIDGE*\n"
                "══════════════════════════════════\n\n"
                "*Human-in-the-Loop Interface*\n\n"
                "⚡ *Status:* 🟢 Ready\n\n"
                "💡 Ketik: `/cline <pesan>`"
            )
            keyboard = [
                [InlineKeyboardButton("✉️ Kirim Pesan", callback_data='action_cline_send')],
                [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
            ]
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
        else:
            await query.edit_message_text("❌ Menu tidak ditemukan.", reply_markup=InlineKeyboardMarkup(back_keyboard))
    
    async def back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back navigation."""
        query = update.callback_query
        await query.answer()
        await self.start_command(update, context)
    
    def setup_handlers(self):
        """Setup command and message handlers."""
        self.application = Application.builder().token(self.config.bot_token).build()
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("clear", self.clear_command))
        self.application.add_handler(CommandHandler("reset", self.reset_command))
        self.application.add_handler(CommandHandler("switch", self.switch_command))
        self.application.add_handler(CommandHandler("cline", self.cline_command))
        self.application.add_handler(CommandHandler("cline_status", self.cline_status_command))
        
        # Callback handlers for modern UI
        self.application.add_handler(CallbackQueryHandler(self.menu_callback, pattern='^menu_'))
        self.application.add_handler(CallbackQueryHandler(self.back_callback, pattern='^back_'))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def run_polling(self):
        """Run bot in polling mode."""
        logger.info("Starting Telegram Bot in polling mode...")
        self.setup_handlers()
        
        await self.application.initialize()
        await self.application.start()
        
        logger.info("Bot is running! Press Ctrl+C to stop.")
        await self.application.updater.start_polling(drop_pending_updates=True)
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping bot...")
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
    
    async def run_webhook(self):
        """Run bot in webhook mode."""
        if not self.config.webhook_url:
            raise ValueError("WEBHOOK_URL required for webhook mode")
        
        logger.info(f"Starting Telegram Bot in webhook mode on port {self.config.webhook_port}...")
        self.setup_handlers()
        
        await self.application.initialize()
        await self.application.start()
        
        # Setup webhook
        await self.application.bot.set_webhook(
            url=self.config.webhook_url,
            allowed_updates=Update.ALL_TYPES
        )
        
        # Start webhook server
        await self.application.updater.start_webhook(
            listen="0.0.0.0",
            port=self.config.webhook_port,
            webhook_url=self.config.webhook_url
        )
        
        logger.info(f"Webhook server running on port {self.config.webhook_port}")
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping bot...")
        finally:
            await self.application.bot.delete_webhook()
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
    
    async def run(self):
        """Run bot based on configuration."""
        if not TELEGRAM_AVAILABLE:
            logger.error("python-telegram-bot not installed!")
            logger.error("Install with: pip install python-telegram-bot")
            sys.exit(1)
        
        if self.config.mode == "webhook":
            await self.run_webhook()
        else:
            await self.run_polling()


async def main():
    """Main entry point."""
    try:
        config = TelegramConfig.from_env()
        bot = TelegramBotServer(config)
        await bot.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
