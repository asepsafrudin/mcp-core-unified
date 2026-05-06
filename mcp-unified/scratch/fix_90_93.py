import json
import os

def fix_90_93():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_with_kemenlu_audited.json"
    with open(json_path, "r") as f:
        data = json.load(f)
    
    mapping = {
        "90": {
            "usulan": "Disarankan untuk dihapus",
            "keterangan": "Mutatis mutandis dengan DIM 86."
        },
        "91": {
            "usulan": "Disarankan untuk dihapus atau disesuaikan dengan UU No. 23 Tahun 2014 tentang Pemerintahan Daerah.",
            "keterangan": ""
        },
        "92": {
            "usulan": "Disarankan untuk dihapus atau disesuaikan dengan UU No. 23 Tahun 2014 tentang Pemerintahan Daerah.",
            "keterangan": ""
        },
        "93": {
            "usulan": "Disarankan untuk dihapus atau disesuaikan dengan UU No. 23 Tahun 2014 tentang Pemerintahan Daerah.",
            "keterangan": ""
        }
    }

    updated_count = 0
    for i in range(len(data)):
        item = data[i]
        d_num = item.get('no._dim')
        if d_num in mapping and item.get('tanggapan_pemerintah') == 'KEMENLU':
            item['usulan_perubahan'] = mapping[d_num]['usulan']
            item['keterangan'] = mapping[d_num]['keterangan']
            updated_count += 1

    print(f"Updated {updated_count} rows for KEMENLU (90, 91, 92, 93).")
    
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    fix_90_93()
