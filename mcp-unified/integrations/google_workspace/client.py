"""
Google Workspace Client for MCP Unified System.

Provides authenticated access to Gmail, Calendar, People (Contacts), 
Sheets, and Docs APIs.
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GoogleWorkspaceClient:
    """
    Unified client for Google Workspace APIs.
    Supports Service Account authentication.
    """
    
    # Scopes for all requested services
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.modify",       # Gmail: Read/Write
        "https://www.googleapis.com/auth/calendar",           # Calendar: Read/Write
        "https://www.googleapis.com/auth/contacts",           # People: Read/Write
        "https://www.googleapis.com/auth/spreadsheets",       # Sheets: Read/Write
        "https://www.googleapis.com/auth/documents",          # Docs: Read/Write
        "https://www.googleapis.com/auth/drive.file",         # Drive: File access
        "https://www.googleapis.com/auth/userinfo.profile",  # Profile access for 'me'
    ]
    
    def __init__(self, credentials_path: Optional[str] = None, subject_email: Optional[str] = None):
        """
        Initialize Google Workspace client.
        
        Args:
            credentials_path: Path to service account JSON OR OAuth client JSON.
            subject_email: Email to impersonate (only for Service Account).
        """
        self.credentials_path = credentials_path or self._get_credentials_path()
        self.subject_email = subject_email or os.getenv("GOOGLE_WORKSPACE_SUBJECT_EMAIL")
        
        # OAuth files
        self.oauth_client_file = os.getenv("GOOGLE_WORKSPACE_OAUTH_CLIENT_FILE")
        self.token_file = os.getenv("GOOGLE_WORKSPACE_TOKEN_FILE", "token.json")
        
        self._credentials = None
        self._services = {}
        self._flow = None # To store flow state for PKCE
    
    def _get_credentials_path(self) -> str:
        """Get credentials path from environment."""
        root_dir = "/home/aseps/MCP"
        # Default path - use service account credentials
        default_dir = os.path.join(root_dir, "config/credentials/google")
        default_file = "mcp-gmail-482015-682b788ee191.json"  # Service account file
        
        creds_dir = os.getenv("GOOGLE_WORKSPACE_CREDENTIALS_PATH", default_dir)
        creds_file = os.getenv("GOOGLE_WORKSPACE_SERVICE_ACCOUNT_FILE", default_file)
        
        return os.path.join(creds_dir, creds_file)
    
    def connect(self) -> bool:
        """
        Authenticate and prepare credentials.
        Priority: 1. OAuth2 (if token exists), 2. Service Account
        """
        try:
            # Try OAuth2 flow if token file exists or client file is provided
            if self._try_connect_oauth2():
                return True

            # Fallback to Service Account if provided
            if self.credentials_path and os.path.exists(self.credentials_path):
                # Only use service account if it's NOT an OAuth client file (checking for "type": "service_account")
                with open(self.credentials_path, 'r') as f:
                    data = json.load(f)
                    if data.get("type") == "service_account":
                        self._credentials = service_account.Credentials.from_service_account_file(
                            self.credentials_path,
                            scopes=self.SCOPES
                        )
                        if self.subject_email:
                            self._credentials = self._credentials.with_subject(self.subject_email)
                        return True
            
            return False
            
        except Exception as e:
            logger.error("[GoogleWorkspace] Connection error: %s", e)
            return False

    def _try_connect_oauth2(self) -> bool:
        """Attempt to load existing OAuth2 credentials from token.json."""
        try:
            token_path = self._get_token_path()
            if os.path.exists(token_path):
                self._credentials = Credentials.from_authorized_user_file(token_path, self.SCOPES)
                
                # If credentials expired, refresh them
                if self._credentials and self._credentials.expired and self._credentials.refresh_token:
                    self._credentials.refresh(Request())
                    # Save updated token
                    with open(token_path, 'w') as token:
                        token.write(self._credentials.to_json())
                
                return self._credentials and self._credentials.valid
            return False
        except Exception as e:
            logger.error("[GoogleWorkspace] OAuth2 loading error: %s", e)
            return False

    def _get_token_path(self) -> str:
        """Get absolute path for the token file."""
        if os.path.isabs(self.token_file):
            return self.token_file
        
        creds_dir = os.getenv("GOOGLE_WORKSPACE_CREDENTIALS_PATH")
        if creds_dir:
            return os.path.join(creds_dir, self.token_file)
        return self.token_file

    def get_auth_url(self) -> str:
        """Generate Authorization URL for the user to visit (Option B)."""
        creds_dir = os.getenv("GOOGLE_WORKSPACE_CREDENTIALS_PATH")
        client_file = os.path.join(creds_dir, self.oauth_client_file)
        
        self._flow = InstalledAppFlow.from_client_secrets_file(client_file, self.SCOPES)
        self._flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob" # For manual copy-paste of code
        auth_url, _ = self._flow.authorization_url(prompt='consent', access_type='offline')
        return auth_url

    def finish_auth(self, code: str) -> bool:
        """Finish OAuth2 flow with the code provided by user."""
        try:
            if not self._flow:
                # If flow is lost (e.g. process restarted), we might need to recreate it
                # but PKCE will likely fail. Re-running the script is better.
                logger.error("[GoogleWorkspace] Flow state lost. Please restart the setup script.")
                return False

            token_path = self._get_token_path()
            self._flow.fetch_token(code=code)
            
            self._credentials = self._flow.credentials
            
            with open(token_path, 'w') as token:
                token.write(self._credentials.to_json())
            
            return True
        except Exception as e:
            logger.error("[GoogleWorkspace] Finalizing auth failed: %s", e)
            return False
            
    def get_service(self, service_name: str, version: str):
        """Get or build a Google API service instance."""
        service_key = f"{service_name}_{version}"
        if service_key not in self._services:
            if not self._credentials and not self.connect():
                raise ConnectionError("Failed to authenticate with Google Workspace")
            
            self._services[service_key] = build(
                service_name, 
                version, 
                credentials=self._credentials, 
                cache_discovery=False
            )
        return self._services[service_key]

    # --- Gmail Service ---
    @property
    def gmail(self):
        return self.get_service("gmail", "v1")

    # --- Calendar Service ---
    @property
    def calendar(self):
        return self.get_service("calendar", "v3")

    # --- People (Contacts) Service ---
    @property
    def people(self):
        return self.get_service("people", "v1")

    # --- Sheets Service ---
    @property
    def sheets(self):
        return self.get_service("sheets", "v4")

    # --- Docs Service ---
    @property
    def docs(self):
        return self.get_service("docs", "v1")


# Global client instance
_google_workspace_client: Optional[GoogleWorkspaceClient] = None

def get_google_client() -> GoogleWorkspaceClient:
    """Get or create global Google Workspace client instance."""
    global _google_workspace_client
    if _google_workspace_client is None:
        _google_workspace_client = GoogleWorkspaceClient()
    return _google_workspace_client
