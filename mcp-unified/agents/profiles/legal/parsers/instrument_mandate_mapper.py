"""
instrument_mandate_mapper.py — Pilar 5 & 7: Mandate Instruments & Closed-Loop Governance
===========================================================================================
Pilar 5: Validasi mandat instrumen digital (SPBE), keterkaitan fiskal (APBD/RKP),
         dan pemetaan standar fasilitas/kapasitas.

Pilar 7: Siklus evaluasi paska-berlaku, pemicu sunset clause, dan closed-loop
         feedback loop otomatis untuk merekomendasikan draft revisi ke Pilar 1.

Subtask 131-H (Pilar 5) dan 131-J (Pilar 7).

Referensi Pilar 5:
- Perpres No. 95/2018 tentang SPBE
- Perpres No. 39/2019 tentang Satu Data Indonesia
- Inpres No. 7/2017 tentang Pengambilan, Pengawasan, dan Pengendalian Pelaksanaan Kebijakan
- APBD/RKP/SIPD sebagai instrumen fiskal

Referensi Pilar 7:
- UU 12/2011 tentang mekanisme evaluasi dan pencabutan
- RIA (Regulatory Impact Assessment) — OECD/Bappenas

Digunakan oleh: legal_tools.py → legal_mandate_check() & legal_governance_loop()
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime, date


# ─── PILAR 5: MANDAT INSTRUMEN ────────────────────────────────────────────────

# Kata kunci mandat digital/SPBE dalam teks regulasi
SPBE_MANDATE_KEYWORDS: List[str] = [
    "sistem elektronik", "sistem informasi", "aplikasi", "portal",
    "digitalisasi", "transformasi digital", "teknologi informasi",
    "basis data", "data terintegrasi", "satu data", "spbe",
    "e-government", "e-service", "online", "daring", "platform"
]

# Kata kunci keterkaitan fiskal APBD/RKP
FISCAL_MANDATE_KEYWORDS: List[str] = [
    "apbd", "apbn", "rkp", "renja", "sipd", "alokasi anggaran",
    "pagu anggaran", "dana alokasi", "hibah", "bantuan keuangan",
    "dana desa", "add", "dad", "pad", "belanja daerah",
    "rencana kerja dan anggaran", "rka", "dpa"
]

# Kata kunci standar kapasitas/fasilitas
FACILITY_STANDARD_KEYWORDS: List[str] = [
    "standar pelayanan minimal", "spm", "standar sarana", "standar prasarana",
    "kapasitas", "fasilitas", "infrastruktur", "laboratorium", "puskesmas",
    "sekolah", "gedung", "peralatan", "logistik"
]

# Perpres SPBE tahun 2018 - mandat utama
SPBE_REFERENCE = "Peraturan Presiden Nomor 95 Tahun 2018 tentang Sistem Pemerintahan Berbasis Elektronik"
SDI_REFERENCE = "Peraturan Presiden Nomor 39 Tahun 2019 tentang Satu Data Indonesia"


def check_spbe_alignment(
    regulation_text: str,
    regulation_title: str = "Regulasi"
) -> Dict[str, Any]:
    """
    PILAR 5 — Validasi keselarasan mandat digital dengan kebijakan SPBE (P5-01).
    
    Mendeteksi apakah regulasi mengandung mandat/amanat digital/sistem elektronik
    dan memvalidasi keselarasannya dengan Perpres SPBE 95/2018.
    
    Returns:
        Dict dengan digital_mandates, alignment_issues, recommendations
    """
    text_lower = regulation_text.lower()
    
    # Deteksi mandat digital
    detected_mandates: List[str] = []
    for kw in SPBE_MANDATE_KEYWORDS:
        if kw in text_lower:
            # Ekstrak konteks kalimat
            for m in re.finditer(re.escape(kw), text_lower):
                start = max(0, m.start() - 50)
                end = min(len(text_lower), m.end() + 100)
                detected_mandates.append(text_lower[start:end].strip())
            break  # Satu contoh per keyword cukup untuk deteksi
    
    has_digital_mandate = len(detected_mandates) > 0
    
    alignment_issues: List[Dict[str, Any]] = []
    
    if has_digital_mandate:
        # Cek apakah ada referensi ke Perpres SPBE
        has_spbe_ref = bool(re.search(r'perpres.*95.*2018|spbe|sistem pemerintahan berbasis elektronik', text_lower))
        has_sdi_ref = bool(re.search(r'perpres.*39.*2019|satu data indonesia', text_lower))
        
        if not has_spbe_ref:
            alignment_issues.append({
                "issue_type": "MISSING_SPBE_REFERENCE",
                "severity": "MEDIUM",
                "description": "Regulasi mengandung mandat digital namun tidak merujuk Perpres SPBE 95/2018",
                "recommendation": f"Tambahkan dasar hukum: '{SPBE_REFERENCE}' dalam bagian Mengingat"
            })
        
        if not has_sdi_ref and "basis data" in text_lower or "data terintegrasi" in text_lower:
            alignment_issues.append({
                "issue_type": "MISSING_SDI_REFERENCE",
                "severity": "LOW",
                "description": "Regulasi mengandung mandat data terintegrasi tanpa merujuk Perpres Satu Data Indonesia 39/2019",
                "recommendation": f"Pertimbangkan tambahkan: '{SDI_REFERENCE}'"
            })
    
    return {
        "has_digital_mandate": has_digital_mandate,
        "digital_mandate_count": len(set(kw for kw in SPBE_MANDATE_KEYWORDS if kw in text_lower)),
        "detected_keywords": [kw for kw in SPBE_MANDATE_KEYWORDS if kw in text_lower],
        "spbe_aligned": has_digital_mandate and not alignment_issues,
        "alignment_issues": alignment_issues,
        "total_issues": len(alignment_issues),
        "recommendation": "Selaraskan mandat digital dengan ekosistem SPBE nasional" if alignment_issues else "Mandat digital sudah selaras atau tidak ditemukan"
    }


def analyze_fiscal_statutory_linkage(
    regulation_text: str,
    regulation_title: str = "Regulasi"
) -> Dict[str, Any]:
    """
    PILAR 5 — Analisis keterkaitan mandat regulasi dengan pembiayaan APBD/RKP (P5-02).
    
    Mengidentifikasi pasal-pasal yang mengandung implikasi pembiayaan dan
    mengevaluasi apakah ada kejelasan sumber anggaran.
    
    Returns:
        Dict dengan fiscal_mandates, budget_clarity_score, recommendations
    """
    text_lower = regulation_text.lower()
    
    # Deteksi kata kunci fiskal
    detected_fiscal: List[str] = [kw for kw in FISCAL_MANDATE_KEYWORDS if kw in text_lower]
    has_fiscal_mandate = len(detected_fiscal) > 0
    
    fiscal_issues: List[Dict[str, Any]] = []
    budget_clarity_score = 100
    
    if has_fiscal_mandate:
        # Cek apakah ada pasal pendanaan eksplisit
        has_pendanaan_chapter = bool(re.search(r'bab.*pendanaan|bab.*pembiayaan|pasal.*pendanaan', text_lower))
        has_apbd_allocation = bool(re.search(r'dibebankan.*apbd|bersumber.*apbd|apbd.*kabupaten|anggaran.*daerah', text_lower))
        has_rka_reference = bool(re.search(r'rka|rencana kerja dan anggaran|dpa.*skpd', text_lower))
        
        if not has_pendanaan_chapter:
            fiscal_issues.append({
                "issue_type": "MISSING_PENDANAAN_CHAPTER",
                "severity": "MEDIUM",
                "description": "Regulasi mengandung mandat yang berimplikasi pembiayaan namun tidak ada bab/pasal Pendanaan",
                "recommendation": "Tambahkan Bab Pendanaan yang menyatakan sumber anggaran secara eksplisit (APBD/DAK/dll)"
            })
            budget_clarity_score -= 30
        
        if not has_apbd_allocation:
            fiscal_issues.append({
                "issue_type": "UNCLEAR_BUDGET_SOURCE",
                "severity": "HIGH",
                "description": "Tidak ada klausul eksplisit tentang sumber pembiayaan (APBD/APBN/DAK)",
                "recommendation": "Tambahkan frasa: 'Pendanaan pelaksanaan Peraturan ini dibebankan pada APBD Kabupaten/Kota'"
            })
            budget_clarity_score -= 40
    
    # Estimasi implikasi SIPD
    has_sipd_implication = bool(re.search(r'sipd|sistem informasi pemerintahan daerah|e-budgeting', text_lower))
    
    return {
        "has_fiscal_mandate": has_fiscal_mandate,
        "detected_fiscal_keywords": detected_fiscal,
        "budget_clarity_score": max(0, budget_clarity_score),
        "has_explicit_pendanaan_chapter": bool(re.search(r'bab.*pendanaan|bab.*pembiayaan', text_lower)),
        "has_explicit_apbd_source": bool(re.search(r'apbd|anggaran.*daerah', text_lower)),
        "has_sipd_implication": has_sipd_implication,
        "fiscal_issues": fiscal_issues,
        "total_issues": len(fiscal_issues),
        "verdict": "JELAS ✅" if budget_clarity_score >= 70 else "PERLU KLARIFIKASI ⚠️"
    }


def map_facility_capacity_standards(
    regulation_text: str,
    urusan_type: str = ""
) -> Dict[str, Any]:
    """
    PILAR 5 — Pemetaan kebutuhan standar fasilitas dan kapasitas (P5-03).
    
    Mengidentifikasi amanat pembangunan/penyediaan fasilitas dan memvalidasi
    apakah ada rujukan ke standar nasional (SNI/SPM/Permen Teknis).
    
    Returns:
        Dict dengan facility_mandates, standard_compliance, gaps
    """
    text_lower = regulation_text.lower()
    
    detected_facilities: List[str] = [kw for kw in FACILITY_STANDARD_KEYWORDS if kw in text_lower]
    has_facility_mandate = len(detected_facilities) > 0
    
    gaps: List[Dict[str, Any]] = []
    
    if has_facility_mandate:
        has_spm_reference = bool(re.search(r'standar pelayanan minimal|spm|peraturan menteri.*standar', text_lower))
        has_sni_reference = bool(re.search(r'standar nasional indonesia|sni', text_lower))
        has_capacity_spec = bool(re.search(r'kapasitas.*\d+|minimal.*\d+.*unit|paling sedikit.*\d+', text_lower))
        
        if not has_spm_reference:
            gaps.append({
                "gap_type": "NO_SPM_REFERENCE",
                "severity": "MEDIUM",
                "description": "Amanat fasilitas/sarana tidak merujuk SPM atau standar nasional",
                "recommendation": "Tambahkan rujukan ke SPM yang relevan (e.g., Permendagri 59/2021 tentang SPM)"
            })
        
        if not has_capacity_spec:
            gaps.append({
                "gap_type": "VAGUE_CAPACITY_SPEC",
                "severity": "LOW",
                "description": "Spesifikasi kapasitas/jumlah fasilitas tidak dinyatakan secara kuantitatif",
                "recommendation": "Tentukan minimal jumlah/kapasitas yang terukur atau rujuk ke lampiran teknis"
            })
    
    return {
        "has_facility_mandate": has_facility_mandate,
        "detected_facility_keywords": detected_facilities,
        "has_spm_reference": bool(re.search(r'spm|standar pelayanan minimal', text_lower)),
        "has_quantified_capacity": bool(re.search(r'\d+\s*(?:unit|buah|orang|meter)', text_lower)),
        "gaps": gaps,
        "total_gaps": len(gaps),
        "verdict": "TERSTANDAR ✅" if not gaps else "PERLU STANDARISASI ⚠️"
    }


# ─── PILAR 7: MONITORING & EVALUASI & CLOSED-LOOP ────────────────────────────

def extract_lifecycle_mandates(legal_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    PILAR 7 — Ekstraksi mandat pemantauan, evaluasi, dan tenggat waktu (P7-01).
    
    Mengidentifikasi:
    - Tenggat waktu penyesuaian (pasal peralihan)
    - Klausul sunset / tanggal kedaluwarsa
    - Amanat monitoring & evaluasi
    - Amanat laporan pelaksanaan
    """
    from .legal_ast_parser import extract_articles_flat
    
    articles = extract_articles_flat(legal_doc)
    lifecycle_findings: List[Dict[str, Any]] = []
    
    # Pattern tenggat waktu
    deadline_pattern = re.compile(
        r'(?:paling lama|paling lambat|dalam waktu|dalam jangka waktu)\s+'
        r'(\d+\s*(?:hari|bulan|tahun))',
        re.IGNORECASE
    )
    # Pattern sunset
    sunset_pattern = re.compile(
        r'(?:berlaku selama|masa berlaku|berakhir pada|tidak berlaku lagi setelah|dicabut'
        r'|masa transisi|penyesuaian.*paling lama)',
        re.IGNORECASE
    )
    # Pattern monitoring
    monitoring_pattern = re.compile(
        r'(?:pemantauan|monitoring|evaluasi|laporan|pelaporan|pengawasan)\s+'
        r'(?:dilakukan|dilaksanakan|disampaikan)',
        re.IGNORECASE
    )
    
    sunset_clauses: List[str] = []
    deadlines: List[Dict[str, Any]] = []
    monitoring_mandates: List[str] = []
    
    for art in articles:
        text = art.get("raw_text", "")
        art_id = art["article_id"]
        
        # Deteksi tenggat waktu
        for m in deadline_pattern.finditer(text):
            deadlines.append({
                "article_id": art_id,
                "deadline": m.group(1),
                "context": text[max(0, m.start()-30):m.end()+80].strip()
            })
        
        # Deteksi sunset clause
        if sunset_pattern.search(text):
            sunset_clauses.append(art_id)
            lifecycle_findings.append({
                "type": "SUNSET_CLAUSE",
                "article_id": art_id,
                "description": f"{art['number_label']} mengandung klausul peralihan/sunset"
            })
        
        # Deteksi mandat monitoring
        if monitoring_pattern.search(text):
            monitoring_mandates.append(art_id)
            lifecycle_findings.append({
                "type": "MONITORING_MANDATE",
                "article_id": art_id,
                "description": f"{art['number_label']} mewajibkan pemantauan/evaluasi"
            })
    
    return {
        "total_deadlines": len(deadlines),
        "deadlines": deadlines,
        "sunset_clause_articles": sunset_clauses,
        "has_sunset_provision": len(sunset_clauses) > 0,
        "monitoring_mandate_articles": monitoring_mandates,
        "has_monitoring_mandate": len(monitoring_mandates) > 0,
        "lifecycle_findings": lifecycle_findings,
        "compliance_check_recommended": len(deadlines) > 0
    }


def detect_sunset_trigger(legal_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    PILAR 7 — Deteksi pemicu review/sunset clause (P7-04).
    
    Mengevaluasi apakah regulasi perlu di-review berdasarkan:
    1. Tenggat waktu yang sudah lewat
    2. Keberadaan regulasi superior baru
    3. Perubahan kondisi sosiologis/fiskal
    """
    lifecycle = extract_lifecycle_mandates(legal_doc)
    
    promulgation = legal_doc.get("promulgation_date")
    year = legal_doc.get("year", 0) or 0
    current_year = datetime.now().year
    
    triggers: List[Dict[str, Any]] = []
    
    # Trigger 1: Regulasi > 5 tahun tanpa evaluasi
    if year and (current_year - year) >= 5:
        triggers.append({
            "trigger_type": "AGE_THRESHOLD",
            "severity": "MEDIUM",
            "description": f"Regulasi berusia {current_year - year} tahun. Evaluasi berkala direkomendasikan (≥5 tahun)",
            "recommendation": "Lakukan Ex-Post Evaluation untuk menilai efektivitas implementasi"
        })
    
    # Trigger 2: Regulasi tidak punya klausul evaluasi/monitoring
    if not lifecycle["has_monitoring_mandate"]:
        triggers.append({
            "trigger_type": "NO_MONITORING_MANDATE",
            "severity": "LOW",
            "description": "Tidak ada pasal yang mewajibkan pemantauan/evaluasi berkala",
            "recommendation": "Tambahkan pasal pemantauan dalam revisi mendatang"
        })
    
    # Trigger 3: Tenggat waktu peralihan yang sudah lewat
    for dl in lifecycle["deadlines"]:
        # Sederhana: jika menyebut "1 tahun" atau "2 tahun" dan regulasi sudah >2 tahun
        num_match = re.search(r'(\d+)\s*tahun', dl["deadline"])
        if num_match and year:
            deadline_years = int(num_match.group(1))
            if (current_year - year) > deadline_years:
                triggers.append({
                    "trigger_type": "DEADLINE_OVERDUE",
                    "severity": "HIGH",
                    "description": f"Tenggat waktu '{dl['deadline']}' di {dl['article_id']} kemungkinan sudah lewat (regulasi tahun {year})",
                    "recommendation": "Verifikasi status pemenuhan kewajiban pasal ini dan pertimbangkan revisi/pencabutan"
                })
    
    review_urgency = "HIGH" if any(t["severity"] == "HIGH" for t in triggers) else \
                    ("MEDIUM" if triggers else "LOW")
    
    return {
        "needs_review": len(triggers) > 0,
        "review_urgency": review_urgency,
        "total_triggers": len(triggers),
        "triggers": triggers,
        "regulation_age_years": current_year - year if year else None,
        "lifecycle_data": lifecycle,
        "verdict": "PERLU REVIEW SEGERA 🔴" if review_urgency == "HIGH" else
                   ("JADWALKAN REVIEW ⚠️" if triggers else "TIDAK ADA PEMICU REVIEW ✅")
    }


def generate_closed_loop_revision(
    legal_doc: Dict[str, Any],
    compliance_issues: Optional[List[Dict[str, Any]]] = None,
    ex_post_findings: Optional[List[str]] = None,
    max_iterations: int = 2,
    current_iteration: int = 1
) -> Dict[str, Any]:
    """
    PILAR 7 — Closed-Loop Feedback Engine (P7-05).
    
    Engine yang menghasilkan rekomendasi draf revisi (Pilar 1) berdasarkan:
    - Temuan ketidakpatuhan (compliance monitoring)
    - Evaluasi dampak paska-berlaku (ex-post RIA+)
    - Pemicu sunset clause
    
    Guardrail: Maksimal 2 iterasi otomatis untuk mencegah infinite revision loop.
    Iterasi ke-3 wajib melalui Human Review.
    
    Args:
        legal_doc: Dokumen yang dievaluasi
        compliance_issues: Temuan audit kepatuhan
        ex_post_findings: Temuan evaluasi dampak lapangan
        max_iterations: Batas iterasi otomatis (default: 2)
        current_iteration: Iterasi saat ini (1-indexed)
    Returns:
        Dict dengan revision_draft atau human_review_flag
    """
    # Guardrail: Cek batas iterasi
    if current_iteration > max_iterations:
        return {
            "action": "HUMAN_REVIEW_REQUIRED",
            "iteration": current_iteration,
            "message": (
                f"Batas iterasi otomatis ({max_iterations}x) telah tercapai. "
                "Revisi selanjutnya WAJIB melalui Human-in-the-Loop Review "
                "oleh tim perancang peraturan sebelum dapat dilanjutkan."
            ),
            "escalation_to": "Tim Hukum / Bagian Peraturan Perundang-undangan",
            "compliance_issues": compliance_issues or [],
            "ex_post_findings": ex_post_findings or []
        }
    
    # Kumpulkan seluruh temuan
    all_issues = list(compliance_issues or []) + [
        {"type": "EX_POST", "description": f} for f in (ex_post_findings or [])
    ]
    
    if not all_issues:
        return {
            "action": "NO_REVISION_NEEDED",
            "message": "Tidak ada temuan yang memerlukan revisi norma",
            "iteration": current_iteration
        }
    
    # Kelompokkan temuan per pasal
    from .legal_ast_parser import extract_articles_flat
    articles = extract_articles_flat(legal_doc)
    
    revision_recommendations: List[Dict[str, Any]] = []
    
    for issue in all_issues:
        related_article = issue.get("article_id", "UMUM")
        issue_desc = issue.get("description", str(issue))
        
        # Tentukan aksi DIM yang direkomendasikan berdasarkan jenis masalah
        if "dihapus" in issue_desc.lower() or "dicabut" in issue_desc.lower():
            recommended_action = "HAPUS"
        elif "ditambah" in issue_desc.lower() or "perlu penambahan" in issue_desc.lower():
            recommended_action = "NORMA_BARU"
        elif "diubah" in issue_desc.lower() or "revisi" in issue_desc.lower():
            recommended_action = "UBAH_SEBAGIAN"
        else:
            recommended_action = "UBAH_SEBAGIAN"
        
        revision_recommendations.append({
            "article_id": related_article,
            "finding_source": issue.get("type", "COMPLIANCE"),
            "issue_description": issue_desc,
            "recommended_dim_action": recommended_action,
            "draft_instruction": f"[AUTO-GENERATED] {recommended_action} {related_article}: {issue_desc[:200]}",
            "requires_human_validation": True  # Selalu wajib divalidasi manusia
        })
    
    return {
        "action": "REVISION_RECOMMENDED",
        "iteration": current_iteration,
        "max_iterations": max_iterations,
        "remaining_auto_iterations": max_iterations - current_iteration,
        "total_recommendations": len(revision_recommendations),
        "revision_recommendations": revision_recommendations,
        "next_step": (
            f"Terapkan {len(revision_recommendations)} rekomendasi ke Pilar 1 (Norm Transformation Engine) "
            f"dengan validasi manusia. Iterasi otomatis tersisa: {max_iterations - current_iteration}."
        ),
        "warning": "SEMUA rekomendasi ini WAJIB divalidasi oleh tim perancang peraturan sebelum diterapkan."
    }


def run_full_governance_audit(
    legal_doc: Dict[str, Any],
    compliance_issues: Optional[List[Dict]] = None,
    ex_post_findings: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Menjalankan seluruh audit Pilar 5 & 7 sekaligus.
    Mengembalikan laporan monitoring & evaluasi lengkap + closed-loop output.
    """
    # Pilar 5
    reg_text = str(legal_doc.get("body", {}))
    spbe = check_spbe_alignment(reg_text, legal_doc.get("title", ""))
    fiscal = analyze_fiscal_statutory_linkage(reg_text, legal_doc.get("title", ""))
    facility = map_facility_capacity_standards(reg_text)
    
    # Pilar 7
    lifecycle = extract_lifecycle_mandates(legal_doc)
    sunset = detect_sunset_trigger(legal_doc)
    closed_loop = generate_closed_loop_revision(legal_doc, compliance_issues, ex_post_findings)
    
    total_issues = (
        spbe["total_issues"] +
        fiscal["total_issues"] +
        facility["total_gaps"] +
        sunset["total_triggers"]
    )
    
    return {
        "total_issues": total_issues,
        "overall_governance_score": max(0, 100 - (total_issues * 10)),
        "pilar_5_spbe": spbe,
        "pilar_5_fiscal": fiscal,
        "pilar_5_facility": facility,
        "pilar_7_lifecycle": lifecycle,
        "pilar_7_sunset_trigger": sunset,
        "pilar_7_closed_loop": closed_loop
    }
