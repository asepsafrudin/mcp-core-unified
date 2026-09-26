"""
jurisdiction_analyzer.py — Pilar 4: Portfolio Boundary & Joint Regulation Analyzer (Subtask 131-G)
====================================================================================================
Analisis batas kewenangan portofolio antar-Kementerian/Lembaga (K/L) dan
generator kerangka draf Peraturan Bersama (SKB/Permenko/Joint Decree).

Fitur:
1. Portfolio Boundary Analysis — Deteksi irisan kewenangan antar-K/L (P4-01)
2. Joint Regulation Drafter   — Generate matriks kewenangan & template SKB (P4-02)
3. Vertical SOP Alignment     — Validasi keselarasan SOP pusat-daerah (P4-03)

Referensi:
- UU No. 39/2008 tentang Kementerian Negara
- Perpres SOTK (Susunan Organisasi dan Tata Kerja) masing-masing K/L
- UU No. 23/2014 tentang Pemerintahan Daerah (Pembagian Urusan Konkuren)

Digunakan oleh: legal_tools.py → legal_verify_jurisdiction()
"""

import re
from typing import Dict, Any, List, Optional, Tuple


# ─── Katalog Urusan Pemerintahan (UU 23/2014) ─────────────────────────────────

# Pemetaan urusan pemerintahan konkuren → K/L leading sector
URUSAN_KL_MAP: Dict[str, Dict[str, Any]] = {
    "pendidikan": {
        "leading_kl": "Kemendikbudristek",
        "co_kl": ["Kemendagri (Pemda)", "Kemenag"],
        "legal_basis": "UU 23/2014 Lampiran Urusan Pendidikan",
        "level_pusat": ["standar nasional", "kurikulum nasional", "sertifikasi guru"],
        "level_daerah": ["pengelolaan SD/SMP/SMA", "guru ASN daerah"]
    },
    "kesehatan": {
        "leading_kl": "Kemenkes",
        "co_kl": ["Kemendagri (Pemda)", "BPOM"],
        "legal_basis": "UU 23/2014 Lampiran Urusan Kesehatan",
        "level_pusat": ["standar pelayanan kesehatan", "RS kelas A", "obat nasional"],
        "level_daerah": ["RS kelas B/C/D", "Puskesmas", "tenaga kesehatan daerah"]
    },
    "pekerjaan_umum": {
        "leading_kl": "PUPR",
        "co_kl": ["Kemendagri (Pemda)", "KLHK"],
        "legal_basis": "UU 23/2014 Lampiran Urusan PU",
        "level_pusat": ["jalan nasional", "bendungan nasional", "air minum IKK"],
        "level_daerah": ["jalan kabupaten/kota", "drainase", "sanitasi"]
    },
    "perumahan": {
        "leading_kl": "Kemenpera / PUPR",
        "co_kl": ["Kemendagri (Pemda)", "BPN"],
        "legal_basis": "UU 23/2014 Lampiran Urusan Perumahan",
        "level_pusat": ["kawasan permukiman kumuh >15 ha", "PSU nasional"],
        "level_daerah": ["kawasan kumuh <15 ha", "rumah susun daerah"]
    },
    "pemberdayaan_masyarakat_desa": {
        "leading_kl": "Kemendesa PDTT",
        "co_kl": ["Kemendagri", "Kemenkeu (DAD/ADD)"],
        "legal_basis": "UU 6/2014 tentang Desa; UU 23/2014",
        "level_pusat": ["kebijakan ADD/Dana Desa", "BUMDes nasional"],
        "level_daerah": ["ADD kabupaten", "pendampingan desa", "musrenbangdes"]
    },
    "lingkungan_hidup": {
        "leading_kl": "KLHK",
        "co_kl": ["Kemendagri (Pemda)", "KKP"],
        "legal_basis": "UU 23/2014 Lampiran Urusan LH; UU 32/2009",
        "level_pusat": ["AMDAL nasional strategis", "perizinan berusaha KLHK"],
        "level_daerah": ["SPPL", "UKL-UPL daerah", "taman kota"]
    },
    "ketenteraman_ketertiban_perlindungan": {
        "leading_kl": "Kemendagri",
        "co_kl": ["Polri", "BNPB"],
        "legal_basis": "UU 23/2014 Lampiran Trantibumlinmas",
        "level_pusat": ["kebijakan nasional Trantibumlinmas"],
        "level_daerah": ["Satpol PP", "Linmas", "pemadam kebakaran"]
    },
    "keuangan_daerah": {
        "leading_kl": "Kemenkeu",
        "co_kl": ["Kemendagri", "BPKP"],
        "legal_basis": "UU 1/2022 HKPD; UU 17/2003",
        "level_pusat": ["DAU", "DAK", "DBH", "TKDD nasional"],
        "level_daerah": ["APBD", "PAD", "Pinjaman Daerah"]
    },
}


# ─── Portfolio Boundary Analysis ──────────────────────────────────────────────

def detect_portfolio_overlap(
    regulation_text: str,
    primary_kl: str,
    instrument_type: str = "PERDA_KABKOTA"
) -> Dict[str, Any]:
    """
    PILAR 4 — Deteksi irisan kewenangan dengan K/L lain (P4-01).
    
    Menganalisis apakah substansi regulasi menyentuh portofolio K/L lain
    yang tidak disebut sebagai leading sector.
    
    Args:
        regulation_text: Teks lengkap regulasi
        primary_kl: K/L yang menerbitkan regulasi ini
        instrument_type: Jenis instrumen
    Returns:
        Dict dengan overlap_findings dan rekomendasi koordinasi
    """
    text_lower = regulation_text.lower()
    overlaps: List[Dict[str, Any]] = []
    touched_urusan: List[str] = []
    
    # Deteksi urusan yang disinggung dalam regulasi
    for urusan, info in URUSAN_KL_MAP.items():
        # Cek apakah kata kunci urusan muncul dalam teks
        urusan_keywords = [urusan.replace("_", " "), urusan.replace("_", "")]
        for kw in urusan_keywords:
            if kw in text_lower:
                touched_urusan.append(urusan)
                
                # Jika leading KL bukan primary_kl → overlap
                leading = info["leading_kl"].lower()
                if primary_kl.lower() not in leading and not any(
                    primary_kl.lower() in co.lower() for co in info["co_kl"]
                ):
                    overlaps.append({
                        "urusan": urusan,
                        "primary_kl": primary_kl,
                        "leading_kl": info["leading_kl"],
                        "co_kl": info["co_kl"],
                        "legal_basis": info["legal_basis"],
                        "severity": "HIGH",
                        "finding": f"Regulasi dari '{primary_kl}' menyentuh urusan '{urusan}' yang merupakan portofolio utama '{info['leading_kl']}'",
                        "recommendation": f"Koordinasikan dengan {info['leading_kl']} dan pertimbangkan penerbitan SKB atau sinkronisasi kebijakan"
                    })
                break
    
    return {
        "primary_kl": primary_kl,
        "instrument_type": instrument_type,
        "touched_urusan": touched_urusan,
        "total_overlaps": len(overlaps),
        "has_portfolio_conflict": len(overlaps) > 0,
        "overlap_findings": overlaps,
        "coordination_recommended": len(overlaps) > 0
    }


def generate_skb_framework(
    regulation_title: str,
    subject_matter: str,
    participating_kl: List[str],
    legal_basis_list: Optional[List[str]] = None,
    target_year: int = 2026
) -> Dict[str, Any]:
    """
    PILAR 4 — Generator kerangka draf Peraturan Bersama/SKB (P4-02).
    
    Menghasilkan template draf SKB dengan matriks kewenangan antar-K/L.
    
    Args:
        regulation_title: Judul substansi yang akan diatur bersama
        subject_matter: Pokok pengaturan (deskripsi singkat)
        participating_kl: Daftar K/L yang ikut serta
        legal_basis_list: Daftar dasar hukum
        target_year: Tahun target penetapan
    Returns:
        Dict dengan template SKB dan matriks kewenangan
    """
    # Validasi: SKB minimal 2 K/L
    if len(participating_kl) < 2:
        return {
            "success": False,
            "error": "SKB memerlukan minimal 2 Kementerian/Lembaga"
        }
    
    # Bangun matriks kewenangan per urusan yang relevan
    authority_matrix: List[Dict[str, Any]] = []
    
    for kl in participating_kl:
        kl_lower = kl.lower()
        kl_authorities = []
        
        for urusan, info in URUSAN_KL_MAP.items():
            if kl_lower in info["leading_kl"].lower():
                kl_authorities.extend(info["level_pusat"])
            elif any(kl_lower in co.lower() for co in info["co_kl"]):
                kl_authorities.extend(info["level_daerah"])
        
        authority_matrix.append({
            "kementerian": kl,
            "peran": "Koordinator" if kl == participating_kl[0] else "Pelaksana",
            "kewenangan_utama": kl_authorities[:5] if kl_authorities else ["Sesuai SOTK masing-masing"],
            "penandatangan": f"Menteri / Kepala {kl}"
        })
    
    # Generate template draf SKB
    pihak_list = "\n".join([
        f"  {i+1}. Menteri {kl}{',' if i < len(participating_kl)-1 else ';'}"
        for i, kl in enumerate(participating_kl)
    ])
    
    legal_basis_text = "\n".join([f"  {i+3}. {lb};" for i, lb in enumerate(legal_basis_list or [])])
    
    skb_template = f"""PERATURAN BERSAMA
{chr(10).join([f"MENTERI {kl.upper()}" for kl in participating_kl])}

NOMOR : [NOMOR-{participating_kl[0].upper()[:3]}]/{target_year}
NOMOR : [NOMOR-{participating_kl[1].upper()[:3] if len(participating_kl) > 1 else 'XX'}]/{target_year}

TENTANG
{regulation_title.upper()}

DENGAN RAHMAT TUHAN YANG MAHA ESA

{chr(10).join([f"MENTERI {kl.upper()}," for kl in participating_kl])}

Menimbang:
  a. bahwa {subject_matter};
  b. bahwa koordinasi antar kementerian diperlukan untuk efektivitas pelaksanaan;
  c. bahwa berdasarkan pertimbangan sebagaimana dimaksud dalam huruf a dan huruf b,
     perlu menetapkan Peraturan Bersama tentang {regulation_title};

Mengingat:
  1. Undang-Undang Nomor 39 Tahun 2008 tentang Kementerian Negara;
  2. Undang-Undang Nomor 23 Tahun 2014 tentang Pemerintahan Daerah;
{legal_basis_text}

MEMUTUSKAN:
Menetapkan: PERATURAN BERSAMA TENTANG {regulation_title.upper()}

BAB I — KETENTUAN UMUM
Pasal 1
[Definisi dan istilah yang digunakan]

BAB II — MAKSUD, TUJUAN, DAN RUANG LINGKUP
Pasal 2
[Maksud dan tujuan peraturan bersama]

BAB III — PEMBAGIAN KEWENANGAN
Pasal 3
Pembagian kewenangan antar pihak sebagaimana diatur dalam Lampiran I Peraturan Bersama ini.

BAB IV — MEKANISME KOORDINASI
Pasal 4
[Tim Koordinasi, rapat berkala, pelaporan]

BAB V — PEMBIAYAAN
Pasal 5
Pembiayaan pelaksanaan Peraturan Bersama ini dibebankan pada DIPA masing-masing Kementerian.

BAB VI — KETENTUAN PENUTUP
Pasal 6
Peraturan Bersama ini mulai berlaku pada tanggal ditandatangani.

[Tempat, Tanggal]
{chr(10).join([f"MENTERI {kl.upper()}" for kl in participating_kl])}
"""
    
    return {
        "success": True,
        "regulation_title": regulation_title,
        "participating_kl": participating_kl,
        "total_parties": len(participating_kl),
        "authority_matrix": authority_matrix,
        "skb_template": skb_template,
        "recommended_legal_basis": [
            "UU No. 39/2008 tentang Kementerian Negara",
            "UU No. 23/2014 tentang Pemerintahan Daerah",
            "PP yang relevan per bidang urusan"
        ],
        "notes": "Template ini adalah kerangka awal. Penyempurnaan substansial diperlukan oleh tim perancang peraturan."
    }


def validate_vertical_sop_alignment(
    local_sop_text: str,
    national_sop_reference: str,
    urusan_type: str = ""
) -> Dict[str, Any]:
    """
    PILAR 4 — Validasi keselarasan SOP daerah dengan SOP/kebijakan pusat (P4-03).
    
    Memeriksa apakah prosedur operasional daerah selaras dengan
    panduan/standar yang ditetapkan pemerintah pusat.
    
    Args:
        local_sop_text: Teks SOP daerah
        national_sop_reference: Teks referensi SOP/kebijakan nasional
        urusan_type: Bidang urusan (e.g., 'kesehatan', 'pendidikan')
    Returns:
        Dict dengan alignment_score dan gap findings
    """
    alignment_score = 100
    gaps: List[Dict[str, Any]] = []
    
    local_lower = local_sop_text.lower()
    national_lower = national_sop_reference.lower()
    
    # Ekstrak frasa kunci dari SOP nasional (sederhana: 5+ kata)
    national_phrases = set(re.findall(r'\b\w{5,}\b', national_lower))
    local_phrases = set(re.findall(r'\b\w{5,}\b', local_lower))
    
    # Cek coverage kata kunci nasional di SOP lokal
    common = national_phrases & local_phrases
    coverage = len(common) / max(len(national_phrases), 1) * 100
    
    if coverage < 30:
        gaps.append({
            "gap_type": "LOW_KEYWORD_COVERAGE",
            "severity": "HIGH",
            "description": f"SOP daerah hanya mencakup {coverage:.0f}% kata kunci dari referensi nasional",
            "recommendation": "Perluas cakupan SOP daerah untuk menyelaraskan dengan standar nasional"
        })
        alignment_score -= 40
    elif coverage < 60:
        gaps.append({
            "gap_type": "MEDIUM_KEYWORD_COVERAGE",
            "severity": "MEDIUM",
            "description": f"SOP daerah mencakup {coverage:.0f}% kata kunci nasional — perlu penguatan",
            "recommendation": "Tambahkan prosedur yang mengacu pada sub-bab standar nasional yang belum tercakup"
        })
        alignment_score -= 20
    
    # Cek keberadaan referensi ke regulasi nasional dalam SOP lokal
    has_national_ref = bool(re.search(
        r'(?:peraturan|peraturan menteri|standar nasional|spm|pedoman nasional)',
        local_lower
    ))
    if not has_national_ref:
        gaps.append({
            "gap_type": "NO_NATIONAL_REFERENCE",
            "severity": "MEDIUM",
            "description": "SOP daerah tidak menyebut/merujuk regulasi atau standar nasional",
            "recommendation": "Tambahkan frasa 'berpedoman pada [Peraturan/Standar Nasional]' di bagian dasar hukum SOP"
        })
        alignment_score -= 15
    
    return {
        "alignment_score": max(0, alignment_score),
        "keyword_coverage_percent": round(coverage, 1),
        "has_national_reference": has_national_ref,
        "urusan_type": urusan_type,
        "is_aligned": alignment_score >= 70,
        "total_gaps": len(gaps),
        "gaps": gaps,
        "verdict": "SELARAS ✅" if alignment_score >= 70 else "PERLU PENYELARASAN ⚠️"
    }
