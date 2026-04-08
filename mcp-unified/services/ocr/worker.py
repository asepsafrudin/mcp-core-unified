# services/ocr/worker.py
import sys
import json
import os
import argparse
from pathlib import Path

# Memasukkan folder proyek ke sys.path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def main():
    parser = argparse.ArgumentParser(description="OCR/Structure Background Worker (Stable 3.11)")
    parser.add_argument("--image", required=True, help="Path ke file")
    parser.add_argument("--mode", choices=["ocr", "structure"], default="ocr", help="Mode operasi")
    parser.add_argument("--json", action="store_true", help="Output via JSON")
    args = parser.parse_args()

    try:
        from services.ocr.service import OCREngine
        engine = OCREngine.get_instance()
        
        if args.mode == "ocr":
            # Panggil logika eksekusi internal
            result = engine._execute_ocr_logic(args.image)
            print(json.dumps(result))
        elif args.mode == "structure":
            result = engine._execute_structure_logic(args.image)
            # Karena structure mengembalikan string (markdown), kita bungkus ke JSON
            print(json.dumps({"markdown": result, "status": "success"}))
            
    except Exception as e:
        error_msg = {"status": "error", "message": f"Worker Error: {str(e)}", "image": args.image}
        print(json.dumps(error_msg))
        sys.exit(1)

if __name__ == "__main__":
    main()
