import json
import os

def manual_fix_pasal_1():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_perfected_final.json"
    with open(json_path, "r") as f:
        data = json.load(f)
    
    # Target strings from PDF for Pasal 1
    # 9. Dana Perimbangan
    # 10. Dana Transfer Khusus
    # 11. Dana Khusus Kepulauan
    
    found_9 = False
    found_10 = False
    found_11 = False
    
    for i in range(len(data)):
        item = data[i]
        if item.get('tanggapan_pemerintah') != 'KEMENKEU':
            continue
            
        substance = item.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', '')
        
        # Match 9
        if "Dana Perimbangan" in substance:
            item['nomor_urut_internal'] = "9."
            item['keterangan'] = "[PERUBAHAN SUBSTANSI] Usulan: Transfer ke Daerah yang selanjutnya disingkat TKD adalah dana yang bersumber dari APBN dan merupakan bagian dari belanja negara yang dialokasikan dan disalurkan kepada Daerah untuk dikelola oleh Daerah dalam rangka mendanai penyelenggaraan Urusan Pemerintahan yang menjadi kewenangan Daerah. | Ket: Perlu disesuaikan dengan ketentuan umum dalam Pasal 1 angka 69 UU HKPD"
            if not substance.startswith("9."):
                item['draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)'] = "9. " + substance.replace("1. ", "")
            found_9 = True
            
        # Match 10
        elif "Dana Transfer Khusus" in substance:
            item['nomor_urut_internal'] = "10."
            item['keterangan'] = "[DIHAPUS]"
            if not substance.startswith("10."):
                item['draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)'] = "10. " + substance
            found_10 = True
            
        # Match 11
        elif "Dana Khusus Kepulauan" in substance:
            item['nomor_urut_internal'] = "11."
            item['keterangan'] = "[DIHAPUS] | Ket: Skema sudah ditampung dalam formulasi Dana Alokasi Umum (DAU) yang didalamnya memperhatikan Indeks Daerah Berciri Kepulauan atau luas wilayah laut (IKP). - DBH Perikanan dibagihasilkan kepada kabupaten/kota berdasarkan formula luas wilayah laut dan dibagi sama rata."
            if not substance.startswith("11."):
                item['draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)'] = "11. " + substance
            found_11 = True
            
        # Clean up the misaligned "1. Pasal 1" row if it was enriched incorrectly
        if substance == "1. Pasal 1" or substance == "Pasal 1":
             if "Perlu disesuaikan" in item.get('keterangan', ''):
                 item['keterangan'] = ""
                 item['nomor_urut_internal'] = ""

    print(f"Manual Fix Results: 9:{found_9}, 10:{found_10}, 11:{found_11}")
    
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    manual_fix_pasal_1()
