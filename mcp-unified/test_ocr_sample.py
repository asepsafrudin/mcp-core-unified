#!/usr/bin/env python3
"""
Test script untuk OCR service PaddleOCR 3.x menggunakan sample file gambar.
"""
import sys
import os
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("PYTHONPATH", str(project_root))

from services.ocr.service import OCREngine
from services.ocr.tools import register_tools
from execution.registry import registry

# Test configuration
SAMPLE_IMAGE = "/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/arsip20260402_08370635.png"
OUTPUT_DIR = "/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan"


async def main():
    print("=" * 60)
    print("OCR Service Test - Sample Image (PaddleOCR 3.x)")
    print("=" * 60)

    # Verify sample image exists
    if not os.path.exists(SAMPLE_IMAGE):
        print(f"ERROR: Sample image not found: {SAMPLE_IMAGE}")
        sys.exit(1)

    print(f"Sample image: {SAMPLE_IMAGE}")
    print(f"Image size: {os.path.getsize(SAMPLE_IMAGE) / 1024:.1f} KB")

    # Register OCR tools
    print("\n[1] Registering OCR tools...")
    register_tools(server=None)
    tools = registry.list_tools()
    print(f"    Registered tools: {[t['name'] for t in tools]}")

    # Initialize OCR engine
    print("\n[2] Initializing OCR engine...")
    engine = OCREngine.get_instance()

    # Test 1: OCR text extraction (using predict() API)
    print("\n[3] Testing ocr/extract_text (PP-OCRv5)...")
    print("    Running PaddleOCR predict() (this may take a moment)...")

    try:
        ocr_result = engine.run_ocr(SAMPLE_IMAGE)
        full_text = ocr_result.get("full_text", "")
        lines = ocr_result.get("lines", [])

        print(f"    Extracted {len(lines)} text lines")
        print(f"    Full text length: {len(full_text)} characters")
        print("\n    Preview (first 200 chars):")
        print("    " + "-" * 56)
        print(f"    {full_text[:200]}")
        print("    " + "-" * 56)
    except Exception as e:
        print(f"    ERROR in OCR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Test 2: Tool registry execution
    print("\n[4] Testing tool registry execution...")
    try:
        result = await registry.execute("ocr/extract_text", {"image_path": SAMPLE_IMAGE})
        print(f"    Tool execution successful, text length: {len(result.get('full_text', ''))}")
    except Exception as e:
        print(f"    ERROR in tool execution: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Document structure parsing (may be slow)
    print("\n[5] Testing ocr/parse_document (PP-StructureV3)...")
    print("    Running PP-StructureV3 (this may take a moment)...")
    structure_result = None
    try:
        structure_result = engine.run_structure(SAMPLE_IMAGE)
        print(f"    Structure result length: {len(str(structure_result))} characters")
        print("\n    Preview (first 200 chars):")
        print("    " + "-" * 56)
        print(f"    {str(structure_result)[:200]}")
        print("    " + "-" * 56)
    except Exception as e:
        print(f"    ERROR in structure parsing: {e}")
        import traceback
        traceback.print_exc()
        # Continue with OCR-only output

    # Generate markdown output
    print("\n[6] Generating markdown output...")
    output_file = os.path.join(OUTPUT_DIR, "arsip20260402_08370635.md")

    md_content = f"# OCR Extraction Result\n\n"
    md_content += f"**Source File:** `arsip20260402_08370635.png`\n"
    md_content += f"**Image Size:** {os.path.getsize(SAMPLE_IMAGE) / 1024:.1f} KB\n"
    md_content += f"**Extracted Lines:** {len(lines)}\n\n"
    md_content += f"---\n\n"
    md_content += f"## Extracted Text\n\n"
    md_content += f"```text\n{full_text}\n```\n\n"
    md_content += f"---\n\n"
    md_content += f"## Detailed Lines\n\n"
    md_content += f"| Line | Text | Score | Bbox |\n"
    md_content += f"|------|------|-------|------|\n"
    for i, line in enumerate(lines, 1):
        text = line.get('text', '')[:50].replace('|', '\\|')
        score = line.get('score', 0)
        bbox = line.get('bbox', [])
        bbox_str = str(bbox[:4]) if len(bbox) > 4 else str(bbox)
        md_content += f"| {i} | {text} | {score:.4f} | {bbox_str} |\n"
    if structure_result:
        md_content += f"\n---\n\n"
        md_content += f"## Document Structure (PP-StructureV3)\n\n"
        md_content += f"{structure_result}\n"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"    Markdown saved to: {output_file}")

    print("\n" + "=" * 60)
    print("OCR Service Test - COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
