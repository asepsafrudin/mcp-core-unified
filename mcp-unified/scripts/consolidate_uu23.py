import json
from pathlib import Path

# Paths
base_dir = Path("/home/aseps/MCP/src/Bangda_PUU/data/workspace/lampiran_UU_23/processed")
body_path = base_dir / "UU_23_2014_PEMERINTAHAN_DAERAH_parsed.json"
lampiran_path = base_dir / "UU_23_2014_lampiran.json"
output_path = base_dir / "UU_23_2014_single_source_of_truth.json"

# Mapping Bidang Codes to Pasal 12 Ayat and Huruf
bidang_pasal_map = {
    "A": {"pasal": 12, "ayat": 1, "huruf": "a", "jenis_urusan": "Urusan Pemerintahan Wajib yang berkaitan dengan Pelayanan Dasar"},
    "B": {"pasal": 12, "ayat": 1, "huruf": "b", "jenis_urusan": "Urusan Pemerintahan Wajib yang berkaitan dengan Pelayanan Dasar"},
    "C": {"pasal": 12, "ayat": 1, "huruf": "c", "jenis_urusan": "Urusan Pemerintahan Wajib yang berkaitan dengan Pelayanan Dasar"},
    "D": {"pasal": 12, "ayat": 1, "huruf": "d", "jenis_urusan": "Urusan Pemerintahan Wajib yang berkaitan dengan Pelayanan Dasar"},
    "E": {"pasal": 12, "ayat": 1, "huruf": "e", "jenis_urusan": "Urusan Pemerintahan Wajib yang berkaitan dengan Pelayanan Dasar"},
    "F": {"pasal": 12, "ayat": 1, "huruf": "f", "jenis_urusan": "Urusan Pemerintahan Wajib yang berkaitan dengan Pelayanan Dasar"},
    "G": {"pasal": 12, "ayat": 2, "huruf": "a", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "H": {"pasal": 12, "ayat": 2, "huruf": "b", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "I": {"pasal": 12, "ayat": 2, "huruf": "c", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "J": {"pasal": 12, "ayat": 2, "huruf": "d", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "K": {"pasal": 12, "ayat": 2, "huruf": "e", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "L": {"pasal": 12, "ayat": 2, "huruf": "f", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "M": {"pasal": 12, "ayat": 2, "huruf": "g", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "N": {"pasal": 12, "ayat": 2, "huruf": "h", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "O": {"pasal": 12, "ayat": 2, "huruf": "i", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "P": {"pasal": 12, "ayat": 2, "huruf": "j", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "Q": {"pasal": 12, "ayat": 2, "huruf": "k", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "R": {"pasal": 12, "ayat": 2, "huruf": "l", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "S": {"pasal": 12, "ayat": 2, "huruf": "m", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "T": {"pasal": 12, "ayat": 2, "huruf": "n", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "U": {"pasal": 12, "ayat": 2, "huruf": "o", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "V": {"pasal": 12, "ayat": 2, "huruf": "p", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "W": {"pasal": 12, "ayat": 2, "huruf": "q", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "X": {"pasal": 12, "ayat": 2, "huruf": "r", "jenis_urusan": "Urusan Pemerintahan Wajib yang tidak berkaitan dengan Pelayanan Dasar"},
    "Y": {"pasal": 12, "ayat": 3, "huruf": "a", "jenis_urusan": "Urusan Pemerintahan Pilihan"},
    "Z": {"pasal": 12, "ayat": 3, "huruf": "b", "jenis_urusan": "Urusan Pemerintahan Pilihan"},
    "AA": {"pasal": 12, "ayat": 3, "huruf": "c", "jenis_urusan": "Urusan Pemerintahan Pilihan"},
    "BB": {"pasal": 12, "ayat": 3, "huruf": "d", "jenis_urusan": "Urusan Pemerintahan Pilihan"},
    "CC": {"pasal": 12, "ayat": 3, "huruf": "e", "jenis_urusan": "Urusan Pemerintahan Pilihan"},
    "DD": {"pasal": 12, "ayat": 3, "huruf": "f", "jenis_urusan": "Urusan Pemerintahan Pilihan"},
    "EE": {"pasal": 12, "ayat": 3, "huruf": "g", "jenis_urusan": "Urusan Pemerintahan Pilihan"},
    "FF": {"pasal": 12, "ayat": 3, "huruf": "h", "jenis_urusan": "Urusan Pemerintahan Pilihan"}
}

def main():
    print("Starting consolidation of UU 23/2014 Batang Tubuh and Lampiran...")
    
    if not body_path.exists():
        print(f"Error: {body_path} not found.")
        return
    if not lampiran_path.exists():
        print(f"Error: {lampiran_path} not found.")
        return

    # Load JSON files
    with open(body_path, 'r', encoding='utf-8') as f:
        body_data = json.load(f)
        
    with open(lampiran_path, 'r', encoding='utf-8') as f:
        lampiran_data = json.load(f)
        
    # Inject cross-references into Lampiran Bidang
    for bidang in lampiran_data.get('bidang', []):
        code = bidang.get('kode')
        ref = bidang_pasal_map.get(code)
        if ref:
            bidang['referensi_hukum'] = {
                "pasal": ref["pasal"],
                "ayat": ref["ayat"],
                "huruf": ref["huruf"],
                "jenis_urusan": ref["jenis_urusan"],
                "label_referensi": f"Pasal {ref['pasal']} ayat ({ref['ayat']}) huruf {ref['huruf']}"
            }
            print(f"  Mapped Bidang {code} ({bidang.get('nama_bidang')}) -> {bidang['referensi_hukum']['label_referensi']}")
            
    # Combine into a single JSON structure
    consolidated_data = {
        "undang_undang": "Undang-Undang Republik Indonesia Nomor 23 Tahun 2014 Tentang Pemerintahan Daerah",
        "metadata": body_data.get("metadata", {}),
        "pembukaan": body_data.get("pembukaan", {}),
        "batang_tubuh": {
            "bab": body_data.get("bab", [])
        },
        "lampiran": {
            "judul": lampiran_data.get("judul", ""),
            "bidang": lampiran_data.get("bidang", [])
        }
    }
    
    # Save output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(consolidated_data, f, indent=2, ensure_ascii=False)
        
    print(f"\nSuccess! Saved consolidated single source of truth database to: {output_path}")

if __name__ == "__main__":
    main()
