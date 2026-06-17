import os
import sys
import logging
import asyncio

from typing import Dict, Any, List

# Add parent to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from tools.media.canva_tools import create_canva_design, upload_canva_asset
from tools.media.unsplash_tools import search_unsplash_image, download_unsplash_image

logger = logging.getLogger(__name__)

async def create_canva_presentation_pipeline(topic: str, image_queries: List[str] = None) -> Dict[str, Any]:
    """
    Skill orchestration: Orchestrates the creation of a Canva presentation.
    It can search for images, upload them to Canva, and create a design.
    """
    logger.info(f"Starting Canva Presentation Pipeline for topic: {topic}")
    
    result_data = {
        "topic": topic,
        "assets_uploaded": [],
        "design_url": None,
        "errors": []
    }
    
    # Step 1: Search and Download Images from Unsplash
    local_images = []
    if image_queries:
        for query in image_queries:
            try:
                print(f"[Skill] Searching Unsplash for: {query}")
                search_res = search_unsplash_image(query)
                if "error" not in search_res:
                    dl_path = download_unsplash_image(search_res, "/home/aseps/MCP/scratch")
                    local_images.append(dl_path)
                    print(f"[Skill] Downloaded: {dl_path}")
                else:
                    logger.warning(f"Failed to find image for query '{query}': {search_res['error']}")
            except Exception as e:
                err_msg = f"Error fetching image for '{query}': {str(e)}"
                logger.error(err_msg)
                result_data["errors"].append(err_msg)
                
    # Step 2: Upload Images to Canva Assets
    for local_img in local_images:
        try:
            print(f"[Skill] Uploading to Canva: {local_img}")
            asset = upload_canva_asset(local_img)
            result_data["assets_uploaded"].append(asset)
            print(f"[Skill] Upload success! ID: {asset['id']}")
        except Exception as e:
            err_msg = f"Error uploading {local_img} to Canva: {str(e)}"
            logger.error(err_msg)
            result_data["errors"].append(err_msg)
            
    # Step 3: Create Blank Canva Design
    try:
        print(f"[Skill] Creating Canva Presentation: {topic}")
        design = create_canva_design(title=topic, preset_name="presentation")
        result_data["design_url"] = design.get('url') or design.get('urls', {}).get('edit_url')
        print(f"[Skill] Canva Design created at: {result_data['design_url']}")
    except Exception as e:
        err_msg = f"Error creating Canva design: {str(e)}"
        logger.error(err_msg)
        result_data["errors"].append(err_msg)
        
    return result_data
