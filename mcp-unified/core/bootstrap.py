"""
Shared bootstrap logic for MCP Unified servers (stdio and SSE).
Handles component initialization and tool registration.
"""
import logging
import inspect
import json
from pathlib import Path
import os
import sys

from execution import registry, resource_registry, prompt_registry
from execution.registry import discover_remote_tools
from execution.discovery import discover_all_standard_locations
from memory.longterm import initialize_db
from memory.working import working_memory

# Import scheduler tools
from scheduler.tools import get_scheduler_tools
from scheduler.database import init_schema as init_scheduler_schema

# Import Google Drive tools
from integrations.gdrive.tools import (
    gdrive_list_files,
    gdrive_search_files,
    gdrive_get_file_info,
    gdrive_create_folder,
    gdrive_upload_file,
    gdrive_download_file,
    gdrive_delete_file,
)

# Import Google Workspace tools
from integrations.google_workspace.tools import (
    gmail_list_messages,
    gmail_send_message,
    calendar_list_events,
    people_list_contacts,
    people_search_contacts,
    sheets_read_values,
)

# Import WhatsApp tools
from integrations.whatsapp.tools import (
    whatsapp_get_status,
    whatsapp_send_message,
    whatsapp_get_qr,
    whatsapp_list_chats,
    whatsapp_get_messages,
)

# Import Unified Sync tools
from integrations.common.sync import (
    tool_sync_communications,
    tool_get_unified_history,
)

# Import Knowledge Tools
from knowledge.tools import (
    knowledge_search,
    knowledge_ingest_text,
    knowledge_ingest_spreadsheet,
    knowledge_ingest_googlesheet,
    knowledge_list_namespaces,
)

logger = logging.getLogger("mcp-unified-bootstrap")

async def initialize_all_components():
    """
    Initialize all system components and register all tools.
    Shared between mcp_server.py (stdio) and mcp_server_sse.py (HTTP).
    """
    logger.info("Starting global component initialization...")

    # 1. Initialize PostgreSQL schema
    try:
        await initialize_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"CRITICAL: Database initialization failed: {e}")
        logger.error("Memory tools will not function. Check PostgreSQL connection.")
    
    # 2. Initialize Scheduler database schema
    try:
        await init_scheduler_schema()
        logger.info("Scheduler database schema initialized successfully")
    except Exception as e:
        logger.warning(f"Scheduler schema initialization failed: {e}")
    
    # 3. Initialize Redis (working memory)
    try:
        await working_memory.connect()
        logger.info("Working memory (Redis) connected successfully")
    except Exception as e:
        logger.warning(f"Working memory unavailable: {e}")
    
    # 4. Register scheduler tools
    try:
        scheduler_tools = get_scheduler_tools()
        for tool_func in scheduler_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(scheduler_tools)} scheduler tools")
    except Exception as e:
        logger.warning(f"Failed to register scheduler tools: {e}")
    
    # 5. Register Google Drive tools
    try:
        gdrive_tools = [
            gdrive_list_files,
            gdrive_search_files,
            gdrive_get_file_info,
            gdrive_create_folder,
            gdrive_upload_file,
            gdrive_download_file,
            gdrive_delete_file,
        ]
        for tool_func in gdrive_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(gdrive_tools)} Google Drive tools")
    except Exception as e:
        logger.warning(f"Failed to register Google Drive tools: {e}")

    # 5b. Register Google Workspace tools
    try:
        gw_tools = [
            gmail_list_messages,
            gmail_send_message,
            calendar_list_events,
            people_list_contacts,
            people_search_contacts,
            sheets_read_values,
        ]
        for tool_func in gw_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(gw_tools)} Google Workspace tools")
    except Exception as e:
        logger.warning(f"Failed to register Google Workspace tools: {e}")
    
    # 5c. Register WhatsApp tools
    try:
        wa_tools = [
            whatsapp_get_status,
            whatsapp_send_message,
            whatsapp_get_qr,
            whatsapp_list_chats,
            whatsapp_get_messages,
        ]
        for tool_func in wa_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(wa_tools)} WhatsApp tools")
    except Exception as e:
        logger.warning(f"Failed to register WhatsApp tools: {e}")

    # 5d. Register Unified Sync tools
    try:
        sync_tools = [
            tool_sync_communications,
            tool_get_unified_history,
        ]
        for tool_func in sync_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(sync_tools)} Unified Sync tools")
    except Exception as e:
        logger.warning(f"Failed to register Unified Sync tools: {e}")

    # 5e. Register Knowledge Tools
    try:
        kn_tools = [
            knowledge_search,
            knowledge_ingest_text,
            knowledge_ingest_spreadsheet,
            knowledge_ingest_googlesheet,
            knowledge_list_namespaces,
        ]
        for tool_func in kn_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(kn_tools)} Knowledge tools")
    except Exception as e:
        logger.warning(f"Failed to register Knowledge tools: {e}")

    # 5f. Register Semantic Analysis tools
    try:
        import tools.code.semantic_tools  # Trigger auto-registration via @register_tool
        logger.info("Registered Semantic Analysis tools")
    except Exception as e:
        logger.warning(f"Failed to register Semantic Analysis tools: {e}")

    # 5g. Register Blackbox tools
    try:
        import integrations.blackbox.tools  # Trigger auto-registration via @register_tool
        logger.info("Registered BlackboxAI tools")
    except Exception as e:
        logger.warning(f"Failed to register Blackbox tools: {e}")

    # 5h. Register Monitoring tools
    try:
        import core.monitoring.health_tools  # Trigger auto-registration via @register_tool
        logger.info("Registered Monitoring tools")
    except Exception as e:
        logger.warning(f"Failed to register Monitoring tools: {e}")

    # 5i. Register Default Resources
    try:
        from core.resources import register_default_resources
        await register_default_resources()
        logger.info("Registered default resources")
    except Exception as e:
        logger.warning(f"Failed to register default resources: {e}")

    # 5j. Register Default Prompts
    try:
        from core.prompts import register_default_prompts
        register_default_prompts()
        logger.info("Registered default prompts")
    except Exception as e:
        logger.warning(f"Failed to register default prompts: {e}")

    # 5k. Register OCR tools (Optional)
    try:
        from services.ocr.tools import register_tools as register_ocr_tools
        register_ocr_tools()
        logger.info("Registered OCR tools (ocr/extract_text, ocr/parse_document)")
    except ImportError:
        logger.warning("OCR tools (paddleocr) dependencies missing. Skipping OCR registration.")
    except Exception as e:
        logger.warning(f"Failed to register OCR tools: {e}")

    # 6. Discover remote tools
    try:
        await discover_remote_tools()
        logger.info("Remote tools discovery completed")
    except Exception as e:
        logger.warning(f"Failed to discover remote tools: {e}")

    # 7. Discover local dynamic plugins
    try:
        discover_all_standard_locations()
        logger.info("Local plugins discovery completed")
    except Exception as e:
        logger.error(f"Failed to discover local plugins: {e}")
