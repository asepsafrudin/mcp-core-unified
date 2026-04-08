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

SAMPLE_IMAGE = "/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/arsip20260402_08370635.png"

async def test_mode(mode_name):
    print(f"\n>>> TESTING MODE: {mode_name.upper()} <<<")
    engine = OCREngine.get_instance()
    try:
        result = engine.run_ocr(SAMPLE_IMAGE, mode=mode_name)
        print(f"Status: {result.get('status', 'success')}")
        print(f"LLM Status: {result.get('llm_status', 'executed')}")
        print(f"Text Length: {len(result.get('full_text', ''))}")
        if "refined_data" in result:
             print(f"Refined Data Keys: {list(result['refined_data'].keys())}")
    except Exception as e:
        print(f"Error in {mode_name}: {e}")

async def main():
    print("=" * 60)
    print("Google Cloud Vision Multi-Mode Test")
    print("=" * 60)

    # Test individual modes
    await test_mode("fast")
    await test_mode("standard")
    await test_mode("deep")
    await test_mode("structured")

    print("\n" + "=" * 60)
    print("Multi-Mode Test COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
