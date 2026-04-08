import sys
import os
import re
from pathlib import Path

# Setup path
project_root = Path("/home/aseps/MCP/mcp-unified")
sys.path.insert(0, str(project_root))
os.environ.setdefault("PYTHONPATH", str(project_root))

from services.ocr.service import OCREngine
from services.ocr.context_refiner import get_context_refiner

def refine_layout_with_llm(raw_text):
    refiner = get_context_refiner()
    prompt = f"""
Tugas: Rekonstruksi teks OCR menjadi format dokumen resmi pemerintahan Indonesia (Markdown) yang UTUH.
ATURAN:
1. JANGAN SERTAKAN tag <think> atau penjelasan. Langsung berikan konten Markdown.
2. Gabungkan kata-kata terpisah menjadi kalimat utuh.
3. Sajikan perincian dalam format tabel Markdown.
4. Koreksi typo: "I11" -> "III", "8H" -> "SH", "DITJFN" -> "DITJEN".
5. PASTIKAN SELURUH DOKUMEN TERULIS SAMPAI AKHIR (TANDA TANGAN/TANGGAL).

Teks OCR:
\"\"\"
{raw_text}
\"\"\"
"""
    try:
        refined = refiner._call_llm(prompt)
        if refined:
            refined = re.sub(r"<think>.*?</think>", "", refined, flags=re.DOTALL).strip()
            refined = re.sub(r"```markdown|```", "", refined).strip()
            return refined
    except Exception as e:
        print(f"Error LLM: {e}")
    return raw_text

def run_fix():
    base_path = Path("/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/")
    files = sorted(list(base_path.glob("*.png")))
    engine = OCREngine.get_instance()
    
    for img_path in files:
        filename = img_path.name
        print(f"Processing (Full-token): {filename}...")
        result = engine.run_ocr(str(img_path), mode="standard")
        raw_text = result.get("full_text", "")
        confidence = result.get("nlp_quality", {}).get("avg_confidence", 0.0)
        
        refined_text = refine_layout_with_llm(raw_text)
        
        md_content = f"# OCR Extraction Result (Refined)\n\n**Source File:** `{filename}`\n**Extraction Date:** 2026-04-06\n**Engine:** Google Cloud Vision + LLM Refinement (Full)\n**Confidence Score:** {confidence}\n\n---\n\n## Document Content\n\n{refined_text}\n"
        
        md_path = base_path / filename.replace(".png", ".md")
        with open(md_path, "w") as f:
            f.write(md_content)
        print(f"✅ Saved: {md_path.name}")

if __name__ == "__main__":
    run_fix()
