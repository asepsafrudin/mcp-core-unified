"""
norm_transformation_engine.py — Pilar 1 Norm Transformation Engine (Subtask 131-C & 131-D)
============================================================================================
Engine manipulasi struktural norma hukum dalam dokumen perundang-undangan.

Operasi yang didukung (Taksonomi 7 Pilar DIM v2.0 — Pilar 1):
1. AS_IS           : Pasal tidak berubah
2. UBAH_SEBAGIAN   : Mengubah teks sebagian pasal/ayat  [amendment_mapping()]
3. HAPUS           : Menghapus pasal dan memperbarui DAG [delete_article()]
4. SUBSTITUSI      : Mengganti pasal sepenuhnya          [substitute_article()]
5. NORMA_BARU      : Menyisipkan pasal baru              [insert_article()]
6. PECAH           : Memecah 1 pasal → n pasal           [split_article()]    ★
7. GABUNG          : Menggabungkan n pasal → 1           [merge_articles()]   ★
8. RELOKASI        : Memindahkan & renumber pasal         [relocate_article()] ★

Semua operasi yang mengubah nomor pasal akan OTOMATIS memperbarui:
- Semua cross-references (rujukan silang) di seluruh dokumen
- Blast radius analysis sebelum transformasi

Digunakan oleh:
- legal_tools.py → legal_transform_clause() [tool baru]
- Pilar 6 Disposition Matrix (preview perubahan tanpa commit)
"""

import re
import copy
from typing import Dict, Any, List, Optional, Tuple
from .legal_ast_parser import extract_articles_flat, get_article_by_id


# ─── Cross-Reference DAG Engine ───────────────────────────────────────────────

def build_cross_reference_graph(legal_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Membangun DAG (Directed Acyclic Graph) rujukan silang antar-pasal.
    Melengkapi field 'cross_references', 'references_to', dan 'referenced_by' di setiap pasal.
    
    Returns:
        LegalDocument yang telah diperkaya dengan cross-reference data lengkap.
    """
    from .legal_ast_parser import extract_articles_flat

    doc = copy.deepcopy(legal_doc)
    articles = extract_articles_flat(doc)
    
    # Map article_id → article object
    art_map: Dict[str, Dict] = {a["article_id"]: a for a in articles}
    
    # Reset semua references_to dan referenced_by
    for art in articles:
        art["references_to"] = []
        art["referenced_by"] = []
    
    cross_refs: List[Dict[str, Any]] = []
    
    # Pattern deteksi referensi silang
    ref_pattern = re.compile(
        r'(?:sebagaimana dimaksud(?:\s+dalam)?|diatur(?:\s+dalam)?|berdasarkan(?:\s+ketentuan)?|'
        r'dikecualikan dari|merujuk pada|ketentuan|sesuai dengan)\s+'
        r'(Pasal\s+\d+(?:[A-Za-z])?)'
        r'(?:\s+ayat\s+(\(\d+\)))?'
        r'(?:\s+huruf\s+([a-z]))?',
        re.IGNORECASE
    )
    
    for source_art in articles:
        full_text = source_art.get("raw_text", "")
        # Tambahkan teks semua ayat
        for clause in source_art.get("clauses", []):
            full_text += " " + clause.get("raw_text", "")
        
        seen = set()
        for m in ref_pattern.finditer(full_text):
            target_label = re.sub(r'\s+', ' ', m.group(1).strip()).capitalize()
            target_id = "PASAL_" + re.sub(r'[^0-9A-Z]', '_', target_label.upper().replace("PASAL ", ""))
            
            # Cari article_id yang cocok
            matched_id = None
            for art_id in art_map:
                if art_id == target_id or art_id.replace("PASAL_", "") == target_label.replace("Pasal ", ""):
                    matched_id = art_id
                    break
            
            if matched_id and matched_id != source_art["article_id"] and matched_id not in seen:
                seen.add(matched_id)
                
                # Tentukan jenis referensi
                context = m.group(0).lower()
                if "dikecualikan" in context:
                    ref_type = "EXCEPTION"
                elif "berdasarkan" in context or "sesuai" in context:
                    ref_type = "DELEGATION"
                elif "sebagaimana dimaksud" in context:
                    ref_type = "NORMATIVE_SUBORDINATION"
                elif "diatur" in context:
                    ref_type = "DELEGATION"
                else:
                    ref_type = "GENERAL_REFERENCE"
                
                cross_ref = {
                    "source_article": source_art["article_id"],
                    "target_article": matched_id,
                    "ref_type": ref_type,
                    "context_snippet": m.group(0)[:100]
                }
                cross_refs.append(cross_ref)
                
                # Update bidirectional reference pada article nodes
                if matched_id not in source_art["references_to"]:
                    source_art["references_to"].append(matched_id)
                target = art_map.get(matched_id)
                if target and source_art["article_id"] not in target.get("referenced_by", []):
                    target.setdefault("referenced_by", []).append(source_art["article_id"])
    
    # Hitung blast radius per pasal
    for art in articles:
        n_refs = len(art.get("referenced_by", []))
        if n_refs >= 5:
            art["blast_radius"] = "HIGH"
        elif n_refs >= 2:
            art["blast_radius"] = "MEDIUM"
        elif n_refs >= 1:
            art["blast_radius"] = "LOW"
        else:
            art["blast_radius"] = "NONE"
    
    doc["cross_references"] = cross_refs
    return doc


def get_blast_radius_report(legal_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Menghasilkan laporan blast radius untuk semua pasal.
    HIGH = 5+ pasal lain merujuk | MEDIUM = 2-4 | LOW = 1 | NONE = 0
    """
    articles = extract_articles_flat(legal_doc)
    report = {"HIGH": [], "MEDIUM": [], "LOW": [], "NONE": []}
    for art in articles:
        br = art.get("blast_radius", "NONE")
        report[br].append({
            "article_id": art["article_id"],
            "label": art["number_label"],
            "referenced_by": art.get("referenced_by", [])
        })
    return report


# ─── Norm Transformation Operations ──────────────────────────────────────────

def _update_all_references_after_renumber(
    doc: Dict[str, Any],
    old_id: str,
    new_id: str
) -> Dict[str, Any]:
    """
    Perbarui semua rujukan dari old_id → new_id di seluruh teks dokumen.
    Operasi atomik untuk mencegah dangling references.
    """
    old_label = old_id.replace("PASAL_", "Pasal ")
    new_label = new_id.replace("PASAL_", "Pasal ")
    
    articles = extract_articles_flat(doc)
    for art in articles:
        # Update raw_text
        art["raw_text"] = art["raw_text"].replace(old_label, new_label)
        # Update clauses
        for clause in art.get("clauses", []):
            clause["raw_text"] = clause["raw_text"].replace(old_label, new_label)
            for sub in clause.get("sub_items", []):
                sub["text"] = sub["text"].replace(old_label, new_label)
        # Update references_to list
        if old_id in art.get("references_to", []):
            art["references_to"] = [new_id if r == old_id else r for r in art["references_to"]]
        if old_id in art.get("referenced_by", []):
            art["referenced_by"] = [new_id if r == old_id else r for r in art["referenced_by"]]
    
    # Update cross_references list
    for cr in doc.get("cross_references", []):
        if cr["source_article"] == old_id:
            cr["source_article"] = new_id
        if cr["target_article"] == old_id:
            cr["target_article"] = new_id
    
    return doc


def amendment_mapping(
    legal_doc: Dict[str, Any],
    article_id: str,
    clause_number: Optional[str] = None,
    new_text: str = "",
    rationale: str = ""
) -> Dict[str, Any]:
    """
    PILAR 1 — UBAH SEBAGIAN.
    Mengubah teks pasal atau ayat tertentu.
    
    Args:
        legal_doc: Dokumen legal parsed
        article_id: e.g., 'PASAL_7'
        clause_number: e.g., '(2)', None untuk ubah seluruh pasal
        new_text: Teks baru pengganti
        rationale: Alasan perubahan (untuk audit log)
    Returns:
        LegalDocument yang telah diperbarui dengan perubahan dan diff
    """
    doc = copy.deepcopy(legal_doc)
    articles = extract_articles_flat(doc)
    
    for art in articles:
        if art["article_id"] != article_id:
            continue
        
        old_text = art["raw_text"]
        if clause_number:
            # Ubah ayat tertentu
            for clause in art.get("clauses", []):
                if clause["number"] == clause_number:
                    old_clause_text = clause["raw_text"]
                    clause["raw_text"] = new_text
                    art["dim_action"] = "UBAH_SEBAGIAN"
                    return {
                        "success": True,
                        "action": "UBAH_SEBAGIAN",
                        "article_id": article_id,
                        "clause": clause_number,
                        "old_text": old_clause_text,
                        "new_text": new_text,
                        "rationale": rationale,
                        "doc": doc
                    }
            return {"success": False, "error": f"Ayat {clause_number} tidak ditemukan di {article_id}"}
        else:
            # Ubah seluruh pasal
            art["raw_text"] = new_text
            art["dim_action"] = "UBAH_SEBAGIAN"
            return {
                "success": True,
                "action": "UBAH_SEBAGIAN",
                "article_id": article_id,
                "old_text": old_text,
                "new_text": new_text,
                "rationale": rationale,
                "doc": doc
            }
    
    return {"success": False, "error": f"Pasal {article_id} tidak ditemukan"}


def delete_article(
    legal_doc: Dict[str, Any],
    article_id: str,
    rationale: str = ""
) -> Dict[str, Any]:
    """
    PILAR 1 — HAPUS.
    Menghapus pasal dan memperbarui seluruh referensi silang.
    """
    doc = copy.deepcopy(legal_doc)
    
    # Cek blast radius sebelum hapus
    art = get_article_by_id(doc, article_id)
    if not art:
        return {"success": False, "error": f"Pasal {article_id} tidak ditemukan"}
    
    blast = art.get("blast_radius", "NONE")
    referenced_by = art.get("referenced_by", [])
    
    # Hapus dari semua chapter
    for chapter in doc.get("body", {}).get("chapters", []):
        chapter["articles"] = [a for a in chapter.get("articles", []) if a["article_id"] != article_id]
        for section in chapter.get("sections", []):
            section["articles"] = [a for a in section.get("articles", []) if a["article_id"] != article_id]
    
    # Hapus cross_references yang melibatkan pasal ini
    doc["cross_references"] = [
        cr for cr in doc.get("cross_references", [])
        if cr["source_article"] != article_id and cr["target_article"] != article_id
    ]
    
    # Perbarui referenced_by di pasal-pasal yang merujuk ke pasal yang dihapus
    for other_art in extract_articles_flat(doc):
        if article_id in other_art.get("references_to", []):
            other_art["references_to"].remove(article_id)
    
    return {
        "success": True,
        "action": "HAPUS",
        "article_id": article_id,
        "blast_radius": blast,
        "warning": f"Pasal ini dirujuk oleh {len(referenced_by)} pasal lain: {referenced_by}" if referenced_by else None,
        "rationale": rationale,
        "doc": doc
    }


def split_article(
    legal_doc: Dict[str, Any],
    article_id: str,
    split_plan: List[Dict[str, Any]],
    rationale: str = ""
) -> Dict[str, Any]:
    """
    PILAR 1 — PECAH (Split Analysis).
    Memecah 1 pasal menjadi n pasal baru.
    
    Args:
        legal_doc: Dokumen legal parsed
        article_id: ID pasal yang akan dipecah (e.g., 'PASAL_7')
        split_plan: Daftar pasal baru hasil pecahan:
            [
                {"number_label": "Pasal 7", "clauses_indices": [0, 1], "norm_type": "KEWENANGAN"},
                {"number_label": "Pasal 7A", "clauses_indices": [2, 3], "norm_type": "KEWAJIBAN"},
            ]
        rationale: Alasan pemecahan
    Returns:
        Dict dengan LegalDocument yang telah dipecah + renumbering seluruh dokumen
    """
    doc = copy.deepcopy(legal_doc)
    source_art = get_article_by_id(doc, article_id)
    
    if not source_art:
        return {"success": False, "error": f"Pasal {article_id} tidak ditemukan"}
    
    all_clauses = source_art.get("clauses", [])
    new_articles = []
    
    for plan_item in split_plan:
        clause_indices = plan_item.get("clauses_indices", [])
        selected_clauses = [all_clauses[i] for i in clause_indices if i < len(all_clauses)]
        
        num_str = re.sub(r'[^0-9]', '', plan_item.get("number_label", "0"))
        new_art = {
            "article_id": f"PASAL_{num_str}",
            "number": int(num_str) if num_str else 0,
            "number_label": plan_item.get("number_label", f"Pasal ?"),
            "raw_text": "\n".join(c.get("raw_text", "") for c in selected_clauses),
            "clauses": selected_clauses,
            "norm_type": plan_item.get("norm_type", "LAIN"),
            "dim_action": "NORMA_BARU",
            "dim_disposition": None,
            "dim_justification": rationale,
            "references_to": [],
            "referenced_by": [],
            "blast_radius": "NONE"
        }
        new_articles.append(new_art)
    
    # Ganti pasal lama dengan pasal-pasal baru di chapter yang sama
    for chapter in doc.get("body", {}).get("chapters", []):
        for i, art in enumerate(chapter.get("articles", [])):
            if art["article_id"] == article_id:
                # Sisipkan pasal-pasal baru di posisi yang sama
                chapter["articles"] = (
                    chapter["articles"][:i] +
                    new_articles +
                    chapter["articles"][i+1:]
                )
                break
    
    # Rebuild cross-reference graph
    doc = build_cross_reference_graph(doc)
    
    return {
        "success": True,
        "action": "PECAH",
        "source_article_id": article_id,
        "new_articles": [a["article_id"] for a in new_articles],
        "rationale": rationale,
        "doc": doc
    }


def merge_articles(
    legal_doc: Dict[str, Any],
    article_ids: List[str],
    merged_number: int,
    merged_title: str = "",
    rationale: str = ""
) -> Dict[str, Any]:
    """
    PILAR 1 — GABUNG (Merger Analysis).
    Menggabungkan beberapa pasal menjadi satu pasal konsolidasi.
    
    Args:
        legal_doc: Dokumen legal parsed
        article_ids: Daftar article_id yang akan digabung (urutan penting)
        merged_number: Nomor pasal hasil gabungan
        merged_title: Judul/label pasal baru
        rationale: Alasan penggabungan
    """
    doc = copy.deepcopy(legal_doc)
    all_articles = extract_articles_flat(doc)
    art_map = {a["article_id"]: a for a in all_articles}
    
    # Validasi semua pasal ada
    missing = [aid for aid in article_ids if aid not in art_map]
    if missing:
        return {"success": False, "error": f"Pasal tidak ditemukan: {missing}"}
    
    # Kumpulkan semua klausul dari pasal-pasal yang digabung
    merged_clauses = []
    merged_raw_texts = []
    clause_counter = 1
    
    for art_id in article_ids:
        art = art_map[art_id]
        merged_raw_texts.append(art.get("raw_text", ""))
        for clause in art.get("clauses", []):
            new_clause = copy.deepcopy(clause)
            new_clause["number"] = f"({clause_counter})"
            new_clause["clause_id"] = f"AYAT_{clause_counter}"
            merged_clauses.append(new_clause)
            clause_counter += 1
    
    # Buat pasal gabungan
    merged_art = {
        "article_id": f"PASAL_{merged_number}",
        "number": merged_number,
        "number_label": merged_title or f"Pasal {merged_number}",
        "raw_text": "\n\n".join(merged_raw_texts),
        "clauses": merged_clauses,
        "norm_type": "LAIN",
        "dim_action": "GABUNG",
        "dim_disposition": None,
        "dim_justification": rationale,
        "references_to": [],
        "referenced_by": [],
        "blast_radius": "NONE"
    }
    
    # Hapus pasal-pasal lama, sisipkan pasal gabungan di posisi pasal pertama
    first_id = article_ids[0]
    for chapter in doc.get("body", {}).get("chapters", []):
        new_arts = []
        inserted = False
        for art in chapter.get("articles", []):
            if art["article_id"] == first_id and not inserted:
                new_arts.append(merged_art)
                inserted = True
            elif art["article_id"] not in article_ids:
                new_arts.append(art)
        chapter["articles"] = new_arts
    
    doc = build_cross_reference_graph(doc)
    
    return {
        "success": True,
        "action": "GABUNG",
        "merged_from": article_ids,
        "merged_article_id": f"PASAL_{merged_number}",
        "rationale": rationale,
        "doc": doc
    }


def renumber_all_articles(
    legal_doc: Dict[str, Any],
    start_number: int = 1,
    rationale: str = "Renumbering otomatis paska transformasi norma"
) -> Dict[str, Any]:
    """
    PILAR 1 — RELOKASI/RENUMBERING.
    Menomori ulang seluruh pasal secara berurutan mulai dari start_number.
    OTOMATIS memperbarui semua rujukan silang antar-pasal.
    
    Returns:
        Dict dengan doc + mapping_table (old_id → new_id) + blast radius warning
    """
    doc = copy.deepcopy(legal_doc)
    articles = extract_articles_flat(doc)
    
    mapping: Dict[str, str] = {}
    counter = start_number
    
    # Buat peta renaming dahulu
    for art in articles:
        old_id = art["article_id"]
        new_num = counter
        new_id = f"PASAL_{new_num}"
        if old_id != new_id:
            mapping[old_id] = new_id
        counter += 1
    
    # Terapkan renaming ke dokumen
    for old_id, new_id in mapping.items():
        # Update id dan nomor pada objek artikel
        for chapter in doc.get("body", {}).get("chapters", []):
            for art in chapter.get("articles", []):
                if art["article_id"] == old_id:
                    new_num_int = int(new_id.replace("PASAL_", ""))
                    art["article_id"] = new_id
                    art["number"] = new_num_int
                    art["number_label"] = f"Pasal {new_num_int}"
                    art["dim_action"] = "RELOKASI"
        # Update teks silang di seluruh dokumen
        doc = _update_all_references_after_renumber(doc, old_id, new_id)
    
    doc = build_cross_reference_graph(doc)
    
    return {
        "success": True,
        "action": "RELOKASI",
        "mapping_table": mapping,
        "total_renamed": len(mapping),
        "rationale": rationale,
        "doc": doc
    }
