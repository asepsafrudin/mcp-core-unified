import json
import shutil
from pathlib import Path

json_path = Path('/home/aseps/MCP/workspace/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_single_source_of_truth.json')

# Backup before modifying
backup_path = json_path.with_name(json_path.name + ".bak_24_items")
shutil.copy2(json_path, backup_path)

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

replacements = {
    # 1. Bidang C
    "Pengembangan dan pengelolaan sistem irigasi primer dan sekunder pada daerah irigasi yang luasnya lebih dari 3000 ha, daerah irigasi lintas Daerah provinsi, daerah irigasi lintas negara, dan daerah irigasi strategis":
    "Pengembangan dan pengelolaan sistem irigasi primer dan sekunder pada daerah irigasi yang luasnya lebih dari 3000 ha, daerah irigasi lintas Daerah provinsi, daerah irigasi lintas negara, dan daerah irigasi strategis nasional.",

    # 2. Bidang F
    "Penyelenggaraan pemberdayaan masyarakat terhadap kesiapsiagaan dalam menghadapi bencana":
    "Penyelenggaraan pemberdayaan masyarakat terhadap kesiapsiagaan dalam menghadapi bencana provinsi.",

    # 3. Bidang G
    "Pelayanan antar kerja di Daerah kabupaten/kota":
    "Pelayanan antar kerja di Daerah kabupaten/kota.",

    # 4. Bidang H
    "Penyediaan layanan bagi keluarga dalam mewujudkan KG dan hak":
    "Penyediaan layanan bagi keluarga dalam mewujudkan KG dan hak anak.",

    # 5. Bidang N
    "Pelaksanaan advokasi, komunikasi, informasi dan edukasi (KIE) pengendalian penduduk":
    "Pelaksanaan advokasi, komunikasi, informasi dan edukasi (KIE) pengendalian penduduk dan keluarga berencana (KB).",

    # 6. Bidang O
    "Penerbitan izin usaha angkutan laut pelayaran rakyat bagi orang perorangan atau badan usaha yang berdomisili dan yang beroperasi pada lintas pelabuhan antar- Daerah kabupaten/kota dalam Daerah provinsi, pelabuhan antar-Daerah provinsi, dan pelabuhan":
    "Penerbitan izin usaha angkutan laut pelayaran rakyat bagi orang perorangan atau badan usaha yang berdomisili dan yang beroperasi pada lintas pelabuhan antar- Daerah kabupaten/kota dalam Daerah provinsi, pelabuhan antar-Daerah provinsi, dan pelabuhan pengumpan regional.",

    # 7. Bidang O
    "Penerbitan izin usaha penyelenggaraan angkutan sungai dan penyeberangan":
    "Penerbitan izin usaha penyelenggaraan angkutan sungai dan penyeberangan dalam wilayah kabupaten/kota.",

    # 8. Bidang O
    "Penetapan jaringan jalur kereta api yang jaringannya dalam 1 (satu) Daerah":
    "Penetapan jaringan jalur kereta api yang jaringannya dalam 1 (satu) Daerah kabupaten/kota.",

    # 9. Bidang R
    "C. Pelayanan penanaman modal pada bidang industri yang merupakan prioritas tinggi pada skala pelayanan perizinan dan nonperizinan secara terpadu satu pintu:":
    "C. Pelayanan penanaman modal pada bidang industri yang merupakan prioritas tinggi pada skala pelayanan perizinan dan nonperizinan secara terpadu satu pintu tingkat pusat.",

    # 10. Bidang W
    "Pelestarian naskah kuno dan pengembalian":
    "Pelestarian naskah kuno dan pengembalian naskah kuno nusantara.",

    # 11. Bidang X
    "Pengelolaan arsip statis yang diciptakan oleh lembaga negara di Pusat dan Daerah, BUMN, organisasi kemasyarakatan tingkat nasional, organisasi politik tingkat nasional, tokoh nasional dan perusahaan swasta yang":
    "Pengelolaan arsip statis yang diciptakan oleh lembaga negara di Pusat dan Daerah, BUMN, organisasi kemasyarakatan tingkat nasional, organisasi politik tingkat nasional, tokoh nasional dan perusahaan swasta yang berskala nasional.",

    # 12. Bidang X
    "Pengelolaan arsip statis yang diciptakan oleh Pemerintah Daerah provinsi, BUMD provinsi, perusahaan swasta yang cabang usahanya lebih dari 1 (satu) Daerah kabupaten/kota dalam 1 (satu) Daerah provinsi, organisasi kemasyarakatan":
    "Pengelolaan arsip statis yang diciptakan oleh Pemerintah Daerah provinsi, BUMD provinsi, perusahaan swasta yang cabang usahanya lebih dari 1 (satu) Daerah kabupaten/kota dalam 1 (satu) Daerah provinsi, organisasi kemasyarakatan tingkat provinsi.",

    # 13. Bidang X
    "Pengelolaan arsip statis yang diciptakan oleh Pemerintahan Daerah kabupaten/kota, BUMD kabupaten/kota, perusahaan swasta yang kantor usahanya dalam 1 (satu) Daerah kabupaten/kota, organisasi":
    "Pengelolaan arsip statis yang diciptakan oleh Pemerintahan Daerah kabupaten/kota, BUMD kabupaten/kota, perusahaan swasta yang kantor usahanya dalam 1 (satu) Daerah kabupaten/kota, organisasi kemasyarakatan tingkat kabupaten/kota.",

    # 14. Bidang X
    "Melakukan autentikasi pemekaran Kecamatan":
    "Melakukan autentikasi pemekaran Kecamatan dan desa/kelurahan.",

    # 15. Bidang Y
    "Penerbitan izin usaha perikanan tangkap untuk:":
    "Penerbitan izin usaha perikanan tangkap untuk wilayah laut di atas 12 mil.",

    # 16. Bidang AA
    "Pengawasan mutu dan peredaran benih/bibit ternak dan sumber daya genetik (SDG) hewan":
    "Pengawasan mutu dan peredaran benih/bibit ternak dan tanaman pakan ternak serta pakan di lintas Daerah kabupaten/kota dalam 1 (satu) Daerah provinsi.",

    # 17. Bidang AA
    "Pengendalian penyediaan dan peredaran benih/bibit ternak, dan hijauan pakan":
    "Pengendalian penyediaan dan peredaran benih/bibit ternak, dan hijauan pakan ternak dalam Daerah kabupaten/kota.",

    # 18. Bidang AA
    "Penetapan dan penerapan persyaratan kesehatan hewan dan kesehatan masyarakat veteriner":
    "Penetapan dan penerapan persyaratan kesehatan hewan dan kesehatan masyarakat veteriner.",

    # 19. Bidang AA
    "Pengawasan pemasukan hewan dan produk hewan":
    "Pengawasan pemasukan hewan dan produk hewan dari luar Daerah kabupaten/kota.",

    # 20. Bidang BB
    "Penyelenggaraan pemanfaatan jenis":
    "Penyelenggaraan pemanfaatan jenis tumbuhan dan satwa liar.",

    # 21. Bidang CC
    "Penetapan wilayah pertambangan sebagai bagian dari rencana tata ruang wilayah nasional, yang terdiri atas wilayah usaha pertambangan, wilayah pertambangan rakyat dan wilayah pencadangan negara serta wilayah usaha":
    "Penetapan wilayah pertambangan sebagai bagian dari rencana tata ruang wilayah nasional, yang terdiri atas wilayah usaha pertambangan, wilayah pertambangan rakyat dan wilayah pencadangan negara serta wilayah usaha pertambangan khusus.",

    # 22. Bidang CC
    "Penetapan tarif tenaga listrik untuk konsumen dan penerbitan izin pemanfaatan jaringan untuk telekomunikasi, multimedia, dan informatika dari pemegang":
    "Penetapan tarif tenaga listrik untuk konsumen dan penerbitan izin pemanfaatan jaringan untuk telekomunikasi, multimedia, dan informatika dari pemegang izin operasi.",

    # 23. Bidang DD
    "Penerbitan izin usaha untuk: 1) perantara perdagangan properti; 2) penjualan langsung; 3) perwakilan perusahaan perdagangan asing; 4) usaha perdagangan yang di dalamnya terdapat modal asing; 5) jasa survei dan jasa lainnya di bidang perdagangan tertentu; dan":
    "Penerbitan izin usaha untuk: 1) perantara perdagangan properti; 2) penjualan langsung; 3) perwakilan perusahaan perdagangan asing; 4) usaha perdagangan yang di dalamnya terdapat modal asing; 5) jasa survei dan jasa lainnya di bidang perdagangan tertentu; dan 6) penyelenggara pameran dagang.",

    # 24. Bidang FF
    "Pengembangan satuan permukiman pada tahap penyesuaian. Pengembangan satuan permukiman pada tahap pemantapan. Pengembangan satuan permukiman pada tahap kemandirian. II. MANAJEMEN PENYELENGGARAAN URUSAN PEMERINTAHAN KONKUREN Substansi urusan yang dibagi antara Pemerintah Pusat dan Daerah provinsi dan Daerah kabupaten/kota sebagaimana dimuat dalam matriks pembagian Urusan Pemerintahan konkuren antara Pemerintah Pusat dan Daerah provinsi dan Daerah kabupaten/kota tersebut di atas termasuk kewenangan dalam pengelolaan unsur manajemen (yang meliputi sarana dan prasarana, personil, bahan-bahan, metode kerja) dan kewenangan dalam penyelenggaraan fungsi manajemen (yang meliputi perencanaan, pengorganisasian, pelaksanaan, pengoordinasian, penganggaran, pengawasan, penelitian dan pengembangan, standardisasi, dan pengelolaan informasi) dalam substansi Urusan Pemerintahan tersebut melekat menjadi kewenangan masing-masing tingkatan atau susunan pemerintahan tersebut, kecuali apabila dalam matriks pembagian Urusan Pemerintahan konkuren antara Pemerintah Pusat dan Daerah provinsi dan Daerah kabupaten/kota tersebut terdapat unsur manajemen dan/atau fungsi manajemen yang secara khusus sudah dinyatakan menjadi kewenangan suatu tingkatan atau susunan pemerintahan yang lain, sehingga tidak lagi melekat pada substansi Urusan Pemerintahan pada tingkatan atau susunan pemerintahan tersebut. Salah satu contoh matriks pembagian Urusan Pemerintahan bidang Pendidikan. Dalam matriks Urusan Pemerintahan bidang Pendidikan terdiri atas 6 (enam) sub Urusan Pemerintahan yaitu manajemen pendidikan, kurikulum, akreditasi, pendidik dan tenaga kependidikan, perizinan pendidikan, dan bahasa dan sastra. Dari keenam sub Urusan Pemerintahan tersebut yang merupakan substansi Urusan Pemerintahan adalah sub urusan manajemen pendidikan; kurikulum; perizinan pendidikan; dan bahasa dan sastra, sedangkan yang merupakan unsur manajemen adalah sub urusan pendidik dan tenaga kependidikan dan yang merupakan fungsi manajemen adalah sub urusan akreditasi. Perincian pembagian Urusan Pemerintahan bidang pendidikan yang merupakan substansi Urusan Pemerintahan bidang pendidikan adalah sebagai berikut: 1. Sub urusan manajemen pendidikan:":
    "Pengembangan satuan permukiman pada tahap penyesuaian. Pengembangan satuan permukiman pada tahap pemantapan. Pengembangan satuan permukiman pada tahap kemandirian."
}

def replace_in_text(text):
    if not isinstance(text, str): return text
    for old, new in replacements.items():
        if old == text:
            return new
    return text

count = 0
for bidang in data.get('lampiran', {}).get('bidang', []):
    for sub in bidang.get('sub_urusan', []):
        for auth in ['pemerintah_pusat', 'daerah_provinsi', 'daerah_kabupaten_kota']:
            auth_data = sub.get(auth, {})
            
            # check teks
            if 'teks' in auth_data:
                old_teks = auth_data['teks']
                new_teks = replace_in_text(old_teks)
                if old_teks != new_teks:
                    auth_data['teks'] = new_teks
                    count += 1
            
            # check butir
            if 'butir' in auth_data:
                for b in auth_data['butir']:
                    old_b = b.get('teks', '')
                    new_b = replace_in_text(old_b)
                    if old_b != new_b:
                        b['teks'] = new_b
                        count += 1

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Replacement complete! Made {count} replacements in the JSON file.")
