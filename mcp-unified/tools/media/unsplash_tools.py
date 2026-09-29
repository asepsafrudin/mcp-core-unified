import os
import time
import requests
from dotenv import load_dotenv
from scripts.load_env import load_env

# Basic in-memory cache to prevent exhausting the 50 req/hr limit during agent loops
_SEARCH_CACHE = {}

def get_unsplash_key() -> str:
    """Retrieve the Unsplash access key from .env"""
    load_env()
    key = os.getenv("UNSPLASH_ACCES_KEY")
    if not key:
        raise ValueError("UNSPLASH_ACCES_KEY is not set in .env")
    return key

def search_unsplash_image(query: str, orientation: str = "landscape", per_page: int = 1) -> dict:
    """
    Search for an image on Unsplash using the developer API.
    Returns a dictionary containing image metadata (url, ID, download_location, etc).
    Includes a basic cache to protect the 50 req/hr free tier limit.
    """
    global _SEARCH_CACHE
    
    cache_key = f"{query}_{orientation}_{per_page}"
    if cache_key in _SEARCH_CACHE:
        return _SEARCH_CACHE[cache_key]

    access_key = get_unsplash_key()
    url = "https://api.unsplash.com/search/photos"
    headers = {
        "Authorization": f"Client-ID {access_key}"
    }
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": per_page
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Unsplash API Error ({response.status_code}): {response.text}")
        
    data = response.json()
    
    if not data.get("results"):
        return {"error": "No images found for this query."}
        
    best_result = data["results"][0]
    result_data = {
        "id": best_result.get("id"),
        "description": best_result.get("description", best_result.get("alt_description", "Unsplash Image")),
        "url_regular": best_result["urls"]["regular"],
        "url_full": best_result["urls"]["full"],
        "download_location": best_result["links"]["download_location"],
        "author_name": best_result["user"]["name"],
        "author_link": best_result["user"]["links"]["html"]
    }
    
    # Store in cache
    _SEARCH_CACHE[cache_key] = result_data
    
    return result_data

def download_unsplash_image(image_metadata: dict, output_dir: str = "/home/aseps/MCP/scratch") -> str:
    """
    Downloads the physical image file and correctly triggers the Unsplash download_location
    endpoint to comply with their API guidelines.
    Returns the absolute path to the downloaded image.
    """
    access_key = get_unsplash_key()
    headers = {
        "Authorization": f"Client-ID {access_key}"
    }
    
    # 1. Trigger the download_location endpoint (Mandatory for API guidelines)
    download_loc_url = image_metadata.get("download_location")
    if not download_loc_url:
        raise ValueError("Missing 'download_location' in image metadata.")
        
    dl_trigger_resp = requests.get(download_loc_url, headers=headers)
    if dl_trigger_resp.status_code != 200:
        print(f"Warning: Failed to trigger Unsplash download endpoint: {dl_trigger_resp.status_code}")
    else:
        # The download_location endpoint usually returns a json with 'url' that points to the actual file
        dl_data = dl_trigger_resp.json()
        download_url = dl_data.get("url")
    
    # If the endpoint didn't provide a URL, fallback to the regular URL
    if not locals().get("download_url"):
        download_url = image_metadata.get("url_full", image_metadata.get("url_regular"))
        
    # 2. Download the physical file
    img_resp = requests.get(download_url, stream=True)
    if img_resp.status_code != 200:
        raise Exception(f"Failed to download image file: {img_resp.status_code}")
        
    os.makedirs(output_dir, exist_ok=True)
    safe_name = f"unsplash_{image_metadata.get('id')}_{int(time.time())}.jpg"
    file_path = os.path.join(output_dir, safe_name)
    
    with open(file_path, "wb") as f:
        for chunk in img_resp.iter_content(chunk_size=8192):
            f.write(chunk)
            
    return file_path
