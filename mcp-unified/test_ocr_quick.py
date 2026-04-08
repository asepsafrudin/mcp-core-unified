#!/usr/bin/env python3
"""
Quick OCR test - generates markdown from extracted text only.
Skips PP-StructureV3 which has missing dependencies.
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("PYTHONPATH", str(project_root))

SAMPLE_IMAGE = "/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/arsip20260402_08370635.png"
OUTPUT_FILE = "/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/arsip20260402_08370635.md"

from services.ocr.service import OCREngine

def main():
    print("=" * 60)
    print("Quick OCR Test - PP-OCRv5 only")
    print("=" * 60)

    if not os.path.exists(SAMPLE_IMAGE):
        print(f"ERROR: Image not found: {SAMPLE_IMAGE}")
        sys.exit(1)

    print(f"Image: {SAMPLE_IMAGE} ({os.path.getsize(SAMPLE_IMAGE) / 1024:.1f} KB)")

    engine = OCREngine.get_instance()
    print("Running OCR (model loading + inference)...")

    result = engine.run_ocr(SAMPLE_IMAGE)
    full_text = result.get("full_text", "")
    lines = result.get("lines", [])

    print(f"\nExtracted {len(lines)} text lines")
    print(f"Full text: {len(full_text)} characters\n")

    # Preview first 5 lines
    for i, line in enumerate(lines[:5]):
        print(f"  [{i}] score={line['score']:.4f} | {line['text'][:60]}")

    # Generate markdown
    print(f"\nWriting markdown to: {OUTPUT_FILE}")

    md = []
    md.append("# OCR Extraction Result\n")
    md.append(f"**Source File:** `arsip20260402_08370635.png`")
    md.append(f"**Image Size:** {os.path.getsize(SAMPLE_IMAGE) / 1024:.1f} KB")
    md.append(f"**Extracted Lines:** {len(lines)}\n")
    md.append("---\n")
    md.append("## Extracted Text\n")
    md.append("```text")
    md.append(full_text)
    md.append("```\n")
    md.append("---\n")
    md.append("## Detailed Lines\n")
    md.append("| Line | Text | Score | Bbox |")
    md.append("|------|------|-------|------|")
    for i, line in enumerate(lines, 1):
        text = line.get("text", "")[:60].replace("|", "\\|")
        score = line.get("score", 0)
        bbox = line.get("bbox", [])
        # Shorten bbox for table readability
        if isinstance(bbox, list) and len(bbox) > 0:
            if isinstance(bbox[0], list):
                bbox_str = str(bbox[0]) + f" ({len(bbox)} pts)"
            else:
                bbox_str = str(bbox)
        else:
            bbox_str = "[]"
        md.append(f"| {i} | {text} | {score:.4f} | {bbox_str} |")

    content = "\n".join(md) + "\n"
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nDone! Output: {OUTPUT_FILE}")
    print(f"File size: {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")

if __name__ == "__main__":
    main()