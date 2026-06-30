import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class RouterService:
    """
    Super-fast Intent Router untuk mendeteksi intensi percakapan.
    Ini memisahkan pesan menjadi kategori agar tool yang dikirim ke LLM 
    tidak terlalu banyak (mencegah context bloat).
    """
    def __init__(self, ai_manager):
        self.ai_manager = ai_manager
        
    async def classify_intent(self, user_id: int, message: str) -> str:
        # Gunakan provider Gemini jika tersedia karena model flash-nya sangat cepat.
        # Jika tidak, gunakan provider yang aktif.
        provider = self.ai_manager.get_provider('gemini')
        if not provider:
            provider = self.ai_manager.current_provider
            
        system_prompt = """Kamu adalah Intent Router yang SUPER CEPAT.
Tugasmu HANYA membalas dengan SATU KATA dari pilihan berikut berdasarkan pesan user:

1. CHAT: Jika pesan berupa sapaan, basa-basi, pertanyaan umum yang tidak butuh data realtime, atau ucapan terima kasih.
2. DATABASE_QUERY: Jika user meminta perhitungan kompleks, statistik, data agrerat, atau filter dengan tanggal/waktu (misal: "berapa jumlah surat minggu ini", "rekap surat bulan april", "total surat masuk").
3. CORRESPONDENCE: Jika user ingin mencari satu/beberapa surat spesifik (misal: "cari surat dari kemenag", "apa isi surat nomor 123", "tampilkan disposisi surat terbaru", "surat luar bangda", "arsip 2025", "histori arsip").
4. PERSONNEL: Jika berhubungan dengan data staf, pegawai, absensi, jabatan, atau sinkronisasi data pegawai.

Aturan mutlak:
- Balas HANYA dengan SATU KATA (CHAT, DATABASE_QUERY, CORRESPONDENCE, atau PERSONNEL).
- Jangan berikan penjelasan apa pun.
- Jangan gunakan formatting (tanpa bold/italic)."""

        try:
            # Gunakan limit memori/token yang kecil jika API mendukungnya, tapi kita cukup pakai default
            response = await provider.generate_response(
                user_id=user_id,
                message=message,
                system_prompt=system_prompt
            )
            intent = response.text.strip().upper()
            
            if hasattr(provider, 'strip_thinking_tags'):
                intent = provider.strip_thinking_tags(intent)
                
            for valid in ["CHAT", "DATABASE_QUERY", "CORRESPONDENCE", "PERSONNEL"]:
                if valid in intent:
                    logger.info(f"🧭 Intent Router: {valid}")
                    return valid
                    
            logger.warning(f"🧭 Intent Router returned unknown intent: {intent}. Defaulting to CHAT.")
            return "CHAT"
        except Exception as e:
            logger.warning(f"🧭 Intent Router failed: {e}. Fallback to heuristics.")
            # Fallback heuristic super sederhana jika LLM mati
            msg_lower = message.lower()
            if any(k in msg_lower for k in ['berapa', 'jumlah', 'statistik', 'rekap', 'total']):
                return "DATABASE_QUERY"
            elif any(k in msg_lower for k in ['surat', 'cari', 'posisi', 'disposisi', 'agenda', 'dokumen']):
                return "CORRESPONDENCE"
            elif any(k in msg_lower for k in ['staf', 'pegawai', 'pic', 'beban kerja', 'sinkron', 'nip']):
                return "PERSONNEL"
            return "CHAT"
