import json
import os

def manual_fix_pasal_6():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_perfected_final.json"
    with open(json_path, "r") as f:
        data = json.load(f)
    
    usulan_text = "Mengeluarkan Kota Mataram dan Kota Kupang sebagai Daerah Kabupaten/Kota Kepulauan."
    ket_text = "Jika kriteria disetujui, maka perlu dicek kembali penetapan daerah pada Lampiran oleh K/L terkait. Karena berdasarkan temuan awal, terdapat beberapa daerah yang diduga tidak memenuhi kriteria, seperti Kota Mataram dan Kota Kupang."
    
    found = False
    for i in range(len(data)):
        item = data[i]
        # Match Pasal 6 ayat (1) substance
        substance = item.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', '')
        if "Provinsi sebagaimana tercantum dalam Lampiran" in substance and item.get('tanggapan_pemerintah') == 'KEMENKEU':
            item['usulan_perubahan'] = usulan_text
            # Append to existing keterangan or set it
            existing_ket = item.get('keterangan', '')
            item['keterangan'] = f"{existing_ket}\n{ket_text}".strip()
            item['nomor_urut_internal'] = "5." # Based on PDF No. 5
            found = True
            
        # Clean up if it was incorrectly put in Pasal 7
        if "Kabupaten/kota sebagaimana tercantum dalam Lampiran" in substance and item.get('tanggapan_pemerintah') == 'KEMENKEU':
             if "Kota Mataram" in item.get('keterangan', ''):
                 item['keterangan'] = ""
                 item['usulan_perubahan'] = ""

    print(f"Manual Fix for Pasal 6 Results: {found}")
    
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    manual_fix_pasal_6()
