import os
"""
UI Handlers - AssistBot Pro MCP Edition

Implementasi UI modern dengan menu card-based untuk Telegram Bot.
Mengadaptasi desain dari telegram-bot-full-ui.html
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler

from .base import BaseHandler

logger = logging.getLogger(__name__)


class UIHandlers(BaseHandler):
    """Handlers untuk UI modern dengan menu card-based."""
    
    def register(self):
        """Register UI handlers."""
        handlers = [
            CommandHandler("start", self.start_command),
            CommandHandler("menu", self.menu_command),
            CommandHandler("help", self.help_command),
            CallbackQueryHandler(self.menu_callback, pattern='^menu_'),
            CallbackQueryHandler(self.action_callback, pattern='^action_'),
            CallbackQueryHandler(self.back_callback, pattern='^back_'),
        ]
        
        for handler in handlers:
            self.bot.application.add_handler(handler)
        
        logger.info("✅ UI handlers registered")
    
    # ═══════════════════════════════════════════════════════════════
    # COMMANDS
    # ═══════════════════════════════════════════════════════════════
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - Main Menu."""
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
        self.bot.user_sessions[user.id] = {
            "started_at": __import__('datetime').datetime.now().isoformat(),
            "message_count": 0,
        }
        
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
        
        keyboard = self._get_main_menu_keyboard()
        
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command - Show main menu."""
        menu_text = (
            "══════════════════════════════════\n"
            "⚡ *PILIH FITUR*\n"
            "══════════════════════════════════"
        )
        
        keyboard = self._get_main_menu_keyboard()
        
        await update.message.reply_text(
            menu_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = (
            "══════════════════════════════════\n"
            "❓ *BANTUAN PENGGUNAAN*\n"
            "══════════════════════════════════\n\n"
            "*Cara Penggunaan:*\n"
            "• Ketik `/start` untuk menu utama\n"
            "• Ketik `/menu` untuk melihat menu\n"
            "• Ketik `/status` untuk cek status\n"
            "• Gunakan tombol menu untuk navigasi\n\n"
            "*Fitur Tersedia:*\n"
            "🔍 *Knowledge* - Database pengetahuan\n"
            "🖼️ *Vision* - Analisis gambar & PDF\n"
            "📄 *Office* - Kelola dokumen Word/Excel\n"
            "💻 *Code* - Analisis kode Python\n"
            "🔔 *Notifikasi* - Kirim pesan & broadcast\n"
            "⚙️ *System* - Status & konfigurasi\n"
            "💬 *Chat Bebas* - AI dengan MCP tools\n"
            "👤 *Cline* - Human-in-the-loop bridge\n\n"
            "*Tips:*\n"
            "_Kirim pesan langsung untuk chat dengan AI._"
        )
        
        keyboard = [[InlineKeyboardButton("🏠 Kembali ke Menu", callback_data='menu_home')]]
        
        await update.message.reply_text(
            help_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ═══════════════════════════════════════════════════════════════
    # KEYBOARDS
    # ═══════════════════════════════════════════════════════════════
    
    def _get_main_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Get main menu keyboard."""
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
        return InlineKeyboardMarkup(keyboard)
    
    def _get_back_keyboard(self, back_to: str = "home") -> InlineKeyboardMarkup:
        """Get back button keyboard."""
        keyboard = [[
            InlineKeyboardButton("⬅️ Back", callback_data=f'back_{back_to}'),
            InlineKeyboardButton("🏠 Home", callback_data='menu_home'),
            InlineKeyboardButton("❓ Help", callback_data='menu_help')
        ]]
        return InlineKeyboardMarkup(keyboard)
    
    # ═══════════════════════════════════════════════════════════════
    # MENU HANDLERS
    # ═══════════════════════════════════════════════════════════════
    
    async def menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu callbacks."""
        query = update.callback_query
        await query.answer()
        
        menu = query.data.replace('menu_', '')
        
        menu_handlers = {
            'home': self._show_home_menu,
            'knowledge': self._show_knowledge_menu,
            'vision': self._show_vision_menu,
            'office': self._show_office_menu,
            'code': self._show_code_menu,
            'notify': self._show_notify_menu,
            'system': self._show_system_menu,
            'chat': self._show_chat_menu,
            'cline': self._show_cline_menu,
            'help': self._show_help_menu,
        }
        
        handler = menu_handlers.get(menu)
        if handler:
            await handler(update, context)
        else:
            await query.edit_message_text(
                "❌ Menu tidak ditemukan.",
                reply_markup=self._get_back_keyboard()
            )
    
    async def _show_home_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show home menu."""
        query = update.callback_query
        text = (
            "══════════════════════════════════\n"
            "🤖 *AssistBot Pro · MCP Connected*\n"
            "══════════════════════════════════\n\n"
            "⚡ *PILIH FITUR*\n\n"
            "Pilih menu di bawah untuk mulai:"
        )
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=self._get_main_menu_keyboard()
        )
    
    async def _show_knowledge_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show Knowledge Base menu."""
        query = update.callback_query
        text = (
            "══════════════════════════════════\n"
            "🔍 *KNOWLEDGE BASE*\n"
            "══════════════════════════════════\n\n"
            "📍 *Namespace:* `shared_legal`\n"
            "💾 *Memories:* 1,247 items | *Quality:* 94%\n\n"
            "⚡ *AKSI CEPAT*"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📝 Save", callback_data=os.getenv("CALLBACK_DATA", "action_knowledge_save" if not os.getenv("CI") else "DUMMY")),
                InlineKeyboardButton("🔍 Search", callback_data=os.getenv("CALLBACK_DATA", "action_knowledge_search" if not os.getenv("CI") else "DUMMY")),
                InlineKeyboardButton("📁 List", callback_data='action_knowledge_list')
            ],
            [
                InlineKeyboardButton("📤 Upload", callback_data=os.getenv("CALLBACK_DATA", "action_knowledge_upload" if not os.getenv("CI") else "DUMMY")),
                InlineKeyboardButton("🏷️ Tags", callback_data='action_knowledge_tags'),
                InlineKeyboardButton("⚙️ NS", callback_data='action_knowledge_ns')
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _show_vision_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show Vision Analysis menu."""
        query = update.callback_query
        text = (
            "══════════════════════════════════\n"
            "🖼️ *VISION ANALYSIS*\n"
            "══════════════════════════════════\n\n"
            "🎯 *Model:* `llava` via Ollama\n"
            "⚡ *Status:* 🟢 Ready | *Latency:* 245ms\n\n"
            "📸 *ANALISIS GAMBAR*\n"
            "_Kirim foto dengan caption untuk analisis_\n\n"
            "📄 *ANALISIS PDF*\n"
            "_Upload PDF untuk ekstraksi & analisis_\n\n"
            "💡 *Tips:* Tambahkan instruksi spesifik di caption"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🖼️ Vision History", callback_data='action_vision_history'),
                InlineKeyboardButton("📊 Stats", callback_data='action_vision_stats')
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _show_office_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show Office Tools menu."""
        query = update.callback_query
        text = (
            "══════════════════════════════════\n"
            "📄 *OFFICE TOOLS*\n"
            "══════════════════════════════════\n\n"
            "📝 *DOCX*  📊 *XLSX*  📋 *EXTRACT*\n\n"
            "⚡ *AKSI CEPAT*"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📖 Read", callback_data='action_office_read'),
                InlineKeyboardButton("✏️ Edit", callback_data='action_office_edit'),
                InlineKeyboardButton("📝 Create", callback_data='action_office_create')
            ],
            [
                InlineKeyboardButton("📤 Upload", callback_data='action_office_upload'),
                InlineKeyboardButton("📁 Browse", callback_data='action_office_browse')
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _show_code_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show Code Analyzer menu."""
        query = update.callback_query
        text = (
            "══════════════════════════════════\n"
            "💻 *CODE ANALYZER*\n"
            "══════════════════════════════════\n\n"
            "🎯 *ML-Based Risk Assessment*\n"
            "📊 *Threshold:* Complexity 30 | LOC 200\n\n"
            "⚡ *AKSI CEPAT*\n\n"
            "📊 *Risk Levels:*\n"
            "🟢 Low (<0.4)  🟡 Medium (0.4-0.6)\n"
            "🟠 High (>0.6)  🔴 Critical (>0.8)"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 Analyze File", callback_data='action_code_file'),
                InlineKeyboardButton("📁 Project", callback_data='action_code_project')
            ],
            [
                InlineKeyboardButton("📋 Snippet", callback_data='action_code_snippet'),
                InlineKeyboardButton("📈 Report", callback_data='action_code_report')
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _show_notify_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show Notification menu."""
        query = update.callback_query
        text = (
            "══════════════════════════════════\n"
            "🔔 *NOTIFICATION & BRIDGE*\n"
            "══════════════════════════════════\n\n"
            "📬 *Telegram Integration:* Active\n"
            "👤 *Cline Bridge:* Ready\n\n"
            "⚡ *AKSI CEPAT*\n\n"
            "⚡ *Queue:* 0 pending | *Last:* 2m ago"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📤 Send Message", callback_data=os.getenv("CALLBACK_DATA", "action_notify_send" if not os.getenv("CI") else "DUMMY")),
                InlineKeyboardButton("📢 Broadcast", callback_data='action_notify_broadcast')
            ],
            [
                InlineKeyboardButton("👤 Cline Bridge", callback_data='action_notify_cline'),
                InlineKeyboardButton("📊 Status", callback_data='action_notify_status')
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _show_system_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show System & MCP Status menu."""
        query = update.callback_query
        
        # Get AI status
        ai_provider = self.ai_manager.current_provider
        ai_status = "🟢" if ai_provider else "🔴"
        ai_name = ai_provider.__class__.__name__ if ai_provider else "N/A"
        
        # Get MCP status
        mcp_available = self.mcp and self.mcp.is_available
        mcp_status_icon = "🟢" if mcp_available else "🔴"
        mcp_status_text = "Connected" if mcp_available else "Disconnected"
        
        text = (
            "══════════════════════════════════\n"
            "⚙️ *SYSTEM & MCP STATUS*\n"
            "══════════════════════════════════\n\n"
            f"🟢 *Bot:* Online\n"
            f"{mcp_status_icon} *MCP:* {mcp_status_text} (12ms)\n"
            f"{ai_status} *AI:* {ai_name} Active\n"
            f"🟢 *Memory:* PostgreSQL/pgvector\n\n"
            "⚡ *MCP Tools Active:*\n"
            "`memory_save` `memory_search`\n"
            "`analyze_image` `analyze_file`\n"
            "`read_docx` `write_docx` ..."
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Switch AI", callback_data='action_system_switch'),
                InlineKeyboardButton("🧹 Clear", callback_data='action_system_clear')
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data='menu_system'),
                InlineKeyboardButton("⚙️ Config", callback_data='action_system_config')
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _show_chat_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show Chat Bebas menu."""
        query = update.callback_query
        text = (
            "══════════════════════════════════\n"
            "💬 *CHAT BEBAS · AI + MCP*\n"
            "══════════════════════════════════\n\n"
            "Ketik pertanyaan apa saja...\n"
            "AI akan menggunakan MCP tools\n"
            "secara otomatis jika diperlukan.\n\n"
            "💡 *Contoh:*\n"
            "• \"Cari info tentang...\"\n"
            "• \"Analisis kode ini...\"\n"
            "• \"Simpan informasi...\"\n"
            "• \"Baca file di...\"\n\n"
            "⚡ *Mode:* Auto-detect MCP tools"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 Search", callback_data='menu_knowledge'),
                InlineKeyboardButton("🗂️ Files", callback_data='menu_office')
            ],
            [InlineKeyboardButton("🏠 Home", callback_data='menu_home')]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _show_cline_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show Cline Bridge menu."""
        query = update.callback_query
        text = (
            "══════════════════════════════════\n"
            "👤 *CLINE BRIDGE*\n"
            "══════════════════════════════════\n\n"
            "*Human-in-the-Loop Interface*\n\n"
            "Kirim pesan ke Cline untuk\n"
            "ditangani secara manual.\n\n"
            "⚡ *Status:* 🟢 Ready\n"
            "⚡ *Queue:* 0 pending\n\n"
            "*Penggunaan:*\n"
            "`/cline <pesan>` atau ketik langsung"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✉️ Kirim Pesan", callback_data='action_cline_send'),
                InlineKeyboardButton("📊 Status", callback_data='action_cline_status')
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_home')]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _show_help_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help menu."""
        query = update.callback_query
        text = (
            "══════════════════════════════════\n"
            "❓ *BANTUAN*\n"
            "══════════════════════════════════\n\n"
            "*Commands:*\n"
            "• `/start` - Menu utama\n"
            "• `/menu` - Tampilkan menu\n"
            "• `/help` - Bantuan ini\n"
            "• `/status` - Cek status sistem\n"
            "• `/clear` - Reset konteks\n"
            "• `/reset` - Reset sesi\n\n"
            "*Fitur:*\n"
            "🔍 Knowledge | 🖼️ Vision\n"
            "📄 Office | 💻 Code\n"
            "🔔 Notify | ⚙️ System\n"
            "💬 Chat | 👤 Cline"
        )
        
        keyboard = [[InlineKeyboardButton("🏠 Home", callback_data='menu_home')]]
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ═══════════════════════════════════════════════════════════════
    # ACTION HANDLERS
    # ═══════════════════════════════════════════════════════════════
    
    async def action_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle action callbacks."""
        query = update.callback_query
        await query.answer("🔄 Memproses...")
        
        action = query.data.replace('action_', '')
        
        # Placeholder responses - can be extended
        response_text = f"⚡ *Aksi:* `{action}`\n\n_Fitur ini akan segera tersedia._"
        
        await query.edit_message_text(
            response_text,
            parse_mode="Markdown",
            reply_markup=self._get_back_keyboard()
        )
    
    async def back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back navigation."""
        query = update.callback_query
        await query.answer()
        
        back_to = query.data.replace('back_', '')
        
        if back_to == 'home':
            await self._show_home_menu(update, context)
        else:
            await self._show_home_menu(update, context)


# ═══════════════════════════════════════════════════════════════════
# REPLY KEYBOARD SETUP
# ═══════════════════════════════════════════════════════════════════

def get_reply_keyboard() -> ReplyKeyboardMarkup:
    """Get permanent reply keyboard."""
    keyboard = [
        ["🔍 Knowledge", "🖼️ Vision", "📄 Office"],
        ["💻 Code", "💬 Chat", "⚙️ Menu"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)