"""
query_normalizer.py — Modul Penyelaras Kueri Obrolan Santai ke Formulasi Regulasi (HyDE / Query Rewriter).
Mengubah kalimat percakapan WhatsApp yang kasual/panjang menjadi kata kunci hukum normatif murni
sebelum di-embed ke pgvector nomic-embed-text dan pencarian leksikal.
"""

import re
from typing import List, Tuple

# Peta sinonim istilah bahasa percakapan sehari-hari ke istilah baku peraturan perundang-undangan
COLLOQUIAL_LEGAL_MAP = {
    # Kepegawaian & ASN
    "cuti melahirkan": "cuti melahirkan aparatur sipil negara manajemen pegawai pppk pns",
    "gaji pppk": "gaji dan tunjangan pegawai pemerintah dengan perjanjian kerja",
    "kenaikan pangkat": "kenaikan pangkat pola karier jabatan fungsional pns asn",
    "disiplin pns": "disiplin pegawai negeri sipil kewajiban dan larangan hukuman disiplin pp 94",
    "pecat pns": "pemberhentian pegawai negeri sipil pelanggaran disiplin berat",
    "non asn": "penataan tenaga non asn pegawai honorer pppk",
    "pensiun": "batas usia pensiun jaminan pensiun hari tua asn",
    
    # Daerah & Urusan Konkuren UU 23/2014
    "sampah": "pengelolaan persampahan tempat pemrosesan akhir tpa regional lingkungan hidup",
    "tpa": "tempat pemrosesan akhir regional sampah lingkungan hidup",
    "tata ruang": "rencana tata ruang wilayah rtrw persetujuan substansi atr bpn",
    "rtrw": "rencana tata ruang wilayah rtrw persetujuan substansi permendagri 13/2016",
    "rpjmd": "rencana pembangunan jangka menengah daerah evaluasi ranperda permendagri 86/2017",
    "rpjpd": "rencana pembangunan jangka panjang daerah evaluasi permendagri 86/2017",
    "pajak daerah": "pajak daerah dan retribusi daerah pdrd uu 1/2022 hkpd",
    "retribusi": "retribusi daerah evaluasi tarif pdrd uu 1/2022 hkpd",
    "dana desa": "pengelolaan keuangan desa alokasi dana desa permendagri 20/2018",
    "batal perda": "pengujian perda hak uji materil mahkamah agung putusan mk 137",
    "spm": "standar pelayanan minimal pemenuhan kebutuhan dasar urusan wajib pp 2/2018",
    
    # Tata Naskah & Klasifikasi Persuratan
    "format nota dinas": "tata naskah dinas kemendagri nota dinas permendagri 1/2023",
    "margin surat": "tata naskah dinas margin font arial ukuran permendagri 1/2023",
    "kode surat": "kode klasifikasi arsip penomoran naskah dinas permendagri 83/2022",
    "tte": "tanda tangan elektronik sertifikasi bsre bssn tata naskah dinas",
    "mandat plt": "pelaksana tugas plt pelaksana harian plh atas nama an untuk beliau ub",
    
    # Satria & Organisasi Bangda
    "struktur bangda": "struktur organisasi tata kerja sotk ditjen bina pembangunan daerah permendagri 9/2025",
    "peippd": "direktorat perencanaan evaluasi informasi pembangunan daerah ditjen bangda",
    "supd": "direktorat sinkronisasi urusan pemerintahan daerah ditjen bangda",
    
    # Perumahan & Prasarana Utilitas Umum
    "prasarana utilitas umum": "penyerahan prasarana sarana dan utilitas umum psu perumahan permendagri 15 tahun 2026",
    "psu": "penyerahan prasarana sarana dan utilitas umum psu perumahan permendagri 15 tahun 2026",
    "utilitas umum": "penyerahan prasarana sarana dan utilitas umum psu perumahan permendagri 15 tahun 2026"
}

# Stopwords percakapan WhatsApp yang sering mengotori embedding vektor
CHAT_STOPWORDS = {
    "tolong", "mohon", "coba", "carikan", "cariin", "dong", "min", "satria", "bot",
    "bisa", "apakah", "bagaimana", "gimana", "apa", "sih", "nih", "ya", "yah", "kan",
    "mau", "tanya", "nanya", "ada", "nggak", "tidak", "gak", "tau", "info", "tentang",
    "terkait", "soal", "mengenai", "aturan", "regulasi", "peraturan", "nomor", "tahun",
    "pasal", "halo", "selamat", "pagi", "siang", "sore", "malam", "pak", "bu", "mas",
    "mbak", "bro", "admin", "terima", "kasih", "thanks"
}

def normalize_legal_query(query: str) -> Tuple[str, List[str]]:
    """
    Menyelaraskan query chat santai menjadi:
    1. normalized_prompt: Kalimat representasi semantik hukum untuk pgvector embedding.
    2. keywords: Daftar kata kunci presisi untuk filter leksikal ILIKE / Full-Text Search.
    """
    q_raw = query.strip()
    q_lower = q_raw.lower()

    # 1. Deteksi apakah cocok dengan frasa percakapan hukum populer (Colloquial Mapping)
    expanded_terms = []
    for colloquial, formal_terms in COLLOQUIAL_LEGAL_MAP.items():
        if colloquial in q_lower:
            expanded_terms.append(formal_terms)

    # 2. Ekstraksi nomor peraturan spesifik (UU 23/2014, Permendagri 86/2017, PP 2/2018, dll)
    reg_numbers = re.findall(r"\b(?:uu|pp|perpres|permendagri|kepmen|inpres|se)\s*(?:no\.?|nomor)?\s*\d+(?:[./]\d+)*(?:\s*tahun\s*\d{4}|\/\d{4})?", q_lower)
    
    # Ekstraksi kata-kata kunci penting (minimal 3 huruf, bukan stopword)
    cleaned_tokens = []
    tokens = re.findall(r"[a-zA-Z0-9/.-]{3,}", q_lower)
    for t in tokens:
        clean_t = t.strip("./")
        if len(clean_t) >= 3 and clean_t not in CHAT_STOPWORDS and not clean_t.isdigit():
            if clean_t not in cleaned_tokens:
                cleaned_tokens.append(clean_t)

    # Susun kata kunci leksikal
    keywords = list(dict.fromkeys(reg_numbers + cleaned_tokens))[:8]

    # 3. Susun normalized_prompt untuk embedding
    if expanded_terms:
        # Gunakan pengayaan semantik
        normalized_prompt = f"{' '.join(expanded_terms)} {' '.join(keywords)}"
    else:
        # Bersihkan dari kata-kata obrolan chat WhatsApp
        normalized_prompt = " ".join(cleaned_tokens) if cleaned_tokens else q_raw

    # Jika query memuat nomor regulasi spesifik, letakkan di depan
    if reg_numbers:
        normalized_prompt = f"{' '.join(reg_numbers)} {normalized_prompt}"

    return normalized_prompt.strip(), keywords

