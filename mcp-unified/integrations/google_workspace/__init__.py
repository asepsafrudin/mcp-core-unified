"""
Google Workspace Integration for MCP Unified.
"""

from .client import GoogleWorkspaceClient, get_google_client
from .tools import (
    gmail_list_messages,
    gmail_send_message,
    calendar_list_events,
    people_list_contacts,
    people_search_contacts,
    sheets_read_values
)

__all__ = [
    "GoogleWorkspaceClient",
    "get_google_client",
    "gmail_list_messages",
    "gmail_send_message",
    "calendar_list_events",
    "people_list_contacts",
    "people_search_contacts",
    "sheets_read_values"
]
