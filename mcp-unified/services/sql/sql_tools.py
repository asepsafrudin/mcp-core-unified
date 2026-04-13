from typing import Dict, Any, List, Optional, Union, cast
from memory.longterm import pool, ensure_pool_open
from observability.logger import logger
from execution import registry
from psycopg.rows import dict_row
from psycopg import sql

@registry.register
async def query_db(query: Union[str, sql.Composable], params: Optional[List[Any]] = None, namespace: str = "default") -> Dict[str, Any]:
    """
    Execute SQL SELECT query on Postgres DB (mcp DB). Params for safety.
    Namespace for logging/filter (not enforced on query).
    Returns JSON rows.
    """
    if params is None:
        params = []
    
    query_str = str(query) if not isinstance(query, sql.Composable) else "composed query"
    logger.info("sql_query_executed", query_preview=query_str[:100], namespace=namespace)
    
    await ensure_pool_open()
    
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(cast(Any, query), params)
            rows = await cur.fetchall()
    
    logger.info("sql_query_success", row_count=len(rows), namespace=namespace)
    return {
        "success": True,
        "rows": [dict(row) for row in rows],
        "rowCount": len(rows),
        "namespace": namespace
    }

@registry.register
async def list_tables(namespace: str = "default") -> Dict[str, Any]:
    """
    List all tables in public schema.
    """
    result = await query_db(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name",
        namespace=namespace
    )
    return result

@registry.register
async def describe_table(table: str, namespace: str = "default") -> Dict[str, Any]:
    """
    Get table schema (columns, types, nullable).
    """
    result = await query_db(
        """
        SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
        FROM information_schema.columns 
        WHERE table_name = %s
        ORDER BY ordinal_position
        """,
        params=[table],
        namespace=namespace
    )
    return result

@registry.register
async def count_rows(table: str, namespace: str = "default") -> Dict[str, Any]:
    """
    Count rows in table.
    """
    # [REVIEWER] TABLE NAMES CANNOT BE PARAMETERIZED WITH %s
    # Use psycopg.sql.Identifier for safe table name interpolation
    query = sql.SQL("SELECT COUNT(*) as count FROM {}").format(sql.Identifier(table))
    result = await query_db(
        query,
        namespace=namespace
    )
    count = result["rows"][0]["count"] if result["rows"] else 0
    return {"success": True, "table": table, "count": count, "namespace": namespace}
