import sys
import os
import json
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
    # Prompt lebih ketat tanpa pemikiran
    prompt = f"""
Tugas: Rekonstruksi teks OCR menjadi format dokumen resmi pemerintahan Indonesia (Markdown) yang UTUH.
ATURAN KERAS:
1. JANGAN SERTAKAN tag <think> atau penjelasan apapun. Langsung berikan konten Markdown.
2. Gabungkan kata-kata terpisah menjadi kalimat utuh.
3. Sajikan perincian dalam format tabel Markdown (| Header |).
4. Koreksi typo: "I11" -> "III", "8H" -> "SH", "DITJFN" -> "DITJEN".
5. PASTIKAN SELURUH DOKUMEN TERULIS, TERMASUK TANDA TANGAN (JAKARTA, ...) DI BAGIAN AKHIR.

Teks OCR:
\"\"\"
{raw_text}
\"\"\"
"""
    try:
        refined = refiner._call_llm(prompt)
        if refined:
            # Cleanup tag <think> jika masih ada bocor dari model
            refined = re.sub(r"<think>.*?</think>", "", refined, flags=re.DOTALL).strip()
            # Hapus markdown code blocks
            refined = re.sub(r"```markdown|```", "", refined).strip()
            return refined
    except Exception as e:
        print(f"Error LLM: {e}")
    return raw_text

def run_fix():
    files = ["arsip20260402_08404789.png", "arsip20260402_08494294.png", "arsip20260402_08540119.png", "arsip20260402_08552548.png"]
    base_path = Path("/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/")
    engine = OCREngine.get_instance()
    
    for filename in files:
        print(f"Reprocessing incomplete file: {filename}...")
        img_path = base_path / filename
        if not img_path.exists():
            continue
            
        result = engine.run_ocr(str(img_path), mode="standard")
        raw_text = result.get("full_text", "")
        confidence = result.get("nlp_quality", {}).get("avg_confidence", 0.0)
        
        refined_text = refine_layout_with_llm(raw_text)
        
        md_content = [
            "# OCR Extraction Result (Refined)",
            "",
            f"**Source File:** `{filename}`",
            "**Extraction Date:** 2026-04-06",
            "**Engine:** Google Cloud Vision + LLM Refinement (Fixed)",
            f"**Confidence Score:** {confidence}",
            "",
            "---",
            "",
            "## Document Content",
            "",
            refined_text,
            ""
        ]
        
        md_path = base_path / filename.replace(".png", ".md")
        with open(md_path, "w") as f:
            f.write("\n".join(md_content))
        print(f"✅ Fixed and Saved: {md_path.name}")

if __name__ == "__main__":
    run_fix()
