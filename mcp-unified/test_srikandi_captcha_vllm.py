#!/usr/bin/env python3
"""
Workflow Test: VLLM RunPod CAPTCHA Reading from SRIKANDI Login Page

This script:
1. Navigates to https://srikandi.arsip.go.id/auth/login
2. Takes a screenshot of the page and CAPTCHA canvas
3. Sends the CAPTCHA image to RunPod VLLM Vision (Qwen2.5-VL)
4. Displays the extracted text
5. Optionally attempts to fill the captcha and submit
"""

import asyncio
import base64
import json
import logging
import os
import sys
import traceback
from datetime import datetime

# Add the repo root to path
sys.path.insert(0, "/home/aseps/MCP")

from playwright.async_api import async_playwright
from integrations.runpod.vllm_vision import VLLMVisionProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("srikandi_captcha_vllm_test")


async def capture_captcha_from_srikandi():
    """
    Navigate to SRIKANDI login page, extract CAPTCHA canvas as base64,
    and save a screenshot for debugging.
    Returns (b64_data, screenshot_path).
    """
    url = "https://srikandi.arsip.go.id/auth/login"
    logger.info(f"Navigating to: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900}
        )
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            logger.info("Successfully loaded login page")
            
            # Wait for CAPTCHA canvas to be present
            await page.wait_for_timeout(3000)  # Give time for canvas to render
            
            # Check for canvas element
            canvas_count = await page.locator("canvas").count()
            logger.info(f"Found {canvas_count} canvas element(s) on page")
            
            # Extract CAPTCHA from canvas
            b64_data = await page.evaluate('''() => {
                const canvas = document.querySelector('canvas');
                return canvas ? canvas.toDataURL('image/png').split(',')[1] : null;
            }''')
            
            if not b64_data:
                logger.warning("No canvas found. Trying to find CAPTCHA image or iframe...")
                # Try alternative: look for img with captcha in src
                captcha_img = await page.locator('img[src*="captcha"], img[src*="Captcha"], img[src*="captcha.png"]').first
                if await captcha_img.count() > 0:
                    src = await captcha_img.get_attribute("src")
                    logger.info(f"Found CAPTCHA image: {src}")
                    # Screenshot the image area
                else:
                    logger.error("No CAPTCHA element found on page!")
            
            # Take full screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_dir = "/home/aseps/MCP/storage/raw_documents/processed/srikandi_tests"
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_path = os.path.join(screenshot_dir, f"srikandi_login_{timestamp}.png")
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Full page screenshot saved: {screenshot_path}")
            
            # Screenshot just the CAPTCHA area if found
            captcha_locator = page.locator("canvas")
            if await captcha_locator.count() > 0:
                captcha_screenshot_path = os.path.join(screenshot_dir, f"captcha_{timestamp}.png")
                await captcha_locator.screenshot(path=captcha_screenshot_path)
                logger.info(f"Captcha screenshot saved: {captcha_screenshot_path}")
            
            await browser.close()
            return b64_data, screenshot_path
            
        except Exception as e:
            logger.error(f"Error during navigation: {e}")
            await browser.close()
            return None, None


async def test_vllm_captcha_reading(b64_data: str):
    """
    Send CAPTCHA image to VLLM RunPod Vision processor and get extracted text.
    """
    if not b64_data:
        logger.error("No base64 data provided for VLLM processing")
        return None
    
    logger.info("="*60)
    logger.info("Sending CAPTCHA to RunPod VLLM Vision (Qwen2.5-VL)...")
    logger.info("="*60)
    
    processor = VLLMVisionProcessor()
    logger.info(f"VLLM Endpoint ID: {processor.endpoint_id}")
    logger.info(f"VLLM Model: {processor.model_name}")
    
    captcha_prompt = (
        "Ekstrak HANYA teks CAPTCHA dari gambar ini. "
        "Jawab dengan HANYA karakter CAPTCHA yang terlihat, "
        "tanpa spasi, tanpa penjelasan tambahan."
    )
    
    try:
        result = await processor._call_vllm_vision(
            image_base64=b64_data,
            custom_prompt=captcha_prompt,
            timeout=120
        )
        
        logger.info("="*60)
        logger.info("VLLM Vision RESULT:")
        logger.info("="*60)
        print(f"\n  Raw VLLM Output: {result}\n")
        
        # Clean the result - remove non-alphanumeric
        import re
        cleaned = re.sub(r'[^a-zA-Z0-9]', '', result.strip())
        logger.info(f"Cleaned CAPTCHA text: '{cleaned}'")
        logger.info("="*60)
        
        return result, cleaned
        
    except Exception as e:
        logger.error(f"VLLM Vision processing failed: {e}")
        logger.error(traceback.format_exc())
        return None, None


async def main():
    """Main test workflow."""
    logger.info("="*60)
    logger.info("SRIKANDI CAPTCHA - VLLM RunPod Vision Test")
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info("="*60)
    
    # Step 1: Capture CAPTCHA from SRIKANDI login page
    logger.info("\n[STEP 1] Capturing CAPTCHA from SRIKANDI login page...")
    b64_data, screenshot_path = await capture_captcha_from_srikandi()
    
    if b64_data:
        logger.info(f"✅ CAPTCHA canvas extracted successfully (b64 length: {len(b64_data)})")
        
        # Step 2: Test VLLM Vision processing
        logger.info("\n[STEP 2] Testing VLLM Vision processing...")
        raw_result, cleaned_result = await test_vllm_captcha_reading(b64_data)
        
        if raw_result:
            logger.info("✅ VLLM Vision processing completed!")
            logger.info(f"   Raw result: {raw_result}")
            logger.info(f"   Cleaned result: '{cleaned_result}'")
        else:
            logger.warning("❌ VLLM Vision processing failed or returned empty result")
    else:
        logger.warning("❌ No CAPTCHA canvas found on the page")
        logger.info("The page may have changed layout or CAPTCHA may render differently")
        logger.info(f"Check screenshot at: {screenshot_path}")
    
    # Step 3: Save test results
    results = {
        "timestamp": datetime.now().isoformat(),
        "screenshot_path": screenshot_path,
        "captcha_b64_available": b64_data is not None,
        "captcha_b64_length": len(b64_data) if b64_data else 0,
        "vllm_raw_result": raw_result if 'raw_result' in dir() else None,
        "vllm_cleaned_result": cleaned_result if 'cleaned_result' in dir() else None,
        "success": b64_data is not None and raw_result is not None
    }
    
    results_dir = "/home/aseps/MCP/storage/raw_documents/processed/srikandi_tests"
    os.makedirs(results_dir, exist_ok=True)
    results_file = os.path.join(results_dir, f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nTest results saved to: {results_file}")
    
    logger.info("\n" + "="*60)
    logger.info("TEST COMPLETE")
    logger.info("="*60)
    
    return results


if __name__ == "__main__":
    results = asyncio.run(main())
    print(f"\n\nFinal Result: {'✅ SUCCESS' if results.get('success') else '❌ NEEDS ATTENTION'}")
    print(f"Screenshot: {results.get('screenshot_path', 'N/A')}")
    print(f"VLLM Output: {results.get('vllm_cleaned_result', 'N/A')}")