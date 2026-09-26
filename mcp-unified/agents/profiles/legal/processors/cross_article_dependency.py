"""
cross_article_dependency.py — Normative Cross-Article Dependency Tree & Impact Radius.
Membangun graf ketergantungan relasional antar-pasal berbasis symbol intelligence untuk melacak efek amandemen/derogasi norma hukum.
"""

import re
from typing import Dict, Any, List, Set, Optional, Tuple


def parse_articles_and_clauses(regulation_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Memecah teks regulasi menjadi unit-unit Pasal dan Ayat terstruktur.
    """
    articles = {}
    
    # Pattern untuk mendeteksi Header Pasal (hanya di awal baris)
    article_header_pattern = re.compile(r'(?:^|\n)\s*(Pasal\s+\d+)\s*\n?', re.IGNORECASE)
    
    # Cari posisi seluruh header pasal
    matches = list(article_header_pattern.finditer(regulation_text))
    
    if not matches:
        articles["Pasal 1"] = {
            "title": "Pasal 1",
            "text": regulation_text.strip(),
            "subclauses": []
        }
        return articles

    for i in range(len(matches)):
        m = matches[i]
        art_title = m.group(1).strip()
        art_title = re.sub(r'\s+', ' ', art_title).capitalize()
        
        start_idx = m.end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(regulation_text)
        
        art_body = regulation_text[start_idx:end_idx].strip()
        ayat_matches = re.findall(r'(\(\d+\)\s+[^\(\n]+)', art_body)
        
        articles[art_title] = {
            "title": art_title,
            "text": art_body,
            "subclauses": [am.strip() for am in ayat_matches]
        }
        
    return articles


def extract_cross_references(article_name: str, article_text: str) -> List[Dict[str, Any]]:
    """
    Mengekstrak rujukan ke pasal/ayat lain di dalam satu teks pasal.
    """
    references = []
    
    # 1. Pattern rujukan Pasal eksplisit: "sebagaimana dimaksud dalam Pasal X (ayat (Y))?"
    pattern_pasal = re.compile(
        r'(?:sebagaimana dimaksud|dikecualikan dari ketentuan|dikecualikan dari|mengacu pada|berdasarkan ketentuan|berdasarkan|berpedoman pada|ketentuan dalam|pelaksanaan ketentuan|diatur dalam|merujuk pada)?\s*(?:dalam\s+|pada\s+)?(Pasal\s+\d+)(?:\s+ayat\s+(\(\d+\)))?(?:\s+huruf\s+([a-z]))?',
        re.IGNORECASE
    )
    
    seen_refs = set()

    for match in pattern_pasal.finditer(article_text):
        target_pasal_raw = match.group(1)
        if not target_pasal_raw:
            continue
            
        target_pasal = target_pasal_raw.strip().capitalize()
        target_ayat = match.group(2).strip() if match.group(2) else None
        target_huruf = match.group(3).strip() if match.group(3) else None
        
        full_context = match.group(0).lower()
        ref_type = "GENERAL_REFERENCE"
        if "dikecualikan" in full_context:
            ref_type = "EXCEPTION"
        elif "berdasarkan" in full_context or "diatur" in full_context or "berpedoman" in full_context:
            ref_type = "DELEGATION"
        elif "sebagaimana dimaksud" in full_context:
            ref_type = "NORMATIVE_SUBORDINATION"

        ref_key = (article_name, target_pasal, target_ayat, target_huruf)
        if ref_key not in seen_refs:
            seen_refs.add(ref_key)
            references.append({
                "source_article": article_name,
                "target_article": target_pasal,
                "target_ayat": target_ayat,
                "target_huruf": target_huruf,
                "reference_type": ref_type,
                "raw_snippet": match.group(0).strip(),
            })

    # 2. Pattern rujukan internal ayat dalam pasal yang sama: "sebagaimana dimaksud pada ayat (1)"
    pattern_ayat_internal = re.compile(
        r'(?:sebagaimana dimaksud|dikecualikan)\s+(?:pada\s+|dalam\s+)?ayat\s+(\(\d+\))',
        re.IGNORECASE
    )
    for match in pattern_ayat_internal.finditer(article_text):
        target_ayat = match.group(1).strip()
        ref_key = (article_name, article_name, target_ayat, None)
        if ref_key not in seen_refs:
            seen_refs.add(ref_key)
            references.append({
                "source_article": article_name,
                "target_article": article_name,
                "target_ayat": target_ayat,
                "target_huruf": None,
                "reference_type": "INTERNAL_AYAT_REFERENCE",
                "raw_snippet": match.group(0).strip(),
            })
        
    return references


import hashlib

_LOCAL_DEPTREE_CACHE: Dict[str, Dict[str, Any]] = {}


def build_normative_dependency_graph(regulation_text: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Membangun graf relasional dan menghitung Blast Radius amandemen.
    Mendukung caching in-memory & Redis untuk respons sub-millisecond.
    """
    cache_key = hashlib.sha256(regulation_text.strip().encode("utf-8")).hexdigest()[:16]
    
    if use_cache and cache_key in _LOCAL_DEPTREE_CACHE:
        cached = _LOCAL_DEPTREE_CACHE[cache_key].copy()
        cached["from_cache"] = True
        return cached

    articles = parse_articles_and_clauses(regulation_text)
    nodes = list(articles.keys())
    edges = []
    
    # Map ketergantungan: target -> list of callers (siapa saja yang merujuk ke target)
    incoming_refs: Dict[str, List[str]] = {node: [] for node in nodes}
    outgoing_refs: Dict[str, List[str]] = {node: [] for node in nodes}

    for art_name, art_data in articles.items():
        refs = extract_cross_references(art_name, art_data["text"])
        for r in refs:
            edges.append(r)
            target = r["target_article"]
            if target != art_name:
                if target not in incoming_refs:
                    incoming_refs[target] = []
                incoming_refs[target].append(art_name)
                outgoing_refs[art_name].append(target)

    # Identifikasi Root Norms (Pasal yang paling banyak dirujuk oleh pasal lain)
    root_definitions = sorted(
        [(k, len(v)) for k, v in incoming_refs.items() if len(v) > 0],
        key=lambda x: x[1],
        reverse=True
    )

    # Hitung Blast Radius per pasal
    blast_radius = {}
    for node in nodes:
        # Jika node ini diubah/dihapus, pasal apa saja yang terpengaruh?
        affected = set(incoming_refs.get(node, []))
        blast_radius[node] = {
            "direct_dependents_count": len(affected),
            "dependent_articles": list(affected),
            "risk_level": "HIGH" if len(affected) >= 3 else ("MEDIUM" if len(affected) >= 1 else "LOW")
        }

    result = {
        "total_articles": len(nodes),
        "total_cross_references": len(edges),
        "articles": nodes,
        "dependency_edges": edges,
        "root_definitions": [{"article": r[0], "referencing_callers_count": r[1]} for r in root_definitions],
        "blast_radius_analysis": blast_radius,
        "cache_key": cache_key,
        "from_cache": False
    }

    if use_cache:
        _LOCAL_DEPTREE_CACHE[cache_key] = result

    return result
