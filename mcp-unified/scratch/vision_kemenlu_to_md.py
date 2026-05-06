import os
import sys
from google.cloud import vision
from google.oauth2 import service_account
from pdf2image import convert_from_path
import tempfile

SERVICE_ACCOUNT_FILE = "/home/aseps/MCP/config/credentials/google/mcp-gmail-482015-682b788ee191.json"
PDF_PATH = "/home/aseps/MCP/storage/office/raw/00015 HI 08 R - SD Pro Kemdagri Reviu DIM RUU DK table only.pdf"
OUTPUT_PATH = "/home/aseps/MCP/storage/office/raw/KEMENLU_REVIU_VISION.md"

def ocr_kemenlu():
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
    client = vision.ImageAnnotatorClient(credentials=credentials)

    print(f"Converting PDF to images (61 pages): {PDF_PATH}")
    images = convert_from_path(PDF_PATH, dpi=150) # Lower DPI to save memory/speed for 61 pages
    
    full_md = "# Reviu DIM RUU Kepulauan - KEMENTERIAN LUAR NEGERI\n\n"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, image in enumerate(images):
            page_num = i + 1
            print(f"Processing Page {page_num}/{len(images)}...")
            
            img_path = os.path.join(tmpdir, f"page_{page_num}.jpg")
            image.save(img_path, "JPEG")
            
            with open(img_path, "rb") as image_file:
                content = image_file.read()
            
            img = vision.Image(content=content)
            response = client.document_text_detection(image=img)
            
            if response.full_text_annotation:
                page_text = response.full_text_annotation.text
                full_md += f"## Page {page_num}\n\n"
                full_md += page_text + "\n\n"
                full_md += "---\n\n"
            
            # Save intermediate result every 10 pages
            if page_num % 10 == 0:
                with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                    f.write(full_md)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(full_md)
    print(f"Done! Saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    ocr_kemenlu()
