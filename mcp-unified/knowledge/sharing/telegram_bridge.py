"""
Telegram Knowledge Bridge

Integrasi antara Telegram Bot dengan Knowledge Sharing System.
Memungkinkan user upload dokumen via Telegram dan query shared knowledge.
"""

import os
from pathlib import Path
from typing import Optional, Callable


class TelegramKnowledgeBridge:
    """
    Bridge antara Telegram Bot dan Knowledge Sharing.
    
    Features:
        - Handle document uploads dari Telegram
        - Process files dengan DocumentProcessor
        - Query knowledge dengan /ask command
        - Review queue notifications
    """
    
    def __init__(
        self,
        bot,
        document_processor,
        namespace_manager,
        download_path: str = "./downloads/telegram"
    ):
        """
        Initialize Telegram bridge.
        
        Args:
            bot: Telegram bot instance
            document_processor: DocumentProcessor instance
            namespace_manager: NamespaceManager instance
            download_path: Path untuk download files
        """
        self.bot = bot
        self.processor = document_processor
        self.namespaces = namespace_manager
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
    
    async def handle_document(self, message):
        """
        Handle document upload dari Telegram.
        
        Args:
            message: Telegram message object dengan document
        """
        try:
            # Get document info
            document = message.document
            file_name = document.file_name
            file_size = document.file_size
            
            # Check file size (max 20MB)
            if file_size > 20 * 1024 * 1024:
                await message.reply(
                    "❌ File terlalu besar!\n"
                    "Maksimum ukuran file: 20MB"
                )
                return
            
            # Check file extension
            ext = Path(file_name).suffix.lower()
            supported = ['.pdf', '.docx', '.xlsx', '.doc', '.xls']
            if ext not in supported:
                await message.reply(
                    f"❌ Format file tidak didukung: {ext}\n"
                    f"Format yang didukung: {', '.join(supported)}"
                )
                return
            
            # Download file
            await message.reply(f"📥 Mendownload {file_name}...")
            
            file_path = await self._download_file(document, file_name)
            
            # Suggest namespace
            suggested_ns = self.namespaces.suggest_namespace(file_name)
            
            await message.reply(
                f"📄 File diterima: {file_name}\n"
                f"🗂️ Namespace yang disarankan: {suggested_ns}\n"
                f"⏳ Memproses..."
            )
            
            # Process file
            result = await self.processor.process_file(
                file_path=str(file_path),
                suggested_namespace=suggested_ns,
                tags=["telegram_upload"],
                uploaded_by=f"telegram_user_{message.from_user.id}"
            )
            
            # Send result
            if result.status == "approved":
                await message.reply(
                    f"✅ *Berhasil diproses!*\n\n"
                    f"📊 Quality Score: {result.quality_score:.2f}\n"
                    f"🧩 Chunks: {result.chunks_count}\n"
                    f"📁 Namespace: {result.namespace}\n\n"
                    f"Dokumen sekarang bisa diakses oleh semua agent.",
                    parse_mode="Markdown"
                )
            
            elif result.status == "pending_review":
                await message.reply(
                    f"⏳ *Menunggu Review*\n\n"
                    f"📄 File: {file_name}\n"
                    f"⚠️ Quality Score: {result.quality_score:.2f}\n"
                    f"🆔 Review ID: `{result.review_id}`\n\n"
                    f"Dokumen memerlukan review admin sebelum bisa diakses.",
                    parse_mode="Markdown"
                )
            
            else:  # error
                await message.reply(
                    f"❌ *Error*\n\n"
                    f"{result.message}",
                    parse_mode="Markdown"
                )
            
            # Cleanup downloaded file
            if file_path.exists():
                file_path.unlink()
        
        except Exception as e:
            await message.reply(
                f"❌ *Error saat memproses file*\n\n"
                f"```{str(e)}```",
                parse_mode="Markdown"
            )
    
    async def handle_ask_command(self, message):
        """
        Handle /ask command untuk query knowledge.
        
        Args:
            message: Telegram message dengan /ask command
        """
        try:
            # Extract query
            query = message.text.replace("/ask", "").replace("@" + self.bot.username, "").strip()
            
            if not query:
                await message.reply(
                    "❓ *Cara Penggunaan*\n\n"
                    "Ketik: `/ask pertanyaan anda`\n\n"
                    "Contoh:\n"
                    "`/ask apa itu RPJPD?`\n"
                    "`/ask prosedur pengadaan barang`",
                    parse_mode="Markdown"
                )
                return
            
            await message.reply(f"🔍 Mencari: *{query}*...", parse_mode="Markdown")
            
            # Search di semua shared namespaces
            results = await self.namespaces.search_across_namespaces(
                query=query,
                top_k=5,
                agent_id=f"telegram_user_{message.from_user.id}"
            )
            
            if not results:
                await message.reply(
                    "❌ *Tidak menemukan informasi yang relevan.*\n\n"
                    "Coba gunakan kata kunci yang berbeda.",
                    parse_mode="Markdown"
                )
                return
            
            # Format response
            response = f"🔍 *Hasil untuk:* _{query}_\n\n"
            
            for i, r in enumerate(results[:5], 1):
                source_file = r.get("metadata", {}).get("source_file", "Unknown")
                source_name = Path(source_file).name if source_file != "Unknown" else "Unknown"
                score = r.get("score", 0)
                content = r.get("content", "")[:200]
                namespace = r.get("namespace", "unknown")
                
                response += (
                    f"*{i}. {source_name}*\n"
                    f"📁 {namespace} | ⭐ {score:.2f}\n"
                    f"_{content}..._\n\n"
                )
            
            await message.reply(response, parse_mode="Markdown")
        
        except Exception as e:
            await message.reply(
                f"❌ *Error saat mencari*\n\n"
                f"```{str(e)}```",
                parse_mode="Markdown"
            )
    
    async def handle_namespaces_command(self, message):
        """
        Handle /namespaces command untuk list available namespaces.
        """
        try:
            namespaces = await self.namespaces.list_namespaces(
                agent_id=f"telegram_user_{message.from_user.id}"
            )
            
            if not namespaces:
                await message.reply("📂 Tidak ada namespace yang tersedia.")
                return
            
            response = "📚 *Shared Knowledge Namespaces*\n\n"
            
            for ns in namespaces:
                response += (
                    f"*{ns['name']}*\n"
                    f"_{ns['description']}_\n"
                    f"📝 {ns['document_count']} dokumen\n\n"
                )
            
            await message.reply(response, parse_mode="Markdown")
        
        except Exception as e:
            await message.reply(
                f"❌ *Error*\n\n"
                f"```{str(e)}```",
                parse_mode="Markdown"
            )
    
    async def _download_file(self, document, file_name: str) -> Path:
        """
        Download file dari Telegram.
        
        Args:
            document: Telegram document object
            file_name: Nama file untuk disimpan
            
        Returns:
            Path ke downloaded file
        """
        file = await document.get_file()
        file_path = self.download_path / file_name
        await file.download_to_drive(str(file_path))
        return file_path
    
    def register_handlers(self, dispatcher):
        """
        Register handlers ke Telegram dispatcher.
        
        Args:
            dispatcher: Aiogram dispatcher
        """
        from aiogram import types
        
        # Document handler
        @dispatcher.message_handler(content_types=types.ContentType.DOCUMENT)
        async def document_handler(message: types.Message):
            await self.handle_document(message)
        
        # /ask command
        @dispatcher.message_handler(commands=['ask'])
        async def ask_handler(message: types.Message):
            await self.handle_ask_command(message)
        
        # /namespaces command
        @dispatcher.message_handler(commands=['namespaces'])
        async def namespaces_handler(message: types.Message):
            await self.handle_namespaces_command(message)
        
        # /help command untuk knowledge
        @dispatcher.message_handler(commands=['knowledge_help'])
        async def help_handler(message: types.Message):
            help_text = (
                "📚 *Knowledge Sharing Commands*\n\n"
                "*Upload Dokumen:*\n"
                "Kirim file PDF, DOCX, atau XLSX\n"
                "Bot akan otomatis memproses dan menambahkan ke knowledge base\n\n"
                "*Commands:*\n"
                "`/ask <pertanyaan>` - Cari informasi di knowledge base\n"
                "`/namespaces` - List semua shared namespaces\n"
                "`/knowledge_help` - Tampilkan bantuan ini\n\n"
                "*Contoh:*\n"
                "`/ask apa itu RPJPD?`\n"
                "`/ask prosedur pengadaan barang`"
            )
            await message.reply(help_text, parse_mode="Markdown")