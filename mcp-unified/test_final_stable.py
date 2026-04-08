#!/usr/bin/env python3
import sys
import os
import json
from pathlib import Path

# Setup Path Proyek
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.ocr.service import OCREngine

def main():
    img = '/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/arsip20260402_08370635.png'
    print(f"--- MEMULAI PENGUJIAN FINAL (PADDLE + LLM REFINER) ---")
    print(f"Target: {os.path.basename(img)}")
    
    try:
        engine = OCREngine.get_instance()
        result = engine.run_ocr(img)
        
        if result.get("status") == "error":
            print(f"✘ GAGAL: {result.get('message')}")
            return

        doc_type = result.get("document_type", "Tidak Diketahui")
        refined = result.get("refined_data", {})
        full_text = result.get("full_text", "")

        print(f"✔ Ekstraksi Berhasil! Jenis Dokumen: {doc_type}\n")
        print(f"--- SUBSTANSI DATA (REFINED) ---")
        
        if refined:
            satker = refined.get("satuan_kerja", {}).get("nama", "-")
            print(f"SATKER: {satker}")
            print(f"NOMOR: {refined.get('nomor', '-')}")
            
            print("\nDAFTAR RINCIAN PEMBAYARAN:")
            print("-" * 60)
            rincian = refined.get("rincian_pembayaran", [])
            for item in rincian:
                no = item.get("no", "-")
                akun = item.get("akun", "-")
                penerima = item.get("penerima", "-")
                uraian = item.get("uraian", "-")
                jumlah = item.get("jumlah_rp", 0)
                print(f"[{no}] {akun} | {penerima} | {uraian} | Rp {jumlah:,}")
            
            print("-" * 60)
            print(f"TOTAL: Rp {refined.get('total_jumlah_rp', 0):,}")
            
            if refined.get("keterangan"):
                print(f"\nNOTE: {refined.get('keterangan')}")
        else:
            print("⚠️ Data semantik kosong. Teks mentah:")
            print("-" * 60)
            print(full_text[:500] + "...")
            
    except Exception as e:
        print(f"✘ CRITICAL ERROR: {str(e)}")

if __name__ == "__main__":
    main()
