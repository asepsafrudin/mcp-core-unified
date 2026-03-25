"""
Google Drive Client for MCP Unified System.

Provides authenticated access to Google Drive API using service account.
"""

import os
import logging
import io
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, BinaryIO
from dataclasses import dataclass
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


@dataclass
class GDriveFile:
    """Represents a Google Drive file or folder."""
    id: str
    name: str
    mime_type: str
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    size: Optional[int] = None
    parents: List[str] = None
    web_view_link: Optional[str] = None
    
    def __post_init__(self):
        if self.parents is None:
            self.parents = []
    
    @property
    def is_folder(self) -> bool:
        return self.mime_type == "application/vnd.google-apps.folder"
    
    @property
    def is_google_doc(self) -> bool:
        return self.mime_type.startswith("application/vnd.google-apps.")


class GDriveClient:
    """
    Google Drive API client using service account authentication.
    
    Features:
    - List files and folders
    - Upload/download files
    - Create/delete folders
    - Search files
    """
    
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
    ]
    
    FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize GDrive client.
        
        Args:
            credentials_path: Path to service account JSON file.
                            If None, uses GDRIVE_CREDENTIALS_PATH env var.
        """
        self.credentials_path = credentials_path or self._get_credentials_path()
        self.service = None
        self._credentials = None
    
    def _get_credentials_path(self) -> str:
        """Get credentials path from environment."""
        creds_dir = os.getenv("GDRIVE_CREDENTIALS_PATH", "/home/aseps/MCP/OneDrive_PUU/PUU_2026/MCP/credential/gdrive")
        creds_file = os.getenv("GDRIVE_SERVICE_ACCOUNT_FILE", "oval-fort-461712-c0-78646012bddb.json")
        return os.path.join(creds_dir, creds_file)
    
    def connect(self) -> bool:
        """
        Authenticate and connect to Google Drive API.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")
            
            self._credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=self.SCOPES
            )
            
            self.service = build("drive", "v3", credentials=self._credentials, cache_discovery=False)
            return True
            
        except Exception as e:
            logger.error("[GDrive] Connection error: %s", e)
            return False
    
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.service is not None
    
    def ensure_connected(self) -> bool:
        """Ensure client is connected, attempt to connect if not."""
        if not self.is_connected():
            return self.connect()
        return True
    
    def list_files(
        self,
        folder_id: Optional[str] = "root",
        page_size: int = 100,
        include_trashed: bool = False
    ) -> List[GDriveFile]:
        """
        List files in a folder.
        
        Args:
            folder_id: Folder ID (default: root)
            page_size: Number of results per page
            include_trashed: Whether to include trashed files
        
        Returns:
            List of GDriveFile objects
        """
        if not self.ensure_connected():
            return []
        
        try:
            query_parts = []
            
            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")
            
            if not include_trashed:
                query_parts.append("trashed = false")
            
            query = " and ".join(query_parts) if query_parts else None
            
            results = self.service.files().list(
                q=query,
                pageSize=page_size,
                fields="files(id, name, mimeType, createdTime, modifiedTime, size, parents, webViewLink)"
            ).execute()
            
            files = []
            for item in results.get("files", []):
                files.append(self._parse_file(item))
            
            return files
            
        except HttpError as e:
            logger.error("[GDrive] List files error: %s", e)
            return []
    
    def search_files(
        self,
        query: str,
        page_size: int = 100,
        include_trashed: bool = False
    ) -> List[GDriveFile]:
        """
        Search files by name or content.
        
        Args:
            query: Search query (supports Google Drive query syntax)
            page_size: Number of results per page
            include_trashed: Whether to include trashed files
        
        Returns:
            List of GDriveFile objects
        """
        if not self.ensure_connected():
            return []
        
        try:
            # Build search query
            search_query = f"name contains '{query}'"
            
            if not include_trashed:
                search_query += " and trashed = false"
            
            results = self.service.files().list(
                q=search_query,
                pageSize=page_size,
                fields="files(id, name, mimeType, createdTime, modifiedTime, size, parents, webViewLink)"
            ).execute()
            
            files = []
            for item in results.get("files", []):
                files.append(self._parse_file(item))
            
            return files
            
        except HttpError as e:
            logger.error("[GDrive] Search files error: %s", e)
            return []
    
    def get_file_info(self, file_id: str) -> Optional[GDriveFile]:
        """
        Get file information by ID.
        
        Args:
            file_id: File or folder ID
        
        Returns:
            GDriveFile object or None
        """
        if not self.ensure_connected():
            return None
        
        try:
            result = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, createdTime, modifiedTime, size, parents, webViewLink"
            ).execute()
            
            return self._parse_file(result)
            
        except HttpError as e:
            logger.error("[GDrive] Get file info error: %s", e)
            return None
    
    def create_folder(
        self,
        name: str,
        parent_id: Optional[str] = "root"
    ) -> Optional[GDriveFile]:
        """
        Create a new folder.
        
        Args:
            name: Folder name
            parent_id: Parent folder ID (default: root)
        
        Returns:
            Created GDriveFile or None
        """
        if not self.ensure_connected():
            return None
        
        try:
            metadata = {
                "name": name,
                "mimeType": self.FOLDER_MIME_TYPE,
                "parents": [parent_id] if parent_id else []
            }
            
            result = self.service.files().create(body=metadata, fields="id, name, mimeType, createdTime, modifiedTime, parents, webViewLink").execute()
            
            return self._parse_file(result)
            
        except HttpError as e:
            logger.error("[GDrive] Create folder error: %s", e)
            return None
    
    def upload_file(
        self,
        file_path: str,
        parent_id: Optional[str] = "root",
        name: Optional[str] = None
    ) -> Optional[GDriveFile]:
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Local file path
            parent_id: Parent folder ID (default: root)
            name: Custom name for the file (default: use original filename)
        
        Returns:
            Uploaded GDriveFile or None
        """
        if not self.ensure_connected():
            return None
        
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_name = name or file_path.name
            
            metadata = {
                "name": file_name,
                "parents": [parent_id] if parent_id else []
            }
            
            media = MediaFileUpload(str(file_path), resumable=True)
            
            result = self.service.files().create(
                body=metadata,
                media_body=media,
                fields="id, name, mimeType, createdTime, modifiedTime, size, parents, webViewLink"
            ).execute()
            
            return self._parse_file(result)
            
        except HttpError as e:
            logger.error("[GDrive] Upload file error: %s", e)
            return None
    
    def download_file(
        self,
        file_id: str,
        destination_path: str
    ) -> bool:
        """
        Download a file from Google Drive.
        
        Args:
            file_id: File ID to download
            destination_path: Local path to save the file
        
        Returns:
            True if successful, False otherwise
        """
        if not self.ensure_connected():
            return False
        
        try:
            # Get file info to determine mime type
            file_info = self.get_file_info(file_id)
            
            if not file_info:
                return False
            
            # Handle Google Workspace files (Docs, Sheets, etc.)
            if file_info.is_google_doc:
                # Export to appropriate format
                export_mime = self._get_export_mime_type(file_info.mime_type)
                request = self.service.files().export_media(fileId=file_id, mimeType=export_mime)
            else:
                # Binary download for regular files
                request = self.service.files().get_media(fileId=file_id)
            
            # Download to memory first
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            # Save to file
            fh.seek(0)
            with open(destination_path, "wb") as f:
                f.write(fh.read())
            
            return True
            
        except HttpError as e:
            logger.error("[GDrive] Download file error: %s", e)
            return False
    
    def delete_file(self, file_id: str, permanently: bool = False) -> bool:
        """
        Delete a file or folder.
        
        Args:
            file_id: File or folder ID to delete
            permanently: If True, permanently delete (bypass trash)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.ensure_connected():
            return False
        
        try:
            if permanently:
                self.service.files().delete(fileId=file_id).execute()
            else:
                # Move to trash
                self.service.files().update(
                    fileId=file_id,
                    body={"trashed": True}
                ).execute()
            
            return True
            
        except HttpError as e:
            logger.error("[GDrive] Delete file error: %s", e)
            return False
    
    def _parse_file(self, item: Dict[str, Any]) -> GDriveFile:
        """Parse API response into GDriveFile."""
        created = item.get("createdTime")
        modified = item.get("modifiedTime")
        
        return GDriveFile(
            id=item.get("id"),
            name=item.get("name"),
            mime_type=item.get("mimeType"),
            created_time=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
            modified_time=datetime.fromisoformat(modified.replace("Z", "+00:00")) if modified else None,
            size=int(item.get("size", 0)) if item.get("size") else None,
            parents=item.get("parents", []),
            web_view_link=item.get("webViewLink")
        )
    
    def _get_export_mime_type(self, google_mime_type: str) -> str:
        """Get export MIME type for Google Workspace files."""
        export_types = {
            "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.google-apps.presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.google-apps.drawing": "image/png",
        }
        return export_types.get(google_mime_type, "application/pdf")


# Global client instance
_gdrive_client: Optional[GDriveClient] = None


def get_gdrive_client() -> GDriveClient:
    """Get or create global GDrive client instance."""
    global _gdrive_client
    if _gdrive_client is None:
        _gdrive_client = GDriveClient()
    return _gdrive_client
