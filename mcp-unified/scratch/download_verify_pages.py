"""
Download relevant page images from Google Drive verification folder
for visual verification of the 24 remaining suspicious items.

Based on the page mapping from the annex:
- Annex starts at page 314 of the PDF
- Each bidang occupies several pages
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, "/home/aseps/MCP/core/mcp-unified")

try:
    from core.secrets import load_runtime_secrets
    load_runtime_secrets()
except Exception as e:
    print(f"Warning loading secrets: {e}")

from integrations.gdrive.client import get_gdrive_client

FOLDER_ID = "15Bd9s2Q9jAv1hsEzqS1UYMbKklnO4zys"
OUTPUT_DIR = Path("/home/aseps/.gemini/antigravity-ide/brain/58fbbbe1-6617-498e-b870-663590db1356/verification_pages")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Pages we need based on the suspicious items and their bidang locations:
# Bidang C (Pekerjaan Umum) ~ page 317
# Bidang F (Sosial) ~ page 323-324
# Bidang G (Tenaga Kerja) ~ page 317
# Bidang H (Pemberdayaan Perempuan) ~ page 323
# Bidang N (Pengendalian Penduduk) ~ page 339-340
# Bidang O (Perhubungan) ~ page 346-348
# Bidang R (Penanaman Modal) ~ page 352-354
# Bidang W (Perpustakaan) ~ page 383
# Bidang X (Kearsipan) ~ page 393
# Bidang Y (Kelautan & Perikanan) ~ page 409
# Bidang AA (Pertanian) ~ page 413-418
# Bidang BB (Kehutanan) ~ page 423-424
# Bidang CC (ESDM) ~ page 429-435
# Bidang DD (Perdagangan) ~ page 432-433
# Bidang FF (Transmigrasi) ~ page 435+
NEEDED_PAGES = [
    317, 323, 324, 339, 340, 346, 348, 352, 354, 355,
    358, 359, 361, 367, 369, 372, 381, 383, 393, 409,
    413, 418, 423, 424, 429, 432, 433, 435
]

def main():
    client = get_gdrive_client()
    if not client.connect():
        print("Error: Could not connect to Google Drive API.")
        sys.exit(1)

    print(f"Listing files in verification folder ID: {FOLDER_ID}...")
    files = client.list_files(folder_id=FOLDER_ID)

    if not files:
        print(f"No files found in folder {FOLDER_ID}.")
        sys.exit(0)

    print(f"Total files in folder: {len(files)}")

    # Build a mapping of page number -> file
    page_files = {}
    for f in files:
        # Extract page number from filename like UU_NO_23_THN_2014-_PEMERINTAHAN_DAERAH_page_317.png
        name = f.name
        if '_page_' in name:
            try:
                page_num = int(name.split('_page_')[1].split('.')[0])
                page_files[page_num] = f
            except ValueError:
                pass

    print(f"Found {len(page_files)} page files")
    print(f"Available pages: {sorted(page_files.keys())}")

    # Download only the pages we need and don't already have
    downloaded = 0
    skipped = 0
    for page_num in sorted(NEEDED_PAGES):
        out_path = OUTPUT_DIR / f"page_{page_num}.png"
        if out_path.exists():
            print(f"  Page {page_num}: already exists, skipping")
            skipped += 1
            continue

        if page_num in page_files:
            f = page_files[page_num]
            print(f"  Downloading page {page_num} ({f.name})...")
            success = client.download_file(f.id, str(out_path))
            if success:
                downloaded += 1
                print(f"    -> Saved to {out_path}")
            else:
                print(f"    -> FAILED to download")
        else:
            print(f"  Page {page_num}: NOT FOUND in folder")

    print(f"\nDone: {downloaded} downloaded, {skipped} skipped (already exist)")
    print(f"Output directory: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
