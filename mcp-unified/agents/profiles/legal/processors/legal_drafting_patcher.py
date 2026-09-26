"""
legal_drafting_patcher.py — Structured AST-level Legal Clause Patching.
Menerapkan rekomendasi perbaikan redaksional draf pasal secara presisi tanpa merusak struktur hierarki penomoran ayat/huruf.
"""

import re
import difflib
from typing import Dict, Any, Optional, Tuple


def patch_legal_clause(
    regulation_text: str,
    target_article: str,
    new_clause_text: str,
    target_ayat: Optional[str] = None,
    rationale: str = "Perbaikan redaksional rekomendasi Legal Agent (Anti-Ultra Vires)"
) -> Dict[str, Any]:
    """
    Mengganti isi suatu pasal atau ayat secara presisi dalam teks regulasi.
    """
    normalized_target_art = re.sub(r'\s+', ' ', target_article.strip()).capitalize()
    
    # Cari posisi target article
    art_pattern = re.compile(rf'({re.escape(normalized_target_art)}\b[^\n]*)', re.IGNORECASE)
    match_art = art_pattern.search(regulation_text)
    
    if not match_art:
        return {
            "success": False,
            "error": f"Pasal target '{target_article}' tidak ditemukan dalam draf regulasi.",
            "patched_text": regulation_text,
            "diff": ""
        }

    # Cari batas akhir pasal ini (sampai 'Pasal' berikutnya atau akhir dokumen)
    start_pos = match_art.start()
    next_art_pattern = re.compile(r'\n+(?=Pasal\s+\d+)', re.IGNORECASE)
    next_match = next_art_pattern.search(regulation_text, start_pos + len(match_art.group(0)))
    
    end_pos = next_match.start() if next_match else len(regulation_text)
    current_article_block = regulation_text[start_pos:end_pos]

    # Kasus A: Target adalah ayat tertentu dalam pasal
    if target_ayat:
        norm_ayat = target_ayat.strip()
        if not norm_ayat.startswith("("):
            # jika input "ayat (2)" atau "2"
            digits = re.findall(r'\d+', norm_ayat)
            if digits:
                norm_ayat = f"({digits[0]})"
        
        # Cari ayat dalam block pasal
        ayat_pattern = re.compile(rf'({re.escape(norm_ayat)}\s+[^\(\n]+(?:\n(?!\(\d+\)|\bPasal\b)[^\n]+)*)', re.IGNORECASE)
        match_ayat = ayat_pattern.search(current_article_block)
        
        if not match_ayat:
            return {
                "success": False,
                "error": f"Ayat '{target_ayat}' tidak ditemukan di dalam {normalized_target_art}.",
                "patched_text": regulation_text,
                "diff": ""
            }
        
        # Ganti ayat tersebut
        formatted_new_ayat = new_clause_text.strip()
        if not formatted_new_ayat.startswith("("):
            formatted_new_ayat = f"{norm_ayat} {formatted_new_ayat}"
            
        new_article_block = (
            current_article_block[:match_ayat.start()]
            + formatted_new_ayat
            + current_article_block[match_ayat.end():]
        )
    else:
        # Kasus B: Ganti seluruh isi pasal
        formatted_new_article = new_clause_text.strip()
        if not formatted_new_article.lower().startswith("pasal"):
            formatted_new_article = f"{normalized_target_art}\n{formatted_new_article}"
        new_article_block = formatted_new_article

    # Susun dokumen akhir
    patched_text = regulation_text[:start_pos] + new_article_block + regulation_text[end_pos:]

    # Hitung unified diff
    orig_lines = regulation_text.splitlines(keepends=True)
    patch_lines = patched_text.splitlines(keepends=True)
    diff = "".join(difflib.unified_diff(orig_lines, patch_lines, fromfile="original_draft", tofile="patched_draft"))

    return {
        "success": True,
        "target_article": normalized_target_art,
        "target_ayat": target_ayat,
        "rationale": rationale,
        "patched_text": patched_text,
        "diff": diff,
        "characters_changed": abs(len(patched_text) - len(regulation_text)),
    }
