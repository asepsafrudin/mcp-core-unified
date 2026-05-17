import json
import logging
from typing import Dict, Any, Optional
from memory.longterm import pool, ensure_pool_open

logger = logging.getLogger(__name__)

class TokenTracker:
    """
    Antigravity Token Tracker: Records detailed usage to database for pattern analysis.
    """
    
    async def track_usage(
        self, 
        task_id: str, 
        model: str, 
        usage_metadata: Dict[str, Any], 
        agent_id: str = "openhands",
        extra_metadata: Optional[Dict] = None
    ):
        """
        Save token usage to PostgreSQL.
        """
        prompt_tokens = usage_metadata.get("prompt_tokens", 0)
        completion_tokens = usage_metadata.get("completion_tokens", 0)
        # Handle different naming conventions (e.g. Gemini uses candidates_token)
        if not completion_tokens:
            completion_tokens = usage_metadata.get("candidates_token", 0)
        if not completion_tokens:
            completion_tokens = usage_metadata.get("candidates_tokens", 0)
            
        total_tokens = prompt_tokens + completion_tokens
        
        if total_tokens == 0:
            logger.debug(f"[Tracker] No tokens to record for task {task_id}")
            return

        try:
            await ensure_pool_open()
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                    INSERT INTO token_usage (task_id, agent_id, model, prompt_tokens, completion_tokens, total_tokens, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        task_id, 
                        agent_id, 
                        model, 
                        prompt_tokens, 
                        completion_tokens, 
                        total_tokens, 
                        json.dumps(extra_metadata or {})
                    ))
            
            logger.info(f"[Tracker] Recorded {total_tokens} tokens for task {task_id} (Model: {model})")
            
        except Exception as e:
            logger.error(f"[Tracker] Failed to track usage for task {task_id}: {e}")

    async def get_total_usage(self, days: int = 1) -> Dict[str, Any]:
        """
        Retrieve summary of usage for the last N days.
        """
        try:
            await ensure_pool_open()
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                    SELECT model, SUM(prompt_tokens), SUM(completion_tokens), SUM(total_tokens), COUNT(*)
                    FROM token_usage
                    WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '%s days'
                    GROUP BY model
                    """, (days,))
                    
                    rows = await cur.fetchall()
                    summary = {}
                    for row in rows:
                        summary[row[0]] = {
                            "prompt": row[1],
                            "completion": row[2],
                            "total": row[3],
                            "calls": row[4]
                        }
                    return summary
        except Exception as e:
            logger.error(f"[Tracker] Failed to get total usage: {e}")
            return {}

token_tracker = TokenTracker()
