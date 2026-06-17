import os
import time
import requests
from dotenv import load_dotenv

_PEXELS_CACHE = {}

def get_pexels_key() -> str:
    """Retrieve the Pexels API key from .env"""
    load_dotenv("/home/aseps/MCP/.env")
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        raise ValueError("PEXELS_API_KEY is not set in .env")
    return key

def search_pexels_image(query: str, orientation: str = "landscape", per_page: int = 1) -> dict:
    """
    Search for an image on Pexels API.
    Provides a high-quota fallback for Unsplash (20k req/month).
    """
    global _PEXELS_CACHE
    
    cache_key = f"{query}_{orientation}_{per_page}"
    if cache_key in _PEXELS_CACHE:
        return _PEXELS_CACHE[cache_key]

    api_key = get_pexels_key()
    url = "https://api.pexels.com/v1/search"
    headers = {
        "Authorization": api_key
    }
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": per_page
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Pexels API Error ({response.status_code}): {response.text}")
        
    data = response.json()
    
    if not data.get("photos"):
        return {"error": "No images found on Pexels for this query."}
        
    best_result = data["photos"][0]
    result_data = {
        "id": best_result.get("id"),
        "description": best_result.get("alt", "Pexels Image"),
        "url_regular": best_result["src"]["large"],
        "url_full": best_result["src"]["original"],
        "author_name": best_result.get("photographer"),
        "author_link": best_result.get("photographer_url")
    }
    
    _PEXELS_CACHE[cache_key] = result_data
    return result_data

def download_pexels_image(image_metadata: dict, output_dir: str = "/home/aseps/MCP/scratch") -> str:
    """
    Downloads the physical image file from Pexels.
    """
    download_url = image_metadata.get("url_regular", image_metadata.get("url_full"))
    if not download_url:
        raise ValueError("Missing 'url_regular' in image metadata.")
        
    # Pexels doesn't have a strict download trigger endpoint like Unsplash,
    # but we just download the source URL directly.
    img_resp = requests.get(download_url, stream=True)
    if img_resp.status_code != 200:
        raise Exception(f"Failed to download Pexels image file: {img_resp.status_code}")
        
    os.makedirs(output_dir, exist_ok=True)
    safe_name = f"pexels_{image_metadata.get('id')}_{int(time.time())}.jpg"
    file_path = os.path.join(output_dir, safe_name)
    
    with open(file_path, "wb") as f:
        for chunk in img_resp.iter_content(chunk_size=8192):
            f.write(chunk)
            
    return file_path
