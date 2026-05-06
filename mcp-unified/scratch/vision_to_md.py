import os
import sys
import json
from google.cloud import vision
from google.oauth2 import service_account
from pdf2image import convert_from_path
import tempfile
from pathlib import Path

# Config
SERVICE_ACCOUNT_FILE = "/home/aseps/MCP/config/credentials/google/mcp-gmail-482015-682b788ee191.json"
PDF_PATH = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only.pdf"
OUTPUT_PATH = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only_VISION.md"

def vision_ocr_pdf():
    print(f"Initializing Google Cloud Vision with: {SERVICE_ACCOUNT_FILE}")
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
    client = vision.ImageAnnotatorClient(credentials=credentials)

    print(f"Converting PDF to images: {PDF_PATH}")
    # Convert first 18 pages
    images = convert_from_path(PDF_PATH, dpi=200)
    
    full_md = "# Reviu DIM RUU Kepulauan - Google Cloud Vision OCR\n\n"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, image in enumerate(images):
            page_num = i + 1
            print(f"Processing Page {page_num}/{len(images)}...")
            
            img_path = os.path.join(tmpdir, f"page_{page_num}.jpg")
            image.save(img_path, "JPEG")
            
            with open(img_path, "rb") as image_file:
                content = image_file.read()
            
            img = vision.Image(content=content)
            # Use DOCUMENT_TEXT_DETECTION for better table/document handling
            response = client.document_text_detection(image=img)
            
            if response.error.message:
                print(f"Error on page {page_num}: {response.error.message}")
                continue
            
            # Simple approach: Vision API preserves reading order fairly well
            # For complex tables, we'd need spatial sorting, but document_text_detection 
            # usually outputs columns correctly if they are clear.
            
            page_text = response.full_text_annotation.text
            
            full_md += f"## Page {page_num}\n\n"
            full_md += page_text + "\n\n"
            full_md += "---\n\n"

    print(f"Saving Markdown to {OUTPUT_PATH}")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(full_md)
    print("Done!")

if __name__ == "__main__":
    try:
        vision_ocr_pdf()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)
