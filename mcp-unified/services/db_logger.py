import os
import psycopg2
import logging

logger = logging.getLogger(__name__)

# URL default berdasarkan environment sebelumnya
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    pg_user = os.environ.get("POSTGRES_USER") or os.environ.get("PG_USER") or "aseps"
    pg_password = os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PG_PASSWORD")
    pg_host = os.environ.get("POSTGRES_SERVER") or os.environ.get("PG_HOST") or "localhost"
    pg_port = os.environ.get("POSTGRES_PORT") or os.environ.get("PG_PORT") or "5432"
    pg_db = os.environ.get("POSTGRES_DB") or os.environ.get("PG_DATABASE") or "mcp"
    if pg_password:
        DB_URL = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
    else:
        DB_URL = f"postgresql://{pg_user}@{pg_host}:{pg_port}/{pg_db}"

def log_browser_action(engine: str, tool_name: str, status: str, 
                       input_summary: str = None, duration_ms: int = None, 
                       snapshot_tokens: int = 0, error_code: str = None, 
                       error_message: str = None, fallback_to: str = None):
    """
    Menyimpan log operasi hybrid browser (Playwright vs agent-browser) 
    ke dalam tabel browser_hybrid_logs PostgreSQL.
    
    Args:
        engine: 'agent_browser' atau 'playwright'
        tool_name: nama tool MCP yang dipanggil (misal: 'ab_navigate')
        status: 'success', 'error', 'fallback_triggered', 'fallback_executed'
        input_summary: ringkasan input untuk tool tersebut
        duration_ms: lama eksekusi dalam milidetik
        snapshot_tokens: jumlah token yang dihasilkan (terutama agent-browser)
        error_code: kode error jika gagal (misal 'AB_ELEM_NOT_FOUND')
        error_message: detail pesan error
        fallback_to: nama engine fallback jika terjadi perpindahan
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        query = """
            INSERT INTO browser_hybrid_logs 
            (engine, tool_name, status, input_summary, duration_ms, 
             snapshot_tokens, error_code, error_message, fallback_to)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cur.execute(query, (
            engine, tool_name, status, input_summary, duration_ms,
            snapshot_tokens, error_code, error_message, fallback_to
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Failed to log browser action to DB: {e}")
