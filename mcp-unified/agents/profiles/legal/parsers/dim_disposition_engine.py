"""
dim_disposition_engine.py — Pilar 6: Policy Disposition Matrix Engine (Subtask 131-I)
======================================================================================
Engine manajemen matriks disposisi DIM (Daftar Inventarisasi Masalah) per pasal.

Disposisi DIM yang didukung (Taksonomi 7 Pilar v2.0 — Pilar 6):
1. APPROVED         — Pasal disetujui tanpa perubahan
2. PARKING_LOT      — Isu ditunda, perlu pembahasan lebih lanjut
3. ENCLAVE          — Isu dikeluarkan dari cakupan (kelola terpisah)
4. ALTERNATIVE_VEHICLE — Diusulkan melalui instrumen hukum berbeda
5. OUT_OF_SCOPE     — Di luar cakupan regulasi ini
6. FUTURE_AGENDA    — Ditunda untuk agenda pembahasan mendatang

Fitur tambahan (P6-06):
- Justification Writer: Generate argumentasi yuridis per disposisi
- DIM Table Formatter: Output format tabel DIM siap cetak

Digunakan oleh: legal_tools.py → legal_disposition_matrix()
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from .legal_ast_parser import extract_articles_flat


# ─── Konstanta ────────────────────────────────────────────────────────────────

VALID_DISPOSITIONS = {
    "APPROVED", "PARKING_LOT", "ENCLAVE",
    "ALTERNATIVE_VEHICLE", "OUT_OF_SCOPE", "FUTURE_AGENDA"
}

DISPOSITION_LABELS = {
    "APPROVED": "✅ Disetujui",
    "PARKING_LOT": "⏸️ Ditunda (Parking Lot)",
    "ENCLAVE": "🔒 Enklave (Kelola Terpisah)",
    "ALTERNATIVE_VEHICLE": "🔀 Kendaraan Hukum Alternatif",
    "OUT_OF_SCOPE": "❌ Di Luar Cakupan",
    "FUTURE_AGENDA": "📅 Agenda Mendatang",
}

# Template justifikasi hukum otomatis per disposisi
JUSTIFICATION_TEMPLATES = {
    "APPROVED": (
        "Norma Pasal {label} telah memenuhi persyaratan substantif dan formal. "
        "Materi muatan sesuai dengan delegasi wewenang dari {parent_ref} "
        "dan tidak berpotensi menimbulkan konflik norma vertikal maupun horizontal."
    ),
    "PARKING_LOT": (
        "Norma Pasal {label} masih memerlukan kajian lebih mendalam, khususnya terkait: "
        "{issue_summary}. Pembahasan ditunda hingga tersedia data/regulasi pendukung yang memadai."
    ),
    "ENCLAVE": (
        "Substansi Pasal {label} yang mengatur tentang {issue_summary} "
        "bersifat terlalu teknis/khusus dan lebih tepat diatur dalam instrumen terpisah "
        "(Peraturan Kepala Satuan Kerja / Petunjuk Teknis / SOP) "
        "guna menjaga kohesivitas dan kejelasan rumusan regulasi induk."
    ),
    "ALTERNATIVE_VEHICLE": (
        "Substansi Pasal {label} berkenaan dengan {issue_summary} "
        "lebih tepat dituangkan dalam {alt_vehicle} "
        "mengingat cakupan kewenangan dan materi muatan yang lebih sesuai "
        "dengan jenis instrumen hukum dimaksud."
    ),
    "OUT_OF_SCOPE": (
        "Substansi Pasal {label} yang mengatur tentang {issue_summary} "
        "berada di luar cakupan substansi regulasi ini. "
        "Materi tersebut merupakan kewenangan/ranah {responsible_kl} "
        "berdasarkan {legal_basis}."
    ),
    "FUTURE_AGENDA": (
        "Norma Pasal {label} tentang {issue_summary} diakui relevansinya, "
        "namun kondisi politik hukum saat ini belum memungkinkan penetapan. "
        "Direkomendasikan masuk Program Pembentukan Peraturan (Prolegda/Prolegnas) "
        "periode {target_period}."
    ),
}


# ─── Core Functions ───────────────────────────────────────────────────────────

def set_article_disposition(
    legal_doc: Dict[str, Any],
    article_id: str,
    disposition: str,
    issue_summary: str = "",
    reviewer: str = "Legal Agent",
    alt_vehicle: str = "",
    responsible_kl: str = "",
    legal_basis: str = "",
    target_period: str = "",
    parent_ref: str = "regulasi induk"
) -> Dict[str, Any]:
    """
    Menetapkan disposisi DIM pada satu pasal tertentu dan menghasilkan justifikasi yuridis.
    
    Args:
        legal_doc: Dokumen legal parsed
        article_id: ID pasal (e.g., 'PASAL_7')
        disposition: Jenis disposisi (salah satu dari VALID_DISPOSITIONS)
        issue_summary: Uraian singkat isu/masalah
        reviewer: Nama reviewer
        alt_vehicle, responsible_kl, legal_basis, target_period: Konteks disposisi spesifik
        parent_ref: Rujukan regulasi induk untuk APPROVED template
    Returns:
        Dict berisi artikel yang telah diberi disposisi + justifikasi yuridis
    """
    import copy
    
    if disposition not in VALID_DISPOSITIONS:
        return {
            "success": False,
            "error": f"Disposisi tidak valid: '{disposition}'. Pilihan: {sorted(VALID_DISPOSITIONS)}"
        }
    
    doc = copy.deepcopy(legal_doc)
    articles = extract_articles_flat(doc)
    
    target_art = None
    for art in articles:
        if art["article_id"] == article_id:
            target_art = art
            break
    
    if not target_art:
        return {"success": False, "error": f"Pasal {article_id} tidak ditemukan"}
    
    # Generate justifikasi yuridis otomatis
    template = JUSTIFICATION_TEMPLATES.get(disposition, "")
    justification = template.format(
        label=target_art.get("number_label", article_id),
        issue_summary=issue_summary or "substansi yang bersangkutan",
        alt_vehicle=alt_vehicle or "instrumen hukum yang lebih tepat",
        responsible_kl=responsible_kl or "instansi yang berwenang",
        legal_basis=legal_basis or "ketentuan peraturan perundang-undangan yang berlaku",
        target_period=target_period or "Prolegda tahun berikutnya",
        parent_ref=parent_ref
    )
    
    # Update pasal
    target_art["dim_disposition"] = disposition
    target_art["dim_justification"] = justification
    
    # Buat entri DIM
    dim_entry = {
        "article_id": article_id,
        "article_label": target_art.get("number_label", article_id),
        "dim_action": target_art.get("dim_action", "AS_IS"),
        "disposition": disposition,
        "disposition_label": DISPOSITION_LABELS[disposition],
        "issue_summary": issue_summary,
        "legal_basis": legal_basis,
        "justification": justification,
        "proposed_text": target_art.get("raw_text", "")[:500],
        "reviewer": reviewer,
        "review_date": datetime.now().strftime("%Y-%m-%d")
    }
    
    # Update atau tambahkan ke dim_matrix
    existing_entries = [e for e in doc.get("dim_matrix", []) if e["article_id"] != article_id]
    existing_entries.append(dim_entry)
    doc["dim_matrix"] = existing_entries
    
    return {
        "success": True,
        "article_id": article_id,
        "disposition": disposition,
        "disposition_label": DISPOSITION_LABELS[disposition],
        "justification": justification,
        "dim_entry": dim_entry,
        "doc": doc
    }


def batch_set_dispositions(
    legal_doc: Dict[str, Any],
    disposition_list: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Menetapkan disposisi DIM untuk banyak pasal sekaligus (batch operation).
    
    Args:
        legal_doc: Dokumen legal parsed
        disposition_list: List of {"article_id", "disposition", "issue_summary", ...}
    Returns:
        Dict berisi dokumen yang telah diperbarui + summary
    """
    import copy
    doc = copy.deepcopy(legal_doc)
    results = []
    errors = []
    
    for item in disposition_list:
        result = set_article_disposition(
            legal_doc=doc,
            article_id=item.get("article_id", ""),
            disposition=item.get("disposition", "APPROVED"),
            issue_summary=item.get("issue_summary", ""),
            reviewer=item.get("reviewer", "Legal Agent"),
            alt_vehicle=item.get("alt_vehicle", ""),
            responsible_kl=item.get("responsible_kl", ""),
            legal_basis=item.get("legal_basis", ""),
            target_period=item.get("target_period", ""),
            parent_ref=item.get("parent_ref", "regulasi induk")
        )
        if result.get("success"):
            doc = result["doc"]  # Propagate changes
            results.append(result["dim_entry"])
        else:
            errors.append({"article_id": item.get("article_id"), "error": result.get("error")})
    
    return {
        "success": True,
        "total_processed": len(results),
        "total_errors": len(errors),
        "dim_entries": results,
        "errors": errors,
        "doc": doc
    }


def get_dim_summary(legal_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Menghasilkan ringkasan statistik DIM per jenis disposisi.
    """
    articles = extract_articles_flat(legal_doc)
    summary: Dict[str, int] = {d: 0 for d in VALID_DISPOSITIONS}
    summary["PENDING_REVIEW"] = 0
    
    for art in articles:
        disp = art.get("dim_disposition") or "PENDING_REVIEW"
        if disp in summary:
            summary[disp] += 1
        else:
            summary["PENDING_REVIEW"] += 1
    
    return {
        "total_articles": len(articles),
        "disposition_counts": summary,
        "completion_rate": round(
            (len(articles) - summary["PENDING_REVIEW"]) / max(len(articles), 1) * 100, 1
        )
    }


def format_dim_table_markdown(legal_doc: Dict[str, Any]) -> str:
    """
    Menghasilkan tabel DIM dalam format Markdown siap cetak / dipresentasikan.
    Format standar DPR/DPD RI untuk Pembahasan RUU.
    """
    dim_matrix = legal_doc.get("dim_matrix", [])
    if not dim_matrix:
        return "_Tabel DIM kosong — belum ada disposisi yang ditetapkan._"
    
    header = (
        "| No | Pasal/Ayat | Aksi DIM | Disposisi | Ringkasan Isu | Argumentasi Yuridis | Reviewer |\n"
        "|----|-----------:|:--------:|:---------:|---------------|---------------------|----------|\n"
    )
    rows = []
    for i, entry in enumerate(dim_matrix, start=1):
        rows.append(
            f"| {i} "
            f"| {entry.get('article_label', '-')} "
            f"| {entry.get('dim_action', 'AS_IS')} "
            f"| {entry.get('disposition_label', '-')} "
            f"| {(entry.get('issue_summary') or '-')[:80]} "
            f"| {(entry.get('justification') or '-')[:120]}... "
            f"| {entry.get('reviewer', 'Legal Agent')} |"
        )
    
    return f"## 📋 Tabel DIM (Daftar Inventarisasi Masalah)\n\n{header}" + "\n".join(rows)
