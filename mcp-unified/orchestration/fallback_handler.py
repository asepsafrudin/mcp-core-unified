import logging
import traceback
from typing import Callable, Dict, Any

from tools.session_bridge import session_bridge_export, session_bridge_import

logger = logging.getLogger(__name__)

try:
    from services.db_logger import log_browser_action
except ImportError:
    log_browser_action = None

def with_fallback(engine_name: str, fallback_engine: str, tool_func: Callable, *args, **kwargs) -> Dict[str, Any]:
    """
    Middleware/wrapper untuk menjalankan tool browser dengan mekanisme fallback.
    
    Jika eksekusi tool_func() gagal dengan error timeout atau tidak ditemukan elemen (AB_ELEM_NOT_FOUND),
    maka state diekstrak dari engine_name dan diimpor ke fallback_engine.
    Lalu, aksi akan diminta untuk di-retry oleh LLM atau dijalankan ulang secara native jika memungkinkan.
    
    Karena eksekusi tool MCP spesifik terhadap engine (misal ab_navigate vs pw_navigate),
    maka wrapper ini akan mengembalikan sinyal "fallback_triggered" agar sistem/router mengulangi dengan engine baru.
    """
    try:
        result = tool_func(*args, **kwargs)
        
        # Cek jika ada error code spesifik
        if isinstance(result, dict) and not result.get("success", True):
            error_code = result.get("error", "")
            
            if error_code in ["TIMEOUT", "AB_ELEM_NOT_FOUND", "PW_SELECTOR_FAILED"]:
                logger.warning(f"Error {error_code} detected in {engine_name}. Triggering fallback to {fallback_engine}.")
                
                # Ekspor dari current engine
                export_res = session_bridge_export(source_engine=engine_name)
                
                # Impor ke fallback engine
                import_res = session_bridge_import(
                    target_engine=fallback_engine, 
                    session_data=export_res.get("session_data"),
                    session_path=export_res.get("export_path")
                )
                
                # Log fallback event
                if log_browser_action:
                    log_browser_action(
                        engine=engine_name, tool_name=tool_func.__name__, 
                        status="fallback_triggered", error_code=error_code,
                        fallback_to=fallback_engine
                    )
                    
                return {
                    "success": False,
                    "error": "FALLBACK_TRIGGERED",
                    "original_error": error_code,
                    "message": f"Tool failed. Session migrated to {fallback_engine}. Please retry using {fallback_engine} tools.",
                    "import_status": import_res
                }
                
        return result
        
    except Exception as e:
        logger.error(f"Unhandled exception in tool {tool_func.__name__}: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": "UNHANDLED_EXCEPTION",
            "message": str(e)
        }
