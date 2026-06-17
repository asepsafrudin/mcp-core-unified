import os
import json
import time
import requests
import base64
from urllib.parse import urlencode
from dotenv import load_dotenv

TOKEN_PATH = "/home/aseps/MCP/config/credentials/canva/token.json"

def _get_canva_credentials():
    load_dotenv("/home/aseps/MCP/.env")
    client_id = os.getenv("CANVA_CLIENT_ID")
    client_secret = os.getenv("CANVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError("CANVA_CLIENT_ID and CANVA_CLIENT_SECRET must be set in .env")
    return client_id, client_secret

def _refresh_access_token(refresh_token: str) -> dict:
    client_id, client_secret = _get_canva_credentials()
    auth_str = f"{client_id}:{client_secret}"
    b64_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    response = requests.post("https://api.canva.com/rest/v1/oauth/token", headers=headers, data=data)
    if response.status_code == 200:
        new_token = response.json()
        new_token['updated_at'] = time.time()
        with open(TOKEN_PATH, 'w') as f:
            json.dump(new_token, f, indent=4)
        return new_token
    else:
        raise Exception(f"Failed to refresh token: {response.status_code} {response.text}")

def get_canva_token() -> str:
    """Gets the valid access token, refreshing it if necessary."""
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(f"Canva token file not found at {TOKEN_PATH}. Please run authentication first.")
        
    with open(TOKEN_PATH, 'r') as f:
        token_data = json.load(f)
        
    updated_at = token_data.get('updated_at', 0)
    expires_in = token_data.get('expires_in', 14400)
    
    # If the token was generated more than (expires_in - 5 minutes) ago, refresh it
    if time.time() - updated_at > (expires_in - 300):
        print("[Canva API] Refreshing Access Token...")
        token_data = _refresh_access_token(token_data['refresh_token'])
        
    return token_data['access_token']

def upload_canva_asset(file_path: str, name: str = None) -> dict:
    """
    Uploads a local image file to Canva Assets.
    Returns a dictionary with the asset ID and URL.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    access_token = get_canva_token()
    
    if not name:
        name = os.path.basename(file_path)
        
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    # Step 1: Create asset upload job
    # Canva Asset upload is typically a multipart/form-data upload or binary upload depending on the endpoint version.
    # Canva Connect API uses /v1/asset-uploads
    with open(file_path, "rb") as f:
        file_data = f.read()
        
    print(f"[Canva API] Uploading {name} to Canva Assets...")
    
    # Canva asset upload requires Asset-Upload-Metadata header
    metadata = {
        "name_base64": base64.b64encode(name.encode('utf-8')).decode('utf-8')
    }
    headers['Asset-Upload-Metadata'] = json.dumps(metadata)
    headers['Content-Type'] = "application/octet-stream"
    
    response = requests.post(
        "https://api.canva.com/rest/v1/asset-uploads",
        headers=headers,
        data=file_data
    )
    
    if response.status_code == 200:
        job = response.json()
        job_id = job['job']['id']
        
        # Step 2: Poll for completion
        while True:
            poll_resp = requests.get(
                f"https://api.canva.com/rest/v1/asset-uploads/{job_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            poll_data = poll_resp.json()
            status = poll_data['job']['status']
            if status == "success":
                asset = poll_data['job']['asset']
                print(f"[Canva API] Asset uploaded successfully. Asset ID: {asset['id']}")
                return asset
            elif status == "failed":
                raise Exception(f"Asset upload failed: {poll_data}")
            time.sleep(2)
    else:
        raise Exception(f"Failed to initiate asset upload: {response.status_code} {response.text}")

def create_canva_design(title: str, preset_name: str = "presentation") -> dict:
    """
    Creates a new empty design in Canva.
    Returns the design URL which the user can open to edit.
    """
    access_token = get_canva_token()
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "design_type": {
            "type": "preset",
            "name": preset_name
        },
        "title": title
    }
    
    print(f"[Canva API] Creating new design: {title}...")
    response = requests.post(
        "https://api.canva.com/rest/v1/designs",
        headers=headers,
        json=data
    )
    
    if response.status_code == 200:
        design = response.json()
        print(f"[Canva API] Design created successfully!")
        return design['design']
    else:
        raise Exception(f"Failed to create design: {response.status_code} {response.text}")

def get_design_edit_url(design_id: str) -> dict:
    """
    Gets a fresh edit URL for an existing Canva design.
    This is useful when the previous edit URL has expired (they have a ~30 day TTL).
    
    Returns a dictionary with 'edit_url' and 'view_url'.
    """
    access_token = get_canva_token()
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    print(f"[Canva API] Fetching design info for: {design_id}...")
    response = requests.get(
        f"https://api.canva.com/rest/v1/designs/{design_id}",
        headers=headers,
        timeout=15
    )
    
    if response.status_code == 200:
        design = response.json()['design']
        urls = design.get('urls', {})
        print(f"[Canva API] Fresh URLs retrieved successfully!")
        return {
            "id": design['id'],
            "title": design.get('title', ''),
            "edit_url": urls.get('edit_url'),
            "view_url": urls.get('view_url'),
        }
    else:
        raise Exception(f"Failed to get design: {response.status_code} {response.text}")

def list_canva_designs(limit: int = 10) -> list:
    """
    Lists recent designs from the user's Canva account.
    Returns a list of design metadata.
    """
    access_token = get_canva_token()
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    print(f"[Canva API] Listing recent designs...")
    response = requests.get(
        f"https://api.canva.com/rest/v1/designs",
        headers=headers,
        params={"query": "", "ownership": "owned"},
        timeout=15
    )
    
    if response.status_code == 200:
        data = response.json()
        items = data.get('items', [])[:limit]
        print(f"[Canva API] Found {len(items)} designs.")
        return items
    else:
        raise Exception(f"Failed to list designs: {response.status_code} {response.text}")

