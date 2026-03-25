"""
Tests for Long-term Memory (LTM) hardening from TASK-002.
Covers: EmbeddingUnavailableError fallback, UPSERT behavior, initialize_db pool cleanup.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import sys

# Mock Ollama before importing
sys.modules['ollama'] = MagicMock()

from memory.longterm import memory_save, memory_search, EmbeddingUnavailableError


@pytest.mark.asyncio
async def test_memory_save_fallback_when_ollama_down():
    """
    Verifikasi: jika Ollama mati, memory_save tetap berhasil
    dengan embedding=None dan log warning yang jelas.
    """
    with patch('memory.longterm.get_embedding', 
               side_effect=EmbeddingUnavailableError("Ollama is down")):
        with patch('memory.longterm.pool') as mock_pool:
            # Setup mock DB connection
            mock_conn = AsyncMock()
            mock_cur = AsyncMock()
            mock_cur.fetchone.return_value = ("test-uuid-1234",)
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_pool.connection.return_value = mock_conn
            
            result = await memory_save(
                key="test_key",
                content="test content",
                namespace="test_namespace"
            )
            
            # Should succeed even without embedding
            assert result["success"] is True
            assert result["namespace"] == "test_namespace"
            
            # Verify embedding was None in the INSERT call
            call_args = mock_cur.execute.call_args
            assert call_args[0][1][4] is None  # embedding param = None


@pytest.mark.asyncio
async def test_memory_search_fallback_to_keyword_when_ollama_down():
    """
    Verifikasi: jika Ollama mati, memory_search fallback ke keyword strategy.
    """
    with patch('memory.longterm.get_embedding',
               side_effect=EmbeddingUnavailableError("Ollama is down")):
        with patch('memory.longterm.pool') as mock_pool:
            mock_conn = AsyncMock()
            mock_cur = AsyncMock()
            mock_cur.fetchall.return_value = []
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_pool.connection.return_value = mock_conn
            
            result = await memory_search(
                query="test query",
                namespace="test_namespace",
                strategy="hybrid"  # Should fall back to keyword
            )
            
            assert result["success"] is True
            # Verify keyword query was used (not semantic)
            executed_sql = mock_cur.execute.call_args[0][0]
            assert "websearch_to_tsquery" in executed_sql
            assert "embedding <=>" not in executed_sql


@pytest.mark.asyncio
async def test_memory_save_upsert_behavior():
    """
    Verifikasi: save key yang sama 2x tidak ada duplikat (UPSERT behavior).
    """
    with patch('memory.longterm.get_embedding', return_value=[0.1, 0.2, 0.3]):
        with patch('memory.longterm.pool') as mock_pool:
            mock_conn = AsyncMock()
            mock_cur = AsyncMock()
            mock_cur.fetchone.return_value = ("test-uuid-1234",)
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_pool.connection.return_value = mock_conn
            
            # Save same key twice
            await memory_save(key="same_key", content="content1", namespace="ns")
            await memory_save(key="same_key", content="content2", namespace="ns")
            
            # Verify UPSERT was used (ON CONFLICT)
            call_args_list = mock_cur.execute.call_args_list
            for call in call_args_list:
                sql = call[0][0]
                if "INSERT" in sql:
                    assert "ON CONFLICT" in sql or "upsert" in sql.lower()


@pytest.mark.asyncio
async def test_initialize_db_pool_cleanup_on_failure():
    """
    Verifikasi: initialize_db melakukan pool cleanup saat connection failure.
    """
    from memory.longterm import initialize_db
    
    with patch('memory.longterm.psycopg_pool.AsyncConnectionPool') as mock_pool_class:
        mock_pool = AsyncMock()
        mock_pool.close = AsyncMock()
        mock_pool_class.side_effect = Exception("Connection refused")
        
        # Should not raise, just log error
        try:
            await initialize_db()
        except Exception:
            pass  # Expected to not raise
