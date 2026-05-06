import json
import os

def precision_fix_kemenlu():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_with_kemenlu.json"
    with open(json_path, "r") as f:
        data = json.load(f)
    
    target_text_85 = """Disarankan untuk dihapus. Namun demikian, perlu dibentuk atau ditetapkan suatu mekanisme penetapan wilayah pengelolaan laut daerah provinsi kepulauan sesuai dengan peraturan perundang-undangan yang ada. 

Menggunakan referensi UNCLOS dinilai kurang tepat karena hal tersebut mengatur tentang pembagian wilayah laut antara Indonesia dengan negara yang berbatasan."""

    found_85 = False
    
    for i in range(len(data)):
        item = data[i]
        
        # 1. Clear the misplaced text from DIM 98 (if it exists there)
        if item.get('no._dim') == "98" and item.get('tanggapan_pemerintah') == 'KEMENLU':
            if "Disarankan untuk dihapus" in item.get('keterangan', ''):
                # Clean up the clumped text
                item['keterangan'] = "Mutatis mutandis dengan DIM 97. Sudah diatur dalam Pasal 27 s.d. Pasal 30 dan Lampiran UU No. 23 Tahun 2014 tentang Pemerintahan Daerah."
        
        # 2. Place it correctly in DIM 85
        if item.get('no._dim') == "85" and item.get('tanggapan_pemerintah') == 'KEMENLU':
            item['usulan_perubahan'] = target_text_85
            found_85 = True

    print(f"Precision Fix for KEMENLU DIM 85: {found_85}")
    
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    precision_fix_kemenlu()
