import sys
import json
import logging

logger = logging.getLogger("mcp-unified-callback")

async def agent_callback(message: str, urgency: str = "normal") -> str:
    """
    Mengirimkan pesan feedback atau pertanyaan kembali ke parent agent (IDE/User).
    Gunakan ini jika Anda membutuhkan klarifikasi atau ingin melaporkan progress penting
    yang perlu diketahui oleh agen pengendali utama.
    
    Args:
        message: Pesan teks yang ingin disampaikan.
        urgency: Level kepentingan ('normal', 'high', 'critical').
    """
    # Bungkus dalam format JSON agar mudah di-parse oleh parent agent listener
    callback_payload = {
        "type": "agent_callback",
        "urgency": urgency,
        "content": message
    }
    
    # Print ke stderr dengan prefix khusus agar terdeteksi di log stream
    try:
        sys.stderr.write(f"\n<<<AGENT_SIGNAL>>>\n{json.dumps(callback_payload)}\n<<<END_SIGNAL>>>\n")
        sys.stderr.flush()
        logger.info(f"Signal callback terkirim: {message[:50]}...")
        return f"Signal terkirim ke parent agent: {message}"
    except Exception as e:
        logger.error(f"Gagal mengirim signal callback: {e}")
        return f"Gagal mengirim signal: {str(e)}"

# Register tool manual saat module di-load oleh discovery
try:
    from execution.registry import registry
    registry.register(agent_callback)
except Exception:
    # Jika dipanggil dari luar konteks MCP (misal test mentah), abaikan registrasi
    pass
