import os
import sys
import json
from pathlib import Path
import google.generativeai as genai

sys.path.insert(0, "/home/aseps/MCP/core/mcp-unified")
try:
    from core.secrets import load_runtime_secrets
    load_runtime_secrets()
except Exception as e:
    print(f"Warning: {e}")

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("No GEMINI_API_KEY found")
    sys.exit(1)

genai.configure(api_key=api_key)

# We will use gemini-1.5-pro for vision tasks
model = genai.GenerativeModel('gemini-flash-latest')

def verify_item(page_file, bidang_name, sub_name, auth, field, current_text):
    print(f"Verifying {bidang_name} - {sub_name} - {auth} - {field}")
    try:
        sample_file = genai.upload_file(path=str(page_file), display_name=page_file.name)
        
        prompt = f"""
I am digitizing an Indonesian law annex (Lampiran UU 23 Tahun 2014) which is a table distributing authority across Pusat, Provinsi, and Kabupaten/Kota.
I have a suspicious parsed text that seems to be cut off at the page boundary.
Here is the parsed text I have: "{current_text}"

This text belongs to:
Bidang: {bidang_name}
Sub-urusan: {sub_name}
Authority Column: {auth}

Please look at the attached image (which contains the relevant section of the table). Find this exact text in the table. 
Because it is cut off, please provide the **COMPLETE** and **CORRECT** sentence as it appears in the table. 
Only output the corrected text block, nothing else. Make sure to end the sentence with a period or semicolon as it appears in the image.
        """
        response = model.generate_content([sample_file, prompt])
        print("RESULT:")
        print(response.text.strip())
        print("-" * 40)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test Item 1: Bidang C (Pekerjaan Umum), page 317
    img_dir = Path("/home/aseps/.gemini/antigravity-ide/brain/58fbbbe1-6617-498e-b870-663590db1356/verification_pages")
    page_317 = img_dir / "page_317.png"
    if page_317.exists():
        verify_item(
            page_317, 
            "PEKERJAAN UMUM", 
            "Sumber Daya Air (SDA)", 
            "pemerintah_pusat", 
            "butir 1", 
            "Pengembangan dan pengelolaan sistem irigasi primer dan sekunder pada daerah irigasi yang luasnya lebih dari 3000 ha, daerah irigasi lintas Daerah provinsi, daerah irigasi lintas negara, dan daerah irigasi strategis"
        )
    else:
        print("Page 317 not found")
