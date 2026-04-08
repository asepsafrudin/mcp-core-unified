import sys
import os
import json
import re
import time
from pathlib import Path

# Setup path to include mcp-unified
project_root = Path("/home/aseps/MCP/mcp-unified")
sys.path.insert(0, str(project_root))
os.environ.setdefault("PYTHONPATH", str(project_root))

from services.ocr.service import OCREngine
from services.ocr.context_refiner import get_context_refiner

def refine_layout_with_llm(raw_text):
    """Gunakan LLM untuk merapikan layout dokumen dari teks mentah OCR."""
    refiner = get_context_refiner()
    if not refiner.enabled:
        return raw_text
        
    prompt = f"""
Tugas: Rekonstruksi teks OCR berikut menjadi format dokumen resmi pemerintahan Indonesia yang CLEAN dalam Markdown.
Aturan:
1. Gabungkan kata-kata yang terpisah barisnya menjadi kalimat yang utuh.
2. Jika ada data tabel, sajikan dalam format tabel Markdown (| Header |).
3. Pertahankan substansi data (Nomor, Nama, Tanggal, Angka) 100%.
4. Lakukan koreksi otomatis: "I11" -> "III", "8H" -> "SH", "DITJFN" -> "DITJEN".
5. PENTING: JANGAN sertakan tag <think> atau penjelasan apapun. Langsung ke konten Markdown.

Teks OCR Mentah:
\"\"\"
{raw_text}
\"\"\"
"""
    try:
        refined = refiner._call_llm(prompt)
        if refined:
            # Cleanup: Hapus tag <think>...</think> jika masih muncul
            refined = re.sub(r'<think>.*?</think>', '', refined, flags=re.DOTALL).strip()
            # Cleanup: Hapus markdown code block tags
            refined = re.sub(r'```markdown|```', '', refined).strip()
            return refined
    except Exception as e:
        print(f"Gagal merapikan layout: {e}")
    return raw_text

def get_pending_files():
    base_path = Path("/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/")
    all_pngs = sorted(list(base_path.glob("*.png")))
    pending = []
    for png in all_pngs:
        md_file = png.with_suffix(".md")
        # Kita proses ulang semua PNG agar konsisten (tanpa tag <think>)
        pending.append(png.name)
    return pending

def process_batch(file_names):
    base_path = Path("/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/")
    engine = OCREngine.get_instance()
    
    for filename in file_names:
        img_path = base_path / filename
        print(f"⏳ Memproses: {filename} (OCR + Refinement)...")
        try:
            # 1. OCR
            result = engine.run_ocr(str(img_path), mode="standard")
            raw_text = result.get("full_text", "")
            confidence = result.get("nlp_quality", {}).get("avg_confidence", 0.0)
            
            # 2. Refinement
            refined_text = refine_layout_with_llm(raw_text)
            
            # 3. Save
            md_content = [
                "# OCR Extraction Result (Refined)",
                "",
                f"**Source File:** `{filename}`",
                "**Extraction Date:** 2026-04-06",
                "**Engine:** Google Cloud Vision + LLM Refinement",
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
            print(f"✅ Selesai: {md_path.name}")
            # Berikan sedikit jeda untuk API rate limiting jika perlu
            time.sleep(1)
        except Exception as e:
            print(f"❌ Error {filename}: {e}")

if __name__ == "__main__":
    pending = get_pending_files()
    print(f"Menemukan {len(pending)} file untuk diproses/perbaiki.")
    process_batch(pending)
