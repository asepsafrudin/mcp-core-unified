from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .dependencies import get_deps
from .routes import router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🟢 Starting LLM API Gateway...")
    deps = get_deps()
    await deps.initialize_all()
    yield
    # Shutdown
    logger.info("🔴 Shutting down LLM API Gateway...")
    # Any necessary cleanup here
    if deps.text_to_sql:
        if hasattr(deps.text_to_sql, "close"):
            await deps.text_to_sql.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="MCP Unified LLM Gateway",
        description="Headless API service for Multi-Channel Chatbot integration",
        version="1.0.0",
        lifespan=lifespan
    )

    # Allow CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Adjust for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach routers
    app.include_router(router)

    return app

app = create_app()
