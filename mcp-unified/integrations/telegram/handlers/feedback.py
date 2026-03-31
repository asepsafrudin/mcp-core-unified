"""
Feedback Handler

Handler untuk input feedback disposisi via Telegram.
Format: /feedback <agenda_puu> | <pic_nama> | <tanggal> | <catatan>
"""

import logging
from datetime import datetime, date
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from integrations.telegram.handlers.base import BaseHandler

logger = logging.getLogger(__name__)


class FeedbackHandler(BaseHandler):
    """Handler untuk input feedback disposisi."""
    
    def register(self):
        """Register feedback handler."""
        handlers = [
            CommandHandler("feedback", self.feedback_command),
            CommandHandler("fb", self.feedback_command),  # Alias
        ]
        
        for handler in handlers:
            self.bot.application.add_handler(handler)
        
        logger.info("Registered feedback command handlers")
    
    async def feedback_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /feedback command.
        
        Format: /feedback <agenda_puu> | <pic_nama> | <tanggal> | <catatan>
        Contoh: /feedback 001-I | Ahmad Fauzi | 31/03/2026 | Sudah ditandatangani
        """
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            await update.message.reply_text(
                "⛔ Maaf, Anda tidak memiliki akses ke bot ini."
            )
            return
        
        args = context.args
        
        if not args:
            # Tampilkan bantuan
            help_message = (
                "📝 *Input Feedback Disposisi*\n\n"
                "*Format:*\n"
                "`/feedback <agenda_puu> | <pic_nama> | <tanggal> | <catatan>`\n\n"
                "*Contoh:*\n"
                "`/feedback 001-I | Ahmad Fauzi | 31/03/2026 | Sudah ditandatangani`\n\n"
                "*Field:*\n"
                "— `agenda_puu`: Nomor agenda (001-I s/d 023-I)\n"
                "— `pic_nama`: Nama Person In Charge\n"
                "— `tanggal`: Tanggal autentifikasi (DD/MM/YYYY)\n"
                "— `catatan`: Catatan tambahan (opsional)\n\n"
                "*Alias:* `/fb` bisa digunakan代替 `/feedback`"
            )
            await update.message.reply_text(help_message, parse_mode="Markdown")
            return
        
        # Parse input
        full_text = " ".join(args)
        parts = [p.strip() for p in full_text.split("|")]
        
        if len(parts) < 3:
            await update.message.reply_text(
                "❌ *Format tidak valid*\n\n"
                "Minimal 3 field dipisahkan `|`\n"
                "Contoh: `/feedback 001-I | Ahmad | 31/03/2026 | Catatan`",
                parse_mode="Markdown"
            )
            return
        
        agenda_puu = parts[0]
        pic_nama = parts[1]
        tanggal_str = parts[2]
        catatan = parts[3] if len(parts) > 3 else None
        
        # Validasi tanggal
        try:
            tanggal_autentifikasi = datetime.strptime(tanggal_str, "%d/%m/%Y").date()
        except ValueError:
            await update.message.reply_text(
                f"❌ *Format tanggal salah: `{tanggal_str}`*\n\n"
                "Gunakan format: DD/MM/YYYY\n"
                "Contoh: 31/03/2026",
                parse_mode="Markdown"
            )
            return
        
        # Simpan ke database
        try:
            import psycopg
            import sys
            sys.path.insert(0, '/home/aseps/MCP/mcp-unified')
            from core.config import settings
            from core.secrets import load_runtime_secrets
            load_runtime_secrets()
            
            dsn = f'host={settings.POSTGRES_SERVER} port={settings.POSTGRES_PORT} dbname={settings.POSTGRES_DB} user={settings.POSTGRES_USER} password={settings.POSTGRES_PASSWORD}'
            conn = psycopg.connect(dsn)
            cur = conn.cursor()
            
            # Cari lembar_disposisi_id berdasarkan agenda_puu
            cur.execute(
                "SELECT id FROM lembar_disposisi WHERE agenda_puu = %s",
                (agenda_puu,)
            )
            result = cur.fetchone()
            
            if not result:
                await update.message.reply_text(
                    f"❌ *Agenda `{agenda_puu}` tidak ditemukan*\n\n"
                    "Pastikan nomor agenda benar (001-I s/d 023-I)",
                    parse_mode="Markdown"
                )
                conn.close()
                return
            
            lembar_disposisi_id = result[0]
            
            # Insert feedback
            cur.execute("""
                INSERT INTO disposisi_feedback 
                    (lembar_disposisi_id, agenda_puu, pic_nama, pic_telegram_id,
                     tanggal_autentifikasi, catatan, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, 'telegram')
                ON CONFLICT (lembar_disposisi_id, pic_nama, tanggal_autentifikasi) 
                DO UPDATE SET
                    catatan = EXCLUDED.catatan,
                    updated_at = NOW()
                RETURNING id
            """, (lembar_disposisi_id, agenda_puu, pic_nama, str(user.id),
                  tanggal_autentifikasi, catatan))
            
            feedback_id = cur.fetchone()[0]
            conn.commit()
            conn.close()
            
            # Kirim konfirmasi
            confirm_message = (
                "✅ *Feedback Berhasil Disimpan*\n\n"
                f"📋 *Agenda:* `{agenda_puu}`\n"
                f"👤 *PIC:* {pic_nama}\n"
                f"📅 *Tanggal Autentifikasi:* {tanggal_autentifikasi.strftime('%d %B %Y')}\n"
            )
            if catatan:
                confirm_message += f"📝 *Catatan:* {catatan}\n"
            
            confirm_message += f"\n🆔 *Feedback ID:* {feedback_id}"
            
            await update.message.reply_text(confirm_message, parse_mode="Markdown")
            
            # Kirim notifikasi ke admin
            await self._send_notification(agenda_puu, pic_nama, tanggal_autentifikasi, catatan, user)
            
            logger.info(f"Feedback saved: agenda={agenda_puu}, pic={pic_nama}, user={user.id}")
            
        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            await update.message.reply_text(
                f"❌ *Gagal menyimpan feedback*\n\n"
                f"Error: {str(e)[:100]}",
                parse_mode="Markdown"
            )
    
    async def _send_notification(self, agenda_puu: str, pic_nama: str, 
                                  tanggal_autentifikasi: date, catatan: str, user):
        """Kirim notifikasi ke admin setelah feedback disimpan."""
        try:
            from integrations.korespondensi.utils import send_telegram_notification
            
            notification_text = (
                f"📝 *FEEDBACK BARU*\n\n"
                f"Agenda: {agenda_puu}\n"
                f"PIC: {pic_nama}\n"
                f"Tanggal: {tanggal_autentifikasi.strftime('%d/%m/%Y')}\n"
            )
            if catatan:
                notification_text += f"Catatan: {catatan}\n"
            
            notification_text += f"\nOleh: {user.first_name} (@{user.username or 'N/A'})"
            
            await send_telegram_notification(notification_text)
            logger.info(f"Notification sent for feedback: {agenda_puu}")
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")