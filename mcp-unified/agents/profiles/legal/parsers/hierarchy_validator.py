"""
hierarchy_validator.py — Pilar 3: Hierarchy Validator & Non-Statutory Classifier (Subtask 131-F)
================================================================================================
Validator kesesuaian hierarki peraturan perundang-undangan berdasarkan UU No. 12 Tahun 2011
jo. UU No. 13 Tahun 2022 tentang Pembentukan Peraturan Perundang-undangan.

Fitur:
1. Hierarchy Validation        — Validasi instrumen vs level hierarki UU 12/2011 (P3-01)
2. Vertical Norm Conflict      — Deteksi konflik vertikal lex superior (P3-02)
3. Non-Statutory Classifier    — Klasifikasi otomatis SE/Juknis/Juklak/Pedoman/SOP (P3-03)
4. Delegation Authority Check  — Validasi kejelasan dasar delegasi pembentukan

Hierarki Peraturan (Pasal 7 UU 12/2011):
  Level 1: UUD NRI 1945
  Level 2: Ketetapan MPR
  Level 3: Undang-Undang / PERPU
  Level 4: Peraturan Pemerintah (PP)
  Level 5: Peraturan Presiden (Perpres)
  Level 6: Peraturan Daerah Provinsi (Perda Prov)
  Level 7: Peraturan Daerah Kabupaten/Kota (Perda Kab/Kota)

Instrumen di luar Pasal 7 (Pasal 8 UU 12/2011):
  Level 8: Peraturan Menteri, Peraturan Kepala Lembaga, Peraturan Kepala Daerah (Perbup/Perwali)
  Level 9: Non-Statutory (SE, Juknis, Juklak, Pedoman, SOP, Instruksi)

Digunakan oleh: legal_tools.py → legal_verify_hierarchy()
"""

import re
from typing import Dict, Any, List, Optional, Tuple


# ─── Konstanta Hierarki ────────────────────────────────────────────────────────

HIERARCHY_MAP: Dict[str, int] = {
    # Pasal 7 UU 12/2011
    "UUD_1945": 1,
    "TAP_MPR": 2,
    "UU": 3,
    "PERPU": 3,
    "PP": 4,
    "PERPRES": 5,
    "PERDA_PROVINSI": 6,
    "PERDA_KABKOTA": 7,
    # Pasal 8 UU 12/2011
    "PERMEN": 8,
    "PERKA": 8,
    "PERBUP": 8,
    "PERWALI": 8,
    # Non-Statutory (Beleidsregels)
    "SE": 9,
    "JUKNIS": 9,
    "JUKLAK": 9,
    "PEDOMAN": 9,
    "SOP": 9,
    "SKB": 8,
    "KEPUTUSAN": 8,
    "INSTRUKSI": 9,
}

HIERARCHY_LABELS: Dict[int, str] = {
    1: "UUD NRI 1945",
    2: "Ketetapan MPR",
    3: "Undang-Undang / PERPU",
    4: "Peraturan Pemerintah",
    5: "Peraturan Presiden",
    6: "Peraturan Daerah Provinsi",
    7: "Peraturan Daerah Kabupaten/Kota",
    8: "Peraturan Menteri / Perbup / Perwali",
    9: "Instrumen Non-Statutory (Beleidsregels)",
}

# Materi muatan yang HANYA bisa diatur dalam UU (tidak boleh di Perda/PP/Perpres)
UU_EXCLUSIVE_MATTERS: List[str] = [
    r'hak asasi manusia',
    r'kewarganegaraan',
    r'pidana penjara',
    r'pidana mati',
    r'anggaran pendapatan dan belanja negara',
    r'pemilihan umum',
    r'tindak pidana',
    r'pembentukan lembaga negara',
]

# Kata kunci penanda instrumen non-statutory dalam teks
NON_STATUTORY_KEYWORDS: Dict[str, List[str]] = {
    "SE": ["surat edaran", "se nomor", "s.e."],
    "JUKNIS": ["petunjuk teknis", "juknis"],
    "JUKLAK": ["petunjuk pelaksanaan", "juklak"],
    "PEDOMAN": ["pedoman", "buku pedoman", "manual"],
    "SOP": ["standar operasional prosedur", "s.o.p.", "sop"],
    "INSTRUKSI": ["instruksi", "instruksi presiden", "inpres", "instruksi gubernur", "instruksi bupati"],
}

# Frasa yang menunjukkan ada delegasi dari regulasi lebih tinggi
DELEGATION_INDICATORS = re.compile(
    r'(?:sesuai dengan|berdasarkan|dalam rangka pelaksanaan|sebagaimana dimaksud dalam)\s+'
    r'((?:Undang-Undang|Peraturan Pemerintah|Peraturan Presiden|Peraturan Menteri)\s+(?:Nomor\s+)?[\d/]+\s+Tahun\s+\d{4})',
    re.IGNORECASE
)


# ─── Non-Statutory Classifier ─────────────────────────────────────────────────

def classify_instrument_type(
    title: str,
    content_sample: str = "",
    declared_type: str = ""
) -> Dict[str, Any]:
    """
    PILAR 3 — Klasifikasi otomatis jenis instrumen hukum (P3-03).
    Mengidentifikasi apakah dokumen bersifat STATUTORY atau NON_STATUTORY (Beleidsregels).
    
    Args:
        title: Judul dokumen (e.g., "Surat Edaran Direktur Jenderal...")
        content_sample: Cuplikan isi dokumen (500 karakter pertama)
        declared_type: Jenis yang diklaim oleh sistem (bisa kosong)
    Returns:
        Dict: {instrument_type, category, level_hierarki, confidence, evidence}
    """
    title_lower = title.lower()
    content_lower = (content_sample or "").lower()
    full_text = f"{title_lower} {content_lower}"
    
    # 1. Deteksi Non-Statutory
    for inst_type, keywords in NON_STATUTORY_KEYWORDS.items():
        for kw in keywords:
            if kw in full_text:
                return {
                    "instrument_type": inst_type,
                    "category": "NON_STATUTORY_BELEIDSREGELS",
                    "level_hierarki": 9,
                    "level_label": HIERARCHY_LABELS[9],
                    "confidence": 0.9,
                    "evidence": f"Terdeteksi kata kunci non-statutory: '{kw}'",
                    "legal_basis": "Pasal 8 ayat (2) UU 12/2011 — instrumen di luar hierarki Pasal 7"
                }
    
    # 2. Deteksi Statutory berdasarkan kata kunci judul
    statutory_patterns: List[Tuple[str, str, int]] = [
        (r'undang.undang|uu\s+nomor', "UU", 3),
        (r'peraturan pemerintah pengganti undang-undang|perpu', "PERPU", 3),
        (r'peraturan pemerintah(?!\s+daerah)(?!\s+provinsi)(?!\s+kabupaten)(?!\s+kota)|pp\s+nomor', "PP", 4),
        (r'peraturan presiden|perpres', "PERPRES", 5),
        (r'peraturan daerah(?:\s+provinsi)?|perda(?:\s+provinsi)?', "PERDA_PROVINSI", 6),
        (r'peraturan daerah(?:\s+kabupaten|\s+kota)|perda(?:\s+kabupaten|\s+kota)', "PERDA_KABKOTA", 7),
        (r'peraturan menteri|permen', "PERMEN", 8),
        (r'peraturan bupati|perbup', "PERBUP", 8),
        (r'peraturan walikota|perwali', "PERWALI", 8),
        (r'peraturan gubernur|pergub', "PERDA_PROVINSI", 8),
        (r'keputusan bupati|sk bupati', "KEPUTUSAN", 8),
        (r'keputusan menteri|kepmen', "KEPUTUSAN", 8),
        (r'peraturan bersama|skb', "SKB", 8),
    ]
    
    for pattern, inst_type, level in statutory_patterns:
        if re.search(pattern, full_text, re.IGNORECASE):
            return {
                "instrument_type": inst_type,
                "category": "STATUTORY" if level <= 8 else "NON_STATUTORY_BELEIDSREGELS",
                "level_hierarki": level,
                "level_label": HIERARCHY_LABELS.get(level, "Unknown"),
                "confidence": 0.85,
                "evidence": f"Terdeteksi pola instrumen statutory: '{pattern}'",
                "legal_basis": "Pasal 7 UU 12/2011" if level <= 7 else "Pasal 8 UU 12/2011"
            }
    
    # 3. Fallback berdasarkan declared_type
    if declared_type:
        level = HIERARCHY_MAP.get(declared_type.upper(), 9)
        return {
            "instrument_type": declared_type.upper(),
            "category": "STATUTORY" if level <= 8 else "NON_STATUTORY_BELEIDSREGELS",
            "level_hierarki": level,
            "level_label": HIERARCHY_LABELS.get(level, "Unknown"),
            "confidence": 0.6,
            "evidence": f"Berdasarkan tipe yang dideklarasikan: '{declared_type}'",
            "legal_basis": "Pasal 7-8 UU 12/2011"
        }
    
    return {
        "instrument_type": "UNKNOWN",
        "category": "UNKNOWN",
        "level_hierarki": 0,
        "level_label": "Tidak Terklasifikasi",
        "confidence": 0.0,
        "evidence": "Tidak ada pola yang cocok ditemukan",
        "legal_basis": ""
    }


# ─── Hierarchy Validation ─────────────────────────────────────────────────────

def validate_hierarchy_compliance(
    instrument_type: str,
    level_hierarki: int,
    parent_delegation: Optional[str] = None,
    preamble_mengingat: Optional[List[Dict]] = None,
    content_sample: str = ""
) -> Dict[str, Any]:
    """
    PILAR 3 — Validasi kesesuaian hierarki UU 12/2011 (P3-01).
    
    Args:
        instrument_type: Jenis instrumen (e.g., 'PERBUP', 'PP')
        level_hierarki: Level yang diklaim dokumen
        parent_delegation: doc_id regulasi induk yang mendelegasikan
        preamble_mengingat: List dasar hukum dari 'Mengingat'
        content_sample: Isi teks untuk cek materi muatan
    Returns:
        Dict: {is_valid, findings, score, recommendations}
    """
    findings: List[Dict[str, Any]] = []
    score = 100  # mulai dari sempurna, kurangi per masalah
    
    expected_level = HIERARCHY_MAP.get(instrument_type.upper(), 0)
    
    # 1. Validasi konsistensi level yang diklaim vs yang seharusnya
    if expected_level > 0 and abs(expected_level - level_hierarki) > 1:
        findings.append({
            "type": "HIERARCHY_MISMATCH",
            "severity": "HIGH",
            "finding": f"Level hierarki yang diklaim ({level_hierarki}) tidak sesuai dengan jenis instrumen '{instrument_type}' (seharusnya level {expected_level})",
            "recommendation": f"Sesuaikan level_hierarki menjadi {expected_level} atau ubah jenis instrumen"
        })
        score -= 30
    
    # 2. Validasi keberadaan dasar delegasi
    has_delegation = False
    if preamble_mengingat:
        for ref in preamble_mengingat:
            ref_text = ref.get("text", "").lower()
            # Cek apakah ada referensi ke peraturan lebih tinggi
            if any(kw in ref_text for kw in ["undang-undang", "peraturan pemerintah", "peraturan presiden"]):
                has_delegation = True
                break
    
    if content_sample:
        delegation_matches = DELEGATION_INDICATORS.findall(content_sample)
        if delegation_matches:
            has_delegation = True
    
    if not has_delegation and level_hierarki >= 6:
        findings.append({
            "type": "MISSING_DELEGATION_BASIS",
            "severity": "MEDIUM",
            "finding": "Tidak ditemukan dasar delegasi eksplisit dari peraturan yang lebih tinggi dalam bagian 'Mengingat'",
            "recommendation": "Tambahkan referensi ke peraturan induk yang mendelegasikan kewenangan pembentukan regulasi ini"
        })
        score -= 20
    
    # 3. Cek materi muatan eksklusif UU
    if level_hierarki > 3 and content_sample:
        content_lower = content_sample.lower()
        for exclusive_matter in UU_EXCLUSIVE_MATTERS:
            if re.search(exclusive_matter, content_lower):
                findings.append({
                    "type": "ULTRA_VIRES_MATERI_MUATAN",
                    "severity": "HIGH",
                    "finding": f"Terdeteksi materi muatan yang seharusnya diatur dalam UU: '{exclusive_matter}'",
                    "recommendation": "Materi muatan ini melampaui kewenangan instrumen ini. Hapus atau rekomendasikan ke pembentukan UU."
                })
                score -= 25
    
    # 4. Validasi Pasal 8 — apakah ada amanat/dasar hukum
    if level_hierarki == 8:
        if not has_delegation:
            findings.append({
                "type": "PASAL_8_NO_AMANAT",
                "severity": "MEDIUM",
                "finding": "Instrumen level 8 (Pasal 8 UU 12/2011) harus memiliki amanat dari peraturan yang lebih tinggi atau berdasarkan kewenangan jabatan",
                "recommendation": "Pastikan ada amanat tertulis dari PP/Perpres/UU yang mendelegasikan kewenangan ini"
            })
            score -= 15
    
    is_valid = score >= 70
    return {
        "is_valid": is_valid,
        "score": max(0, score),
        "instrument_type": instrument_type,
        "level_hierarki": level_hierarki,
        "expected_level": expected_level,
        "level_label": HIERARCHY_LABELS.get(level_hierarki, "Unknown"),
        "has_delegation_basis": has_delegation,
        "total_findings": len(findings),
        "findings": findings,
        "verdict": "VALID ✅" if is_valid else "BERMASALAH ⚠️",
        "recommendation_summary": "; ".join(f["recommendation"] for f in findings) if findings else "Tidak ada catatan perbaikan"
    }


def detect_vertical_norm_conflict(
    child_doc: Dict[str, Any],
    parent_docs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    PILAR 3 — Deteksi konflik norma vertikal (Lex Superior Derogat Legi Inferiori) (P3-02).
    
    Memeriksa apakah materi muatan regulasi anak bertentangan dengan regulasi induk/superior.
    
    Args:
        child_doc: LegalDocument yang diuji (hierarki lebih rendah)
        parent_docs: List LegalDocument yang menjadi acuan (hierarki lebih tinggi)
    Returns:
        Dict: {has_conflict, conflicts, recommendations}
    """
    conflicts: List[Dict[str, Any]] = []
    child_level = child_doc.get("level_hierarki", 9)
    child_title = child_doc.get("title", "Regulasi Anak")
    
    for parent in parent_docs:
        parent_level = parent.get("level_hierarki", 1)
        parent_title = parent.get("title", "Regulasi Induk")
        
        # Hanya cek jika parent benar-benar lebih tinggi
        if parent_level >= child_level:
            continue
        
        # Kumpulkan semua teks pasal anak
        from .legal_ast_parser import extract_articles_flat
        child_articles = extract_articles_flat(child_doc)
        parent_articles = extract_articles_flat(parent)
        
        # Deteksi kewenangan yang diklaim child tapi tidak ada di parent
        for child_art in child_articles:
            child_text = child_art.get("raw_text", "").lower()
            child_norm = child_art.get("norm_type", "")
            
            # Cek klaim kewenangan: apakah ada frasa kewenangan di anak yang tidak didelegasikan parent
            if child_norm in ("KEWENANGAN", "HAK") and "sebagaimana dimaksud" not in child_text:
                # Klaim kewenangan tanpa rujukan ke parent — potensi ultra vires
                conflicts.append({
                    "conflict_type": "POTENTIAL_ULTRA_VIRES",
                    "severity": "MEDIUM",
                    "child_article": child_art["article_id"],
                    "child_text_snippet": child_text[:150],
                    "parent_doc": parent_title,
                    "description": f"Kewenangan di {child_art['number_label']} diklaim tanpa delegasi eksplisit dari '{parent_title}'",
                    "recommendation": "Tambahkan frasa 'sebagaimana dimaksud dalam [Pasal X regulasi induk]' untuk memperkuat dasar kewenangan"
                })
        
        # Deteksi konflik definisi
        from .legal_ast_parser import get_glossary_definitions
        child_defs = get_glossary_definitions(child_doc)
        parent_defs = get_glossary_definitions(parent)
        
        for term, child_defn in child_defs.items():
            if term in parent_defs:
                parent_defn = parent_defs[term]
                # Sederhana: bandingkan panjang substansi (beda signifikan = potensi konflik)
                if abs(len(child_defn) - len(parent_defn)) > 50:
                    conflicts.append({
                        "conflict_type": "DEFINITION_CONFLICT",
                        "severity": "HIGH",
                        "term": term,
                        "child_definition": child_defn[:100],
                        "parent_definition": parent_defn[:100],
                        "parent_doc": parent_title,
                        "description": f"Definisi '{term}' berbeda signifikan antara regulasi anak dan '{parent_title}'",
                        "recommendation": f"Harmoniskan definisi '{term}' dengan definisi dalam '{parent_title}'"
                    })
    
    return {
        "has_conflict": len(conflicts) > 0,
        "total_conflicts": len(conflicts),
        "conflict_risk": "HIGH" if any(c["severity"] == "HIGH" for c in conflicts) else ("MEDIUM" if conflicts else "NONE"),
        "conflicts": conflicts,
        "child_doc_title": child_title,
        "child_level": child_level,
        "parents_checked": [p.get("title", "Unknown") for p in parent_docs]
    }


def run_full_hierarchy_audit(
    legal_doc: Dict[str, Any],
    parent_docs: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Menjalankan audit hirarki lengkap (P3-01 + P3-02 + P3-03).
    """
    # Klasifikasi instrumen
    classification = classify_instrument_type(
        title=legal_doc.get("title", ""),
        content_sample=str(legal_doc.get("body", {}).get("preamble", {}))[:500],
        declared_type=legal_doc.get("instrument_type", "")
    )
    
    # Validasi hierarki
    hierarchy_result = validate_hierarchy_compliance(
        instrument_type=legal_doc.get("instrument_type", "UNKNOWN"),
        level_hierarki=legal_doc.get("level_hierarki", 0),
        preamble_mengingat=legal_doc.get("body", {}).get("preamble", {}).get("mengingat", []),
        content_sample=str(legal_doc.get("body", {}))[:1000]
    )
    
    # Deteksi konflik vertikal (jika ada parent docs)
    conflict_result = None
    if parent_docs:
        conflict_result = detect_vertical_norm_conflict(legal_doc, parent_docs)
    
    overall_valid = hierarchy_result["is_valid"] and (not conflict_result or not conflict_result["has_conflict"])
    
    return {
        "overall_valid": overall_valid,
        "instrument_classification": classification,
        "hierarchy_validation": hierarchy_result,
        "vertical_conflict": conflict_result,
        "pilar_3_score": hierarchy_result["score"],
        "verdict": "VALID ✅" if overall_valid else "PERLU PERBAIKAN ⚠️"
    }
