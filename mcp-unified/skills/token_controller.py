import logging
from typing import Dict, Any, List
from orchestration.antigravity_ledger import ledger

logger = logging.getLogger(__name__)

class TokenController:
    """
    The Accountant: Responsible for token estimation and recording usage.
    """
    
    def __init__(self, char_to_token_ratio: float = 4.0, safety_factor: float = 1.2):
        self.char_to_token_ratio = char_to_token_ratio
        self.safety_factor = safety_factor

    def estimate_tokens(self, content: str) -> int:
        """
        Estimate tokens: (Chars / 4) * 1.2.
        Simple but effective for pre-flight checks.
        """
        if not content:
            return 0
        char_count = len(content)
        estimate = int((char_count / self.char_to_token_ratio) * self.safety_factor)
        return max(1, estimate)

    async def estimate_files(self, file_paths: List[str]) -> int:
        """Estimate total tokens for a list of files."""
        total = 0
        for path in file_paths:
            try:
                # We could use ledger.get_file_index here if we cached estimates
                cached = await ledger.get_file_index(path)
                if cached and "estimated_tokens" in cached:
                    total += cached["estimated_tokens"]
                    continue
                
                # If not cached, read and estimate (simulated here, should use file_tools)
                # For pre-flight, we might just use file size as a proxy if we don't want to read all
                import os
                if os.path.exists(path):
                    size = os.path.getsize(path)
                    # Rough estimate from size (1 byte ~ 1 char for plain text)
                    est = int((size / self.char_to_token_ratio) * self.safety_factor)
                    total += est
                    
                    # Cache the estimate
                    await ledger.cache_file_index(path, {"estimated_tokens": est})
            except Exception as e:
                logger.warning(f"[Accountant] Failed to estimate {path}: {e}")
        return total

    async def record_usage(
        self, 
        usage_metadata: Dict[str, Any], 
        task_id: str = "unknown", 
        model: str = "unknown"
    ):
        """
        Update ledger (Redis) and tracker (PostgreSQL) with real usage data.
        """
        prompt_tokens = usage_metadata.get("prompt_tokens", 0)
        completion_tokens = usage_metadata.get("completion_tokens", 0) or usage_metadata.get("candidates_tokens", 0)
        total_tokens = prompt_tokens + (completion_tokens or 0)
        
        if total_tokens > 0:
            # 1. Update Real-time Ledger (Redis)
            await ledger.increment_quota(total_tokens)
            
            # 2. Update Long-term Tracker (PostgreSQL)
            from monitoring.token_tracker import token_tracker
            await token_tracker.track_usage(
                task_id=task_id,
                model=model,
                usage_metadata=usage_metadata
            )
            
            logger.info(f"[Accountant] Recorded usage: {total_tokens} tokens for task {task_id}")

token_controller = TokenController()
