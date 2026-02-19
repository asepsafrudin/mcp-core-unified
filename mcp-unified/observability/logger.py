import structlog
import logging
import sys
import uuid
from contextvars import ContextVar
from core.config import settings

# Context variable for request/correlation ID
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")

def get_correlation_id() -> str:
    return correlation_id_ctx.get()

def set_correlation_id(val: str):
    correlation_id_ctx.set(val)

def add_correlation_id(_, __, event_dict):
    cid = get_correlation_id()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict

def configure_logger():
    processors = [
        structlog.contextvars.merge_contextvars,
        add_correlation_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.JSON_LOGS:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

logger = structlog.get_logger()
