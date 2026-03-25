"""
MCP Tools for Google Drive Integration.

Provides MCP tool decorators for CRUD operations on Google Drive.
"""

import json
from typing import Optional, List
from mcp.server.fastmcp import Context

from .client import get_gdrive_client, GDriveFile


def _file_to_dict(file: GDriveFile) -> dict:
    """Convert GDriveFile to dictionary for JSON serialization."""
    return {
        "id": file.id,
        "name": file.name,
        "mime_type": file.mime_type,
        "is_folder": file.is_folder,
        "is_google_doc": file.is_google_doc,
        "created_time": file.created_time.isoformat() if file.created_time else None,
        "modified_time": file.modified_time.isoformat() if file.modified_time else None,
        "size": file.size,
        "parents": file.parents,
        "web_view_link": file.web_view_link
    }


async def gdrive_list_files(
    ctx: Context,
    folder_id: Optional[str] = "root",
    include_trashed: bool = False,
    page_size: int = 100
) -> str:
    """
    List files and folders in a Google Drive folder.
    
    Args:
        folder_id: Folder ID to list (default: 'root' for My Drive)
        include_trashed: Whether to include trashed files
        page_size: Maximum number of results (default: 100)
    
    Returns:
        JSON string with list of files and folders
    """
    try:
        client = get_gdrive_client()
        files = client.list_files(
            folder_id=folder_id,
            page_size=page_size,
            include_trashed=include_trashed
        )
        
        result = {
            "success": True,
            "folder_id": folder_id,
            "total_files": len(files),
            "files": [_file_to_dict(f) for f in files]
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "folder_id": folder_id
        }, indent=2, ensure_ascii=False)


async def gdrive_search_files(
    ctx: Context,
    query: str,
    include_trashed: bool = False,
    page_size: int = 100
) -> str:
    """
    Search files and folders in Google Drive by name.
    
    Args:
        query: Search query (searches in file names)
        include_trashed: Whether to include trashed files
        page_size: Maximum number of results (default: 100)
    
    Returns:
        JSON string with search results
    """
    try:
        client = get_gdrive_client()
        files = client.search_files(
            query=query,
            page_size=page_size,
            include_trashed=include_trashed
        )
        
        result = {
            "success": True,
            "query": query,
            "total_results": len(files),
            "files": [_file_to_dict(f) for f in files]
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "query": query
        }, indent=2, ensure_ascii=False)


async def gdrive_get_file_info(
    ctx: Context,
    file_id: str
) -> str:
    """
    Get detailed information about a file or folder.
    
    Args:
        file_id: File or folder ID
    
    Returns:
        JSON string with file information
    """
    try:
        client = get_gdrive_client()
        file = client.get_file_info(file_id)
        
        if not file:
            return json.dumps({
                "success": False,
                "error": "File not found",
                "file_id": file_id
            }, indent=2, ensure_ascii=False)
        
        result = {
            "success": True,
            "file": _file_to_dict(file)
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "file_id": file_id
        }, indent=2, ensure_ascii=False)


async def gdrive_create_folder(
    ctx: Context,
    name: str,
    parent_id: Optional[str] = "root"
) -> str:
    """
    Create a new folder in Google Drive.
    
    Args:
        name: Name for the new folder
        parent_id: Parent folder ID (default: 'root' for My Drive)
    
    Returns:
        JSON string with created folder information
    """
    try:
        client = get_gdrive_client()
        folder = client.create_folder(name=name, parent_id=parent_id)
        
        if not folder:
            return json.dumps({
                "success": False,
                "error": "Failed to create folder",
                "name": name,
                "parent_id": parent_id
            }, indent=2, ensure_ascii=False)
        
        result = {
            "success": True,
            "message": f"Folder '{name}' created successfully",
            "folder": _file_to_dict(folder)
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "name": name,
            "parent_id": parent_id
        }, indent=2, ensure_ascii=False)


async def gdrive_upload_file(
    ctx: Context,
    file_path: str,
    parent_id: Optional[str] = "root",
    name: Optional[str] = None
) -> str:
    """
    Upload a file to Google Drive.
    
    Args:
        file_path: Local file path to upload
        parent_id: Parent folder ID (default: 'root' for My Drive)
        name: Custom name for the file (optional, uses original filename if not provided)
    
    Returns:
        JSON string with uploaded file information
    """
    try:
        client = get_gdrive_client()
        file = client.upload_file(
            file_path=file_path,
            parent_id=parent_id,
            name=name
        )
        
        if not file:
            return json.dumps({
                "success": False,
                "error": "Failed to upload file",
                "file_path": file_path,
                "parent_id": parent_id
            }, indent=2, ensure_ascii=False)
        
        result = {
            "success": True,
            "message": f"File '{file.name}' uploaded successfully",
            "file": _file_to_dict(file)
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "file_path": file_path,
            "parent_id": parent_id
        }, indent=2, ensure_ascii=False)


async def gdrive_download_file(
    ctx: Context,
    file_id: str,
    destination_path: str
) -> str:
    """
    Download a file from Google Drive.
    
    Args:
        file_id: File ID to download
        destination_path: Local path where file will be saved
    
    Returns:
        JSON string with download result
    """
    try:
        client = get_gdrive_client()
        success = client.download_file(
            file_id=file_id,
            destination_path=destination_path
        )
        
        if success:
            result = {
                "success": True,
                "message": f"File downloaded successfully to '{destination_path}'",
                "file_id": file_id,
                "destination_path": destination_path
            }
        else:
            result = {
                "success": False,
                "error": "Failed to download file",
                "file_id": file_id,
                "destination_path": destination_path
            }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "file_id": file_id,
            "destination_path": destination_path
        }, indent=2, ensure_ascii=False)


async def gdrive_delete_file(
    ctx: Context,
    file_id: str,
    permanently: bool = False
) -> str:
    """
    Delete a file or folder from Google Drive.
    
    Args:
        file_id: File or folder ID to delete
        permanently: If True, permanently delete (bypass trash). Use with caution!
    
    Returns:
        JSON string with deletion result
    """
    try:
        client = get_gdrive_client()
        
        # Get file info before deletion for confirmation message
        file_info = client.get_file_info(file_id)
        file_name = file_info.name if file_info else "Unknown"
        
        success = client.delete_file(file_id, permanently=permanently)
        
        if success:
            action = "permanently deleted" if permanently else "moved to trash"
            result = {
                "success": True,
                "message": f"'{file_name}' {action} successfully",
                "file_id": file_id,
                "file_name": file_name,
                "permanently_deleted": permanently
            }
        else:
            result = {
                "success": False,
                "error": "Failed to delete file",
                "file_id": file_id,
                "file_name": file_name
            }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "file_id": file_id
        }, indent=2, ensure_ascii=False)
