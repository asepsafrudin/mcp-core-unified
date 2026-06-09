import os
import glob
import subprocess
from pathlib import Path

img_dir = Path("/home/aseps/.gemini/antigravity-ide/brain/58fbbbe1-6617-498e-b870-663590db1356/verification_pages")
out_dir = Path("/home/aseps/MCP/core/mcp-unified/scratch/ocr_pages")
out_dir.mkdir(parents=True, exist_ok=True)

print(f"Running Tesseract on images in {img_dir}...")
images = list(img_dir.glob("*.png"))

for img in sorted(images):
    out_file = out_dir / f"{img.stem}"
    # tesseract appends .txt automatically
    cmd = ["tesseract", str(img), str(out_file), "-l", "ind"]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"Processed {img.name}")
    except subprocess.CalledProcessError as e:
        print(f"Error processing {img.name}: {e.stderr.decode()}")
        
print("Done extracting text from images.")
