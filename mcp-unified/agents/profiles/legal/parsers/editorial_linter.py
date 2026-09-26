"""
editorial_linter.py — Pilar 2: Editorial & PUEBI Compliance Engine (Subtask 131-E)
====================================================================================
Engine validasi bahasa hukum, kepatuhan PUEBI, dan harmonisasi glosarium.

Fitur:
1. PUEBI Compliance Check     — ejaan, tanda baca, huruf kapital
2. Typo & Redundancy Linter   — frasa berulang, kata tidak baku
3. Glosarium Harmonizer        — konsistensi penggunaan istilah lintas pasal
4. Cross-Reference Validator   — cek rujukan silang masih valid setelah transformasi
5. Consistency Checker         — terminologi konsisten antar bab/pasal
6. Legal Style Guide           — kepatuhan format penomoran UU 12/2011

Digunakan oleh: legal_tools.py → legal_lint_editorial()
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from .legal_ast_parser import extract_articles_flat, get_glossary_definitions


# ─── Konstanta PUEBI & Hukum ─────────────────────────────────────────────────

# Kata tidak baku umum dalam bahasa hukum Indonesia
KATA_TIDAK_BAKU: Dict[str, str] = {
    "ijin": "izin",
    "ijinkan": "izinkan",
    "kwantitas": "kuantitas",
    "kwalitas": "kualitas",
    "standart": "standar",
    "standard": "standar",
    "rubah": "ubah",
    "merubah": "mengubah",
    "dirubah": "diubah",
    "dirobah": "diubah",
    "sistim": "sistem",
    "analisa": "analisis",
    "aktifitas": "aktivitas",
    "aktif": "aktif",  # OK
    "tehnik": "teknik",
    "effektif": "efektif",
    "effisien": "efisien",
    "resiko": "risiko",
    "nasehat": "nasihat",
    "jaman": "zaman",
    "jadual": "jadwal",
    "azas": "asas",
    "azaz": "asas",
    "propinsi": "provinsi",
    "propinsi": "provinsi",
}

# Frasa mubazir (pleonasme) yang perlu ditandai
FRASA_MUBAZIR: List[Tuple[str, str]] = [
    (r'para\s+anggota-anggota', "redundan: 'para anggota' sudah jamak"),
    (r'saling\s+berinteraksi', "redundan: 'berinteraksi' sudah bermakna timbal balik"),
    (r'turun\s+kebawah', "redundan: 'turun' sudah bermakna ke bawah"),
    (r'masuk\s+kedalam', "redundan: 'masuk' sudah bermakna ke dalam"),
    (r'sejak\s+dari', "redundan: gunakan 'sejak' saja"),
    (r'demi\s+untuk', "redundan: gunakan 'demi' atau 'untuk'"),
    (r'agar\s+supaya', "redundan: gunakan 'agar' atau 'supaya'"),
]

# Pola gaya penulisan hukum UU 12/2011
STYLE_VIOLATIONS: List[Tuple[str, str, str]] = [
    # (pattern, contoh_salah, rekomendasi)
    (r'pasal\s+\d+\s+berbunyi\s+sebagai\s+berikut', "frasa 'berbunyi sebagai berikut' tidak sesuai gaya UU 12/2011", "hapus 'berbunyi sebagai berikut'"),
    (r'(?i)dst\.|etc\.', "singkatan 'dst.' tidak baku dalam naskah hukum", "tulis lengkap 'dan seterusnya'"),
    (r'(?i)\bsb\b', "singkatan 'sb' tidak baku", "tulis lengkap"),
    (r'(?<!\w)/(?!\w)', "garis miring '/' sebaiknya diganti 'atau'", "gunakan kata 'atau'"),
    (r'\d{4}\s*-\s*\d{4}', "penulisan rentang tahun dengan tanda '-' tidak sesuai", "gunakan s.d. atau sampai dengan"),
]

# Pattern untuk pengecekan penggunaan huruf kapital pada nomenklatur
NOMENKLATUR_KAPITAL = re.compile(
    r'(?<!\n)(?<!\.\s)(bupati|walikota|gubernur|presiden|menteri|direktur jenderal|kepala daerah)\b',
    re.IGNORECASE
)


# ─── PUEBI Compliance Functions ───────────────────────────────────────────────

def check_puebi_compliance(legal_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Memeriksa kepatuhan ejaan dan tata bahasa terhadap PUEBI (Pilar 2: P2-01).
    
    Returns:
        List of findings: [{article_id, clause, finding_type, text, suggestion}]
    """
    findings: List[Dict[str, Any]] = []
    articles = extract_articles_flat(legal_doc)
    
    for art in articles:
        full_text = art.get("raw_text", "")
        art_id = art["article_id"]
        
        # 1. Kata tidak baku
        for kata_salah, kata_baku in KATA_TIDAK_BAKU.items():
            pattern = re.compile(r'\b' + re.escape(kata_salah) + r'\b', re.IGNORECASE)
            if pattern.search(full_text):
                findings.append({
                    "article_id": art_id,
                    "clause": None,
                    "finding_type": "PUEBI_KATA_TIDAK_BAKU",
                    "text": f"'{kata_salah}' ditemukan",
                    "suggestion": f"Ganti dengan '{kata_baku}'"
                })
        
        # 2. Frasa mubazir
        for pola, keterangan in FRASA_MUBAZIR:
            if re.search(pola, full_text, re.IGNORECASE):
                findings.append({
                    "article_id": art_id,
                    "clause": None,
                    "finding_type": "PUEBI_FRASA_MUBAZIR",
                    "text": keterangan,
                    "suggestion": "Sederhanakan frasa"
                })
        
        # 3. Pengecekan tanda titik di akhir ayat
        for clause in art.get("clauses", []):
            clause_text = clause.get("raw_text", "").strip()
            if clause_text and not clause_text.endswith(('.', ';', ':')):
                findings.append({
                    "article_id": art_id,
                    "clause": clause.get("number"),
                    "finding_type": "PUEBI_TANDA_BACA",
                    "text": "Ayat tidak diakhiri tanda baca yang tepat",
                    "suggestion": "Tambahkan '.' di akhir ayat terakhir, ';' di ayat selain terakhir"
                })
        
        # 4. Penggunaan huruf kapital nomenklatur jabatan (hanya kapital di awal kalimat)
        for m in NOMENKLATUR_KAPITAL.finditer(full_text):
            jabatan = m.group(0)
            if jabatan[0].isupper():
                # Cek apakah ini di awal kalimat (valid) atau di tengah (perlu lower)
                pos = m.start()
                preceding = full_text[max(0, pos-3):pos].strip()
                if preceding and not preceding.endswith('.'):
                    findings.append({
                        "article_id": art_id,
                        "clause": None,
                        "finding_type": "PUEBI_KAPITAL_JABATAN",
                        "text": f"'{jabatan}' ditulis kapital di tengah kalimat",
                        "suggestion": f"Gunakan huruf kecil: '{jabatan.lower()}' kecuali di awal kalimat"
                    })
    
    return findings


def check_typo_and_redundancy(legal_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Deteksi kata berulang berturut-turut dan frasa duplikat dalam satu pasal (P2-02).
    """
    findings: List[Dict[str, Any]] = []
    articles = extract_articles_flat(legal_doc)
    
    for art in articles:
        text = art.get("raw_text", "")
        art_id = art["article_id"]
        
        # Kata ganda berturut-turut (misal: "yang yang", "dan dan")
        duplikat = re.findall(r'\b(\w+)\s+\1\b', text, re.IGNORECASE)
        for kata in duplikat:
            findings.append({
                "article_id": art_id,
                "clause": None,
                "finding_type": "TYPO_KATA_GANDA",
                "text": f"Kata '{kata}' muncul berurutan",
                "suggestion": f"Hapus salah satu '{kata}'"
            })
        
        # Frasa kalimat yang berulang antar ayat
        ayat_texts = [c.get("raw_text", "")[:100] for c in art.get("clauses", [])]
        seen_texts = set()
        for at in ayat_texts:
            norm = re.sub(r'\s+', ' ', at.lower().strip())
            if norm and norm in seen_texts:
                findings.append({
                    "article_id": art_id,
                    "clause": None,
                    "finding_type": "TYPO_AYAT_DUPLIKAT",
                    "text": f"Potensi ayat duplikat: '{at[:60]}...'",
                    "suggestion": "Periksa apakah dua ayat ini identik atau perlu dipisah lebih jelas"
                })
            seen_texts.add(norm)
    
    return findings


def harmonize_glossary(legal_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Periksa konsistensi penggunaan istilah/definisi dari Pasal 1 (Ketentuan Umum)
    di seluruh pasal dokumen (P2-03: Glosarium Harmonizer).
    
    Returns:
        Dict dengan:
        - definitions: {term: definition}
        - inconsistencies: [{article_id, term, context, suggestion}]
        - undefined_terms: [term] — istilah yang digunakan tapi tidak terdefinisi
    """
    definitions = get_glossary_definitions(legal_doc)
    articles = extract_articles_flat(legal_doc)
    
    inconsistencies: List[Dict[str, Any]] = []
    all_terms_used: Dict[str, List[str]] = {}  # term → [article_ids yang menggunakannya]
    
    # Cari semua penggunaan istilah terdefinisi di luar Pasal 1
    for art in articles:
        if art.get("number") == 1:
            continue
        text = art.get("raw_text", "").lower()
        for term, defn in definitions.items():
            if term.lower() in text:
                all_terms_used.setdefault(term, []).append(art["article_id"])
    
    # Cari variasi penulisan yang berbeda (misal: Pemerintah Daerah vs Pemda)
    # Aturan: setiap istilah dalam Ketentuan Umum harus digunakan persis (case-sensitive check)
    for art in articles:
        if art.get("number") == 1:
            continue
        raw = art.get("raw_text", "")
        for term, defn in definitions.items():
            # Cari variasi huruf kapital yang tidak konsisten
            variations = re.findall(rf'\b{re.escape(term)}\b', raw, re.IGNORECASE)
            for v in variations:
                if v != term and v.lower() == term.lower():
                    inconsistencies.append({
                        "article_id": art["article_id"],
                        "term": term,
                        "used_as": v,
                        "context": raw[max(0, raw.find(v)-30):raw.find(v)+len(v)+30],
                        "suggestion": f"Gunakan penulisan baku: '{term}' (sesuai Pasal 1)"
                    })
    
    return {
        "definitions": definitions,
        "total_defined_terms": len(definitions),
        "terms_usage_map": all_terms_used,
        "inconsistencies": inconsistencies,
        "total_inconsistencies": len(inconsistencies)
    }


def validate_cross_references(legal_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validasi bahwa seluruh rujukan silang dalam dokumen masih valid (P2-04).
    Mengidentifikasi "dangling references" setelah operasi transformasi Pilar 1.
    
    Returns:
        List of invalid references: [{source, target, reason}]
    """
    articles = extract_articles_flat(legal_doc)
    valid_ids = {a["article_id"] for a in articles}
    
    dangling_refs: List[Dict[str, Any]] = []
    
    for cr in legal_doc.get("cross_references", []):
        if cr["source_article"] not in valid_ids:
            dangling_refs.append({
                "source": cr["source_article"],
                "target": cr["target_article"],
                "reason": "Pasal sumber (source) tidak lagi ada di dokumen"
            })
        if cr["target_article"] not in valid_ids:
            dangling_refs.append({
                "source": cr["source_article"],
                "target": cr["target_article"],
                "reason": f"Pasal target '{cr['target_article']}' tidak lagi ada (mungkin telah dihapus atau direname)"
            })
    
    return dangling_refs


def check_legal_style_guide(legal_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validasi format penulisan sesuai Lampiran I & II UU 12/2011 (P2-06).
    Memeriksa: format pasal, ayat, huruf, sistematika bab.
    
    Returns:
        List of style violations [{article_id, violation, recommendation}]
    """
    findings: List[Dict[str, Any]] = []
    articles = extract_articles_flat(legal_doc)
    
    for art in articles:
        text = art.get("raw_text", "")
        art_id = art["article_id"]
        
        # Cek style violations
        for pattern, desc, recom in STYLE_VIOLATIONS:
            if re.search(pattern, text):
                findings.append({
                    "article_id": art_id,
                    "violation": desc,
                    "recommendation": recom,
                    "finding_type": "STYLE_GUIDE_UU12_2011"
                })
        
        # Cek penomoran ayat: harus (1), (2), (3) — bukan (a), (b)
        ayat_alpha = re.findall(r'\([a-z]\)', text)
        if ayat_alpha:
            findings.append({
                "article_id": art_id,
                "violation": "Ayat menggunakan huruf (a), (b), bukan (1), (2)",
                "recommendation": "Gunakan angka (1), (2), ... untuk ayat. Gunakan huruf a., b., ... untuk butir.",
                "finding_type": "STYLE_GUIDE_PENOMORAN_AYAT"
            })
    
    # Cek sistematika struktur bab
    chapters = legal_doc.get("body", {}).get("chapters", [])
    has_ketentuan_umum = any(c.get("chapter_type") == "KETENTUAN_UMUM" for c in chapters)
    has_ketentuan_penutup = any(c.get("chapter_type") == "KETENTUAN_PENUTUP" for c in chapters)
    
    if not has_ketentuan_umum:
        findings.append({
            "article_id": "DOKUMEN",
            "violation": "Tidak ada Bab Ketentuan Umum (Pasal 1 definisi)",
            "recommendation": "Tambahkan BAB I Ketentuan Umum berisi definisi istilah kunci",
            "finding_type": "STYLE_GUIDE_SISTEMATIKA_BAB"
        })
    if not has_ketentuan_penutup:
        findings.append({
            "article_id": "DOKUMEN",
            "violation": "Tidak ada Bab Ketentuan Penutup",
            "recommendation": "Tambahkan bab penutup berisi pasal pemberlakuan regulasi",
            "finding_type": "STYLE_GUIDE_SISTEMATIKA_BAB"
        })
    
    return findings


def run_full_editorial_audit(legal_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Menjalankan seluruh pemeriksaan Pilar 2 sekaligus (P2-01 s.d. P2-06).
    
    Returns:
        Laporan editorial lengkap siap ditampilkan di MCP Tool atau Dashboard.
    """
    puebi_issues = check_puebi_compliance(legal_doc)
    typo_issues = check_typo_and_redundancy(legal_doc)
    glossary_report = harmonize_glossary(legal_doc)
    xref_issues = validate_cross_references(legal_doc)
    style_issues = check_legal_style_guide(legal_doc)
    
    total_issues = len(puebi_issues) + len(typo_issues) + len(glossary_report.get("inconsistencies", [])) + len(xref_issues) + len(style_issues)
    
    return {
        "total_issues": total_issues,
        "severity": "HIGH" if total_issues > 10 else ("MEDIUM" if total_issues > 3 else "LOW"),
        "puebi_compliance": {
            "total": len(puebi_issues),
            "findings": puebi_issues
        },
        "typo_redundancy": {
            "total": len(typo_issues),
            "findings": typo_issues
        },
        "glossary_harmonization": glossary_report,
        "cross_reference_validation": {
            "total_dangling": len(xref_issues),
            "dangling_refs": xref_issues
        },
        "legal_style_guide": {
            "total": len(style_issues),
            "findings": style_issues
        }
    }
