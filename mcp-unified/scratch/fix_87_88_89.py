import json
import os

def fix_87_88_89():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_with_kemenlu.json"
    with open(json_path, "r") as f:
        data = json.load(f)
    
    mapping = {
        "87": {
            "usulan": "Disarankan untuk dihapus",
            "keterangan": "Telah diatur dalam UU No. 23 Tahun 2014 tentang Pemerintahan Daerah."
        },
        "88": {
            "usulan": "Disarankan untuk dihapus",
            "keterangan": "Telah diatur dalam UU No. 23 Tahun 2014 tentang Pemerintahan Daerah."
        },
        "89": {
            "usulan": "Disarankan untuk dihapus",
            "keterangan": "Mutatis mutandis dengan DIM 1."
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

    print(f"Updated {updated_count} rows for KEMENLU (87, 88, 89).")
    
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    fix_87_88_89()
