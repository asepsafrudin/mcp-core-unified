#!/usr/bin/env python3
import sys
import os
import asyncio
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("PYTHONPATH", str(project_root))

from services.ocr.service import OCREngine
from execution.registry import registry
from services.ocr.tools import register_tools

# Test configuration
SAMPLE_IMAGE = "/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/arsip20260402_08370635.png"

async def main():
    print("=" * 60)
    print("Google Cloud Vision Pipeline Test")
    print("=" * 60)

    if not os.path.exists(SAMPLE_IMAGE):
        print(f"ERROR: Sample image not found: {SAMPLE_IMAGE}")
        return

    # Check for credentials
    from services.ocr.config import GOOGLE_VISION_CREDENTIALS
    print(f"Using Google Credentials: {GOOGLE_VISION_CREDENTIALS}")
    if not os.path.exists(GOOGLE_VISION_CREDENTIALS):
        print(f"ERROR: Credentials file not found!")
        return

    # Register tools
    register_tools(None)

    # Initialize Engine
    print("\n[1] Initializing OCREngine (Google Vision prioritized)...")
    engine = OCREngine.get_instance()

    # Run OCR
    print("\n[2] Running Google Vision OCR...")
    try:
        result = engine.run_ocr(SAMPLE_IMAGE)
        
        print(f"\nStatus: {result.get('status', 'success')}")
        print(f"Document Type: {result.get('document_type', 'unknown')}")
        print(f"Confidence (NLP Quality): {result.get('nlp_quality', {}).get('quality_score', 0)}")
        
        full_text = result.get('full_text', '')
        print("\nFull Text Excerpt (first 500 chars):")
        print("-" * 40)
        print(full_text[:500])
        print("-" * 40)
        
        if "refined_data" in result:
            print("\nRefined Data (Semantic Analysis):")
            import json
            print(json.dumps(result["refined_data"], indent=2))
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Test COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
