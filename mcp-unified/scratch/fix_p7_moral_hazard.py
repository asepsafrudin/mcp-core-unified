import json
import os

def fix_pasal_7():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_perfected_final.json"
    with open(json_path, "r") as f:
        data = json.load(f)
    
    ket_text = "Perlu dipertimbangkan moral hazard kab/kota akan mengembangkan/melakukan pemekaran kecamatan pada kepulauan yang berbeda"
    
    found = False
    for i in range(len(data)):
        item = data[i]
        substance = item.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', '')
        if "Kabupaten/kota sebagaimana tercantum dalam Lampiran" in substance and item.get('tanggapan_pemerintah') == 'KEMENKEU':
            item['keterangan'] = ket_text
            item['nomor_urut_internal'] = "6." # Based on PDF No. 6
            found = True
            break
            
    print(f"Manual Fix for Pasal 7 Results: {found}")
    
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    fix_pasal_7()
