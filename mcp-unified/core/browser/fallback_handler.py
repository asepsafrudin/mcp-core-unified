import logging
from typing import Dict, Any, Callable, Awaitable
import time
from .output_formatter import format_error, log_tool_call

logger = logging.getLogger("fallback_handler")

async def execute_with_fallback(
    primary_engine: str,
    primary_action: Callable[[], Awaitable[Dict[str, Any]]],
    fallback_engine: str,
    fallback_action: Callable[[], Awaitable[Dict[str, Any]]],
    tool_name: str
) -> Dict[str, Any]:
    """Execute action with automatic fallback to secondary engine."""
    
    start_time = time.time()
    
    # Try primary
    try:
        result = await primary_action()
        if result.get("success"):
            elapsed = int((time.time() - start_time) * 1000)
            result["engine_used"] = primary_engine
            result["fallback_used"] = False
            return result
    except Exception as e:
        logger.warning(f"Primary engine {primary_engine} failed: {e}")
        result = {"success": False, "error": str(e)}
        
    # Primary failed, attempt fallback
    logger.info(f"Initiating fallback to {fallback_engine}")
    fallback_start = time.time()
    
    try:
        fallback_result = await fallback_action()
        elapsed = int((time.time() - start_time) * 1000)
        
        if fallback_result.get("success"):
            fallback_result["engine_used"] = fallback_engine
            fallback_result["fallback_used"] = True
            log_tool_call(tool_name, fallback_engine, elapsed, 100, True, True)
            return fallback_result
        else:
            # Both failed
            error_msg = format_error(
                "FALLBACK_FAILED",
                f"Primary ({primary_engine}) and Fallback ({fallback_engine}) both failed. Last error: {fallback_result.get('error', 'Unknown')}",
                fallback_engine,
                "Check selectors, refs, or page state.",
                elapsed,
                True
            )
            log_tool_call(tool_name, fallback_engine, elapsed, 100, False, True)
            return error_msg
            
    except Exception as e:
        elapsed = int((time.time() - start_time) * 1000)
        error_msg = format_error(
            "FALLBACK_ERROR",
            str(e),
            fallback_engine,
            "Fatal error in fallback execution.",
            elapsed,
            True
        )
        log_tool_call(tool_name, fallback_engine, elapsed, 100, False, True)
        return error_msg
