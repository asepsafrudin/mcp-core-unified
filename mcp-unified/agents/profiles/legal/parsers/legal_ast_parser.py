"""
legal_ast_parser.py — Hierarchical Legal Document AST Parser (Subtask 131-B)
============================================================================
Parser deterministik multi-level untuk dokumen perundang-undangan Indonesia.

Kemampuan:
- Parsing Hierarki Lengkap: Pembukaan → Bab → Bagian → Paragraf → Pasal → Ayat → Huruf/Angka
- Deteksi otomatis jenis norma per pasal (kewenangan, definisi, kewajiban, sanksi, dll.)
- Output sebagai LegalDocument dict sesuai skema schema/legal_doc.json
- Integrasi dengan CrossReferenceGraph (131-C) untuk membangun DAG rujukan

Digunakan oleh:
- Pilar 1 (Norm Transformation Engine - split/merge/renumber)
- Pilar 2 (PUEBI Linter & Glosarium Harmonizer)
- Pilar 3 (Hierarchy Validator)
- legal_tools.py → legal_ast_parse()
"""

import re
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime


# ─── Konstanta & Pattern Regex ────────────────────────────────────────────────

RE_BAB = re.compile(
    r'(?m)^(?:BAB|Bab)\s+(I{1,3}V?|VI{0,3}|IX|X{1,3}|[0-9]+)\b[^\n]*$',
    re.IGNORECASE
)
RE_BAGIAN = re.compile(
    r'(?m)^(?:Bagian|BAGIAN)\s+(?:Ke(?:satu|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh)|[A-Za-z]+|\d+)',
    re.IGNORECASE
)
RE_PARAGRAF = re.compile(
    r'(?m)^(?:Paragraf|PARAGRAF)\s+(?:[A-Za-z]+|\d+)',
    re.IGNORECASE
)
RE_PASAL = re.compile(
    r'(?m)^(?:Pasal|PASAL)\s+(\d+(?:\s*[A-Z])?)\s*$',
    re.IGNORECASE
)
RE_AYAT = re.compile(r'^\s*\((\d+)\)\s*(.+?)(?=\s*\(\d+\)|\s*$)', re.DOTALL)
RE_HURUF = re.compile(r'^\s*([a-z])\.\s+(.+?)(?=\s*[a-z]\.\s|\s*$)', re.DOTALL)
RE_ANGKA = re.compile(r'^\s*(\d+)\.\s+(.+?)(?=\s*\d+\.\s|\s*$)', re.DOTALL)

# Pattern untuk mengenali jenis norma per pasal
NORM_TYPE_PATTERNS = {
    "DEFINISI": re.compile(r'(?:dalam.*peraturan ini|ketentuan umum|yang dimaksud dengan|berarti|adalah)\s+\w', re.I),
    "ASAS": re.compile(r'(?:asas|prinsip|dasar|tujuan)\s+(?:dari|dalam|peraturan)', re.I),
    "TUJUAN": re.compile(r'(?:tujuan|maksud)\s+(?:dari|peraturan|perundang)', re.I),
    "KEWENANGAN": re.compile(r'(?:berwenang|mempunyai wewenang|memiliki kewenangan|berhak untuk)', re.I),
    "HAK": re.compile(r'(?:berhak|mempunyai hak|mendapat(?:kan)?)\s+(?:untuk|atas)', re.I),
    "KEWAJIBAN": re.compile(r'(?:wajib|berkewajiban|harus|diwajibkan)\s+\w', re.I),
    "LARANGAN": re.compile(r'(?:dilarang|tidak diperbolehkan|tidak boleh|tidak dapat)\s+\w', re.I),
    "SANKSI": re.compile(r'(?:sanksi|pidana|denda|hukuman|administratif|teguran|pencabutan)', re.I),
    "PERALIHAN": re.compile(r'(?:ketentuan peralihan|sebelum peraturan ini|masih tetap berlaku|sudah ada)', re.I),
    "PENUTUP": re.compile(r'(?:mulai berlaku|dicabut|dinyatakan tidak berlaku|agar dimaklumi)', re.I),
}

# Daftar kata kunci PUEBI — pasal penanda Ketentuan Umum
KETUM_PATTERN = re.compile(r'ketentuan umum', re.I)
KETERANGAN_PATTERN = re.compile(r'ketentuan peralihan', re.I)
PENUTUP_PATTERN = re.compile(r'ketentuan penutup', re.I)


# ─── Data Classes (dict-based untuk kompatibilitas JSON) ─────────────────────

def _make_clause(number: str, raw_text: str, sub_items: List[Dict] = None) -> Dict[str, Any]:
    return {
        "clause_id": f"AYAT_{number.strip('()')}",
        "number": number,
        "raw_text": raw_text.strip(),
        "sub_items": sub_items or []
    }


def _make_article(number: int, raw_text: str, clauses: List[Dict] = None) -> Dict[str, Any]:
    label = f"Pasal {number}"
    norm_type = _detect_norm_type(raw_text)
    return {
        "article_id": f"PASAL_{number}",
        "number": number,
        "number_label": label,
        "raw_text": raw_text.strip(),
        "clauses": clauses or [],
        "norm_type": norm_type,
        "dim_action": "AS_IS",         # Default — diubah oleh NormTransformationEngine
        "dim_disposition": None,
        "dim_justification": "",
        "references_to": [],
        "referenced_by": [],
        "blast_radius": "NONE"
    }


def _make_chapter(chapter_id: str, roman: str, title: str, chapter_type: str = "SUBSTANSI") -> Dict[str, Any]:
    return {
        "chapter_id": chapter_id,
        "roman_number": roman,
        "title": title.strip(),
        "chapter_type": chapter_type,
        "sections": [],
        "articles": []
    }


# ─── Core Parser ─────────────────────────────────────────────────────────────

def _detect_norm_type(text: str) -> str:
    """Deteksi jenis norma berdasarkan pola kata kunci."""
    for norm_type, pattern in NORM_TYPE_PATTERNS.items():
        if pattern.search(text):
            return norm_type
    return "LAIN"


def _parse_sub_items(text: str) -> List[Dict[str, Any]]:
    """Parse butir huruf (a., b., c.) atau angka (1., 2.) dalam satu blok teks."""
    items = []
    # Coba huruf dulu
    huruf_blocks = re.split(r'\n(?=[a-z]\.)', text)
    if len(huruf_blocks) > 1:
        for block in huruf_blocks:
            m = re.match(r'^([a-z])\.\s*(.+)', block.strip(), re.DOTALL)
            if m:
                items.append({"item_id": f"HURUF_{m.group(1).upper()}", "marker": m.group(1), "text": m.group(2).strip()})
        return items
    # Coba angka
    angka_blocks = re.split(r'\n(?=\d+\.)', text)
    if len(angka_blocks) > 1:
        for block in angka_blocks:
            m = re.match(r'^(\d+)\.\s*(.+)', block.strip(), re.DOTALL)
            if m:
                items.append({"item_id": f"ANGKA_{m.group(1)}", "marker": m.group(1), "text": m.group(2).strip()})
    return items


def _parse_clauses(article_body: str) -> List[Dict[str, Any]]:
    """
    Parse ayat-ayat dalam satu blok teks pasal.
    Mendeteksi pola (1), (2), (3)... dan sub-item huruf/angka di dalamnya.
    """
    clauses = []
    # Pisahkan berdasarkan marker ayat: (1), (2), ...
    ayat_splits = re.split(r'(?=\s*\(\d+\))', article_body)

    for block in ayat_splits:
        block = block.strip()
        if not block:
            continue
        m = re.match(r'(\(\d+\))\s*(.+)', block, re.DOTALL)
        if m:
            number = m.group(1)
            content = m.group(2).strip()
            sub_items = _parse_sub_items(content)
            clauses.append(_make_clause(number, content, sub_items))
        elif not clauses:
            # Pasal tanpa ayat — seluruh isi adalah body utama
            sub_items = _parse_sub_items(block)
            clauses.append(_make_clause("(1)", block, sub_items))
    
    return clauses if clauses else [_make_clause("(1)", article_body.strip())]


def _extract_preamble(text: str) -> Dict[str, Any]:
    """Ekstraksi bagian pembukaan: Menimbang, Mengingat, Memperhatikan."""
    preamble: Dict[str, Any] = {
        "menimbang": [],
        "mengingat": [],
        "memperhatikan": []
    }
    # Menimbang
    m_timb = re.search(r'MENIMBANG\s*:(.*?)(?=MENGINGAT|MEMPERHATIKAN|MEMUTUSKAN)', text, re.I | re.DOTALL)
    if m_timb:
        butir = re.findall(r'[a-z]\.\s+(.+?)(?=\n[a-z]\.|$)', m_timb.group(1), re.DOTALL)
        preamble["menimbang"] = [b.strip() for b in butir] if butir else [m_timb.group(1).strip()[:500]]
    
    # Mengingat
    m_ing = re.search(r'MENGINGAT\s*:(.*?)(?=MEMUTUSKAN|MENETAPKAN|BAB\s+I)', text, re.I | re.DOTALL)
    if m_ing:
        refs = re.findall(r'\d+\.\s+(.+?)(?=\n\s*\d+\.|$)', m_ing.group(1), re.DOTALL)
        preamble["mengingat"] = [{"doc_ref": "", "text": r.strip()[:300]} for r in refs]
    
    return preamble


def _split_into_article_blocks(text: str) -> List[Tuple[int, str]]:
    """
    Membagi teks regulasi menjadi blok-blok pasal.
    Returns list of (pasal_number, pasal_body_text).
    """
    matches = list(RE_PASAL.finditer(text))
    if not matches:
        return []
    
    blocks = []
    for i, m in enumerate(matches):
        num_str = m.group(1).strip()
        # Handle nomor seperti "7A" → simpan sebagai string untuk label tapi int untuk sorting
        num_int = int(re.sub(r'[^0-9]', '', num_str)) if num_str else 0
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        blocks.append((num_int, body, num_str))
    
    return blocks


def _detect_chapter_type(chapter_title: str) -> str:
    """Deteksi tipe bab dari judul bab."""
    t = chapter_title.lower()
    if "ketentuan umum" in t:
        return "KETENTUAN_UMUM"
    elif "peralihan" in t:
        return "KETENTUAN_PERALIHAN"
    elif "penutup" in t:
        return "KETENTUAN_PENUTUP"
    elif "kewenangan" in t or "tugas" in t:
        return "KEWENANGAN"
    elif "hak" in t and "kewajib" in t:
        return "HAK_KEWAJIBAN"
    elif "pendanaan" in t or "pembiayaan" in t:
        return "PENDANAAN"
    return "SUBSTANSI"


# ─── Public API ───────────────────────────────────────────────────────────────

def parse_regulation_text(
    regulation_text: str,
    title: str = "Peraturan Perundang-undangan",
    instrument_type: str = "PERDA_KABKOTA",
    level_hierarki: int = 7,
    issuer: str = "Unknown",
    year: Optional[int] = None,
    number: Optional[str] = None,
    source_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Mem-parsing teks regulasi menjadi struktur LegalDocument sesuai schema/legal_doc.json.
    
    Args:
        regulation_text: Teks penuh dokumen regulasi (plaintext/markdown)
        title: Judul resmi regulasi
        instrument_type: Jenis instrumen (UU/PP/PERDA_KABKOTA/dll)
        level_hierarki: Level hierarki UU 12/2011 (1-8)
        issuer: Lembaga penerbit
        year: Tahun penetapan
        number: Nomor regulasi
        source_path: Path file sumber (untuk metadata)
    
    Returns:
        Dict berisi struktur LegalDocument lengkap sesuai schema/legal_doc.json
    """
    doc_id = f"{instrument_type}-{number or 'X'}-{year or 'XXXX'}"
    
    # 1. Parse pembukaan
    preamble = _extract_preamble(regulation_text)
    
    # 2. Pisahkan ke blok pasal
    article_blocks = _split_into_article_blocks(regulation_text)
    
    # 3. Parse BAB dan struktur hierarki
    chapters: List[Dict[str, Any]] = []
    bab_matches = list(RE_BAB.finditer(regulation_text))
    
    if bab_matches:
        for i, bm in enumerate(bab_matches):
            roman = bm.group(1).strip().upper()
            bab_header_text = bm.group(0).strip()
            # Cari judul bab (baris berikutnya setelah "BAB XX")
            after_header = regulation_text[bm.end():bm.end() + 200].strip()
            title_m = re.match(r'^([A-Z][^\n]+)', after_header)
            chapter_title = title_m.group(1).strip() if title_m else bab_header_text
            
            chapter_type = _detect_chapter_type(chapter_title)
            chapter = _make_chapter(
                chapter_id=f"BAB_{roman}",
                roman=roman,
                title=chapter_title,
                chapter_type=chapter_type
            )
            chapters.append(chapter)
    else:
        # Tidak ada struktur BAB — buat satu chapter generik
        chapters.append(_make_chapter("BAB_I", "I", "ISI PERATURAN"))
    
    # 4. Parse semua pasal dan assign ke chapter yang tepat
    # Strategi sederhana: assign pasal berurutan ke chapter terakhir yang ditemukan
    all_articles: List[Dict[str, Any]] = []
    pasal_per_chapter: Dict[str, List[int]] = {}
    
    pasal_matches = list(RE_PASAL.finditer(regulation_text))
    
    # Tentukan pasal mana masuk ke BAB mana berdasarkan posisi karakter
    chapter_positions = [(bm.start(), i) for i, bm in enumerate(bab_matches)] if bab_matches else [(0, 0)]
    
    for num_int, body, num_str in article_blocks:
        clauses = _parse_clauses(body)
        article = _make_article(num_int, body, clauses)
        article["number_label"] = f"Pasal {num_str}"
        article["article_id"] = f"PASAL_{num_str}"
        all_articles.append(article)
    
    # Assign pasal ke chapters menggunakan posisi
    for pm in pasal_matches:
        pos = pm.start()
        assigned_chap_idx = 0
        for cp_pos, cp_idx in chapter_positions:
            if pos >= cp_pos:
                assigned_chap_idx = cp_idx
        num_str_local = pm.group(1).strip()
        chap_id = chapters[assigned_chap_idx]["chapter_id"]
        pasal_per_chapter.setdefault(chap_id, []).append(int(re.sub(r'[^0-9]', '', num_str_local)))
    
    # Masukkan artikel ke chapter yang sesuai
    article_map = {a["article_id"]: a for a in all_articles}
    for chap in chapters:
        pasal_nums = pasal_per_chapter.get(chap["chapter_id"], [])
        for num in sorted(pasal_nums):
            art_id = f"PASAL_{num}"
            if art_id in article_map:
                chap["articles"].append(article_map[art_id])
    
    # Hitung statistik
    total_pasal = len(all_articles)
    total_ayat = sum(len(a.get("clauses", [])) for a in all_articles)
    
    # 5. Bangun dokumen final
    legal_doc = {
        "doc_id": doc_id,
        "instrument_type": instrument_type,
        "instrument_category": "STATUTORY" if level_hierarki <= 7 else "NON_STATUTORY_BELEIDSREGELS",
        "level_hierarki": level_hierarki,
        "title": title,
        "number": number,
        "year": year,
        "issuer": issuer,
        "promulgation_date": None,
        "effective_date": None,
        "sunset_date": None,
        "status": "BERLAKU",
        "superseded_by": None,
        "amends": [],
        "parent_delegation": None,
        "subject_area": [],
        "ministry_domain": [],
        "metadata": {
            "parsed_at": datetime.utcnow().isoformat() + "Z",
            "parser_version": "1.0.0-TASK131B",
            "source_format": "TEXT",
            "source_path": source_path or "",
            "total_bab": len(chapters),
            "total_pasal": total_pasal,
            "total_ayat": total_ayat,
            "has_ketentuan_umum": any(c["chapter_type"] == "KETENTUAN_UMUM" for c in chapters),
            "has_ketentuan_peralihan": any(c["chapter_type"] == "KETENTUAN_PERALIHAN" for c in chapters),
            "has_ketentuan_penutup": any(c["chapter_type"] == "KETENTUAN_PENUTUP" for c in chapters),
            "evaluation_6d_status": "PENDING",
            "dim_disposition_status": "PENDING_REVIEW"
        },
        "body": {
            "preamble": preamble,
            "chapters": chapters,
            "attachments": []
        },
        "cross_references": [],   # Diisi oleh CrossReferenceGraph (131-C)
        "dim_matrix": []          # Diisi oleh DIM Disposition Engine (131-I)
    }
    
    return legal_doc


def extract_articles_flat(legal_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Ekstrak semua pasal dari LegalDocument menjadi flat list, terurut berdasarkan nomor.
    Berguna untuk Pilar 1 (norm manipulation) dan Pilar 2 (PUEBI linting).
    """
    articles = []
    for chapter in legal_doc.get("body", {}).get("chapters", []):
        for section in chapter.get("sections", []):
            articles.extend(section.get("articles", []))
        articles.extend(chapter.get("articles", []))
    return sorted(articles, key=lambda a: a.get("number", 0))


def get_article_by_id(legal_doc: Dict[str, Any], article_id: str) -> Optional[Dict[str, Any]]:
    """Cari pasal berdasarkan article_id (e.g., 'PASAL_7')."""
    for art in extract_articles_flat(legal_doc):
        if art.get("article_id") == article_id:
            return art
    return None


def get_glossary_definitions(legal_doc: Dict[str, Any]) -> Dict[str, str]:
    """
    Ekstraksi seluruh definisi dari Pasal Ketentuan Umum (Pasal 1).
    Berguna untuk Pilar 2: Glosarium Harmonizer.
    """
    definitions: Dict[str, str] = {}
    articles = extract_articles_flat(legal_doc)
    for art in articles:
        if art.get("chapter_type") == "KETENTUAN_UMUM" or art.get("number") == 1:
            text = art.get("raw_text", "")
            # Pattern: "Yang dimaksud dengan "X" adalah/berarti ..."
            matches = re.findall(
                r'["\u201c]([\w\s]+)["\u201d]\s+(?:adalah|berarti|merupakan)\s+([^;.]+)',
                text
            )
            for term, defn in matches:
                definitions[term.strip().lower()] = defn.strip()
            # Juga coba format: Nomor X. "Term" adalah ...
            matches2 = re.findall(r'\d+\.\s+["\u201c]([\w\s]+)["\u201d]\s+(?:adalah|berarti)\s+([^;.]+)', text)
            for term, defn in matches2:
                definitions[term.strip().lower()] = defn.strip()
    return definitions


def serialize_to_markdown(legal_doc: Dict[str, Any]) -> str:
    """
    Konversi LegalDocument kembali ke teks markdown terstruktur.
    Berguna untuk memperlihatkan hasil transformasi Pilar 1 (split/merge/renumber).
    """
    lines = []
    meta = legal_doc
    lines.append(f"# {meta.get('title', 'Peraturan')}\n")
    lines.append(f"**Nomor:** {meta.get('number', '-')} | **Tahun:** {meta.get('year', '-')} | **Status:** {meta.get('status', 'BERLAKU')}\n")
    lines.append("---\n")
    
    preamble = legal_doc.get("body", {}).get("preamble", {})
    if preamble.get("menimbang"):
        lines.append("**MENIMBANG:**\n")
        for i, b in enumerate(preamble["menimbang"]):
            lines.append(f"  {chr(97+i)}. {b}\n")
    
    for chapter in legal_doc.get("body", {}).get("chapters", []):
        lines.append(f"\n## BAB {chapter.get('roman_number', '')} — {chapter.get('title', '')}\n")
        all_chap_articles = []
        for sec in chapter.get("sections", []):
            lines.append(f"\n### {sec.get('title', '')}\n")
            all_chap_articles.extend(sec.get("articles", []))
        all_chap_articles.extend(chapter.get("articles", []))
        
        for art in all_chap_articles:
            lines.append(f"\n**{art.get('number_label', 'Pasal ?')}**\n")
            for clause in art.get("clauses", []):
                lines.append(f"{clause.get('number', '')} {clause.get('raw_text', '')}\n")
                for sub in clause.get("sub_items", []):
                    lines.append(f"   {sub.get('marker', '')}. {sub.get('text', '')}\n")
    
    return "\n".join(lines)
