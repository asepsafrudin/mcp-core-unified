from fastapi import FastAPI, Request
from core.config import settings
from observability.logger import configure_logger, logger, set_correlation_id
import uuid
import time
from contextlib import asynccontextmanager

from memory.longterm import initialize_db
from memory.working import working_memory
from messaging.queue_client import mq_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    configure_logger()
    logger.info("server_startup", version=settings.VERSION)
    await initialize_db()
    await working_memory.connect()
    await mq_client.connect()
    
    # Discover remote MCP tools
    from execution.registry import discover_remote_tools
    await discover_remote_tools()
    
    yield
    # Shutdown
    await mq_client.close()
    await working_memory.close()
    logger.info("server_shutdown")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

@app.middleware("http")
async def add_correlation_id_middleware(request: Request, call_next):
    # Generate or extract correlation ID
    cid = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    set_correlation_id(cid)
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=process_time
    )
    
    response.headers["X-Correlation-ID"] = cid
    return response

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

from observability.metrics import metrics

@app.get("/metrics/summary")
async def metrics_summary():
    return metrics.get_summary()

from execution.registry import registry
from pydantic import BaseModel

class ToolCall(BaseModel):
    name: str
    arguments: dict = {}

@app.post("/tools/list")
async def list_tools():
    return {"tools": registry.list_tools()}

from core.circuit_breaker import circuit_breaker, CircuitBreakerOpenError
from core.rate_limiter import budget_limiter, BudgetExceededError

@app.post("/tools/call")
async def call_tool(call: ToolCall):
    start_time = time.time()
    try:
        # 1. Rate Limiting Check (Estimate 1000 tokens per call if not code)
        # This is heuristics. Ideally we count tokens of input args.
        estimated_cost = 100 
        budget_limiter.check_and_consume(estimated_cost)
        
        # 2. Circuit Breaker Execution
        result = await circuit_breaker.call(
            registry.execute, 
            call.name, 
            call.arguments
        )
        duration = time.time() - start_time
        
        # Record success
        # Record success
        duration = time.time() - start_time
        metrics.record_task(success=True, duration=duration)
        
        logger.info("tool_execution", tool=call.name, success=True, duration=duration)
        return {"content": [{"type": "text", "text": str(result)}]}
        
    except (BudgetExceededError, CircuitBreakerOpenError) as e:
        duration = time.time() - start_time
        metrics.record_task(success=False, duration=duration, error=type(e).__name__)
        logger.warning("execution_blocked", reason=str(e))
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Blocked: {str(e)}"}]
        }
        
    except Exception as e:
        duration = time.time() - start_time
        # Record failure
        metrics.record_task(success=False, duration=duration, error=type(e).__name__)
        
        logger.error("tool_failed", tool=call.name, error=str(e))
        return {
            "isError": True,
            "content": [{"type": "text", "text": str(e)}]
        }
