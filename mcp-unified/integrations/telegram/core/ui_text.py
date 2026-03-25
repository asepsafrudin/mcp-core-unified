"""UI Text Constants for Telegram Bot."""

# Main Menu
WELCOME_TEXT = """══════════════════════════════════
🤖 *AssistBot Pro · MCP Connected*
══════════════════════════════════

Halo, {name}! 👋

Selamat datang di *AssistBot Pro*.
Saya terhubung ke *MCP Server* dengan
*22+ tools aktif* untuk membantu Anda.

⚡ *Status:* 🟢 Online
⚡ *Latency:* 12ms | *Tools:* 22 aktif"""

# Menu Texts
MENU_KNOWLEDGE = """══════════════════════════════════
🔍 *KNOWLEDGE BASE*
══════════════════════════════════

📍 *Namespace:* `shared_legal`
💾 *Memories:* 1,247 items | *Quality:* 94%

⚡ *AKSI CEPAT*

💡 Gunakan perintah:
• `/ask <pertanyaan>` - Cari informasi
• `/save <key> <konten>` - Simpan memory"""

MENU_VISION = """══════════════════════════════════
🖼️ *VISION ANALYSIS*
══════════════════════════════════

🎯 *Model:* `llava` via Ollama
⚡ *Status:* 🟢 Ready

📸 *Kirim foto* dengan caption
untuk analisis gambar

📄 *Upload PDF* untuk
ekstraksi & analisis konten"""

MENU_OFFICE = """══════════════════════════════════
📄 *OFFICE TOOLS*
══════════════════════════════════

📝 *DOCX*  📊 *XLSX*  📋 *EXTRACT*

⚡ *Kirim file* untuk diproses:
• PDF, DOCX, XLSX
• Maksimum 20MB"""

MENU_CODE = """══════════════════════════════════
💻 *CODE ANALYZER*
══════════════════════════════════

🎯 *ML-Based Risk Assessment*

📊 *Risk Levels:*
🟢 Low (<0.4)  🟡 Medium (0.4-0.6)
🟠 High (>0.6)  🔴 Critical (>0.8)

💡 Ketik: `/analyze <filepath>`"""

MENU_NOTIFY = """══════════════════════════════════
🔔 *NOTIFICATION & BRIDGE*
══════════════════════════════════

📬 *Telegram Integration:* Active
👤 *Cline Bridge:* Ready

⚡ *Queue:* 0 pending"""

MENU_CHAT = """══════════════════════════════════
💬 *CHAT BEBAS · AI + MCP*
══════════════════════════════════

Ketik pertanyaan apa saja...
AI akan menggunakan MCP tools
secara otomatis jika diperlukan.

⚡ *Mode:* Auto-detect MCP tools"""

MENU_CLINE = """══════════════════════════════════
👤 *CLINE BRIDGE*
══════════════════════════════════

*Human-in-the-Loop Interface*

⚡ *Status:* 🟢 Ready

💡 Ketik: `/cline <pesan>`"""

# Keyboard Layouts
MAIN_MENU_KEYBOARD = [
    [("🔍 Knowledge", "menu_knowledge"), ("🖼️ Vision", "menu_vision")],
    [("📄 Office", "menu_office"), ("💻 Code", "menu_code")],
    [("🔔 Notifikasi", "menu_notify"), ("⚙️ System", "menu_system")],
    [("💬 Chat Bebas", "menu_chat"), ("👤 Cline", "menu_cline")],
]

BACK_KEYBOARD = [[("⬅️ Back", "back_home"), ("🏠 Home", "menu_home")]]
