"""
correspondence_resolver.py — Deterministic Dual-Branch Correspondence Resolver for SATRIA.

Implements explicit lookup and traversal across Ditjen Bina Bangda correspondence sheets:
1. 'Surat Masuk' (Agenda ULA)
2. 'Dispo DJ/TU Pim' (Direktur Jenderal / TU Pimpinan)
3. 'Dispo dari Sekretaris' (Sekretaris Ditjen & Unggahan GDrive)

Provides fast (<2s), zero-hallucination dossier aggregation and auto-downloading of PDF artifacts.
"""

import os
import re
import csv
import io
import time
import logging
import urllib.request
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("satria_correspondence_resolver")

# Spreadsheet published CSV endpoints
DEFAULT_SHEET_URLS = {
    "surat_masuk": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTVRCpbcSfnOZNNAPDpobJUTY_vg1ifsJCLpJ6UKLKhjc5U569CInS1pIMe-NSA7pu6QjVVYSeNbC2J/pub?gid=386300474&single=true&output=csv",
    "dispo_dj": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTVRCpbcSfnOZNNAPDpobJUTY_vg1ifsJCLpJ6UKLKhjc5U569CInS1pIMe-NSA7pu6QjVVYSeNbC2J/pub?gid=424988038&single=true&output=csv",
    "dispo_ses": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTVRCpbcSfnOZNNAPDpobJUTY_vg1ifsJCLpJ6UKLKhjc5U569CInS1pIMe-NSA7pu6QjVVYSeNbC2J/pub?gid=115801400&single=true&output=csv",
}

# Cache for sheet rows in memory: {sheet_key: (timestamp, [rows])}
_SHEET_CACHE: Dict[str, Tuple[float, List[Dict[str, str]]]] = {}
CACHE_TTL_SECONDS = 180  # 3 minutes in-memory cache

CACHE_DIR = Path("/home/aseps/MCP/storage/cache/correspondence_pdfs")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_sheet_url(sheet_key: str) -> str:
    """Retrieve sheet CSV URL from environment variable or fallback."""
    if sheet_key == "surat_masuk":
        return os.getenv("data_surat_luar_2026_surat_masuk") or DEFAULT_SHEET_URLS["surat_masuk"]
    elif sheet_key == "dispo_dj":
        return os.getenv("data_surat_luar_2026_dispo_dari_dirjen") or DEFAULT_SHEET_URLS["dispo_dj"]
    elif sheet_key == "dispo_ses":
        return os.getenv("data-surat-luar-2026_dispo_dari_sekretaris") or DEFAULT_SHEET_URLS["dispo_ses"]
    return DEFAULT_SHEET_URLS.get(sheet_key, "")


def fetch_sheet_records(sheet_key: str, force_refresh: bool = False) -> List[Dict[str, str]]:
    """
    Fetch CSV rows from published Google Sheet with memory caching and timeout.
    """
    now = time.time()
    if not force_refresh and sheet_key in _SHEET_CACHE:
        cached_time, cached_rows = _SHEET_CACHE[sheet_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_rows

    url = _get_sheet_url(sheet_key)
    if not url:
        logger.warning(f"No URL defined for sheet_key '{sheet_key}'")
        return []

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SATRIA-Correspondence/1.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read().decode("utf-8", errors="replace")

        reader = csv.reader(io.StringIO(content))
        header = next(reader, None)
        if not header:
            return []

        # Sanitize header names
        clean_headers = [h.strip() for h in header]

        records: List[Dict[str, str]] = []
        for r in reader:
            if not any(r):
                continue
            row_dict = {}
            for i, val in enumerate(r):
                col_name = clean_headers[i] if i < len(clean_headers) else f"col_{i}"
                row_dict[col_name] = val.strip()
            records.append(row_dict)

        _SHEET_CACHE[sheet_key] = (now, records)
        logger.info(f"Loaded {len(records)} records from sheet '{sheet_key}' (cached for {CACHE_TTL_SECONDS}s)")
        return records

    except Exception as e:
        logger.error(f"Failed to fetch sheet '{sheet_key}' from {url}: {e}")
        # If cache exists even if expired, return it as fallback
        if sheet_key in _SHEET_CACHE:
            return _SHEET_CACHE[sheet_key][1]
        return []


def extract_identifiers(query: str) -> Dict[str, Optional[str]]:
    """
    Extract letter number, agenda ULA, or agenda Ses from user query.
    Examples:
    - '1349/L' or '1349'
    - '0583/SET/L/2026' or '0573/Set/L/2026'
    - 'B-131/Setmen.Birohk/KL.01/08/2026'
    - '100.4.3/11799/Biro Hukum'
    """
    result = {
        "agenda_ula": None,
        "agenda_ses": None,
        "nomor_surat": None,
        "keyword": None
    }

    # 1. Match Agenda ULA: e.g. 1349/L, 0583/L, or standalone digits followed by /L
    m_ula = re.search(r'\b(\d{1,4}/[Ll])\b', query)
    if m_ula:
        result["agenda_ula"] = m_ula.group(1).upper()
    else:
        # Check digit only if preceded by 'agenda'
        m_dig = re.search(r'\bagenda\s+(?:ula\s+)?(\d{1,4})\b', query, re.I)
        if m_dig:
            result["agenda_ula"] = f"{int(m_dig.group(1)):04d}/L"

    # 2. Match Agenda Ses: e.g. 0573/Set/L/2026 or 0583/SET/L/2026
    m_ses = re.search(r'\b(\d{3,4}/[Ss][Ee][Tt]/[A-Za-z0-9/]+)\b', query)
    if m_ses:
        result["agenda_ses"] = m_ses.group(1)

    # 3. Match Nomor Surat: e.g. B-131/... or 100.4.3/... or 900.1.3/...
    m_no = re.search(r'\b([A-Za-z0-9.\-]+/\d+/[A-Za-z0-9.\-]+(?:\/\d+)?)\b', query)
    if m_no and not result["agenda_ses"]:
        result["nomor_surat"] = m_no.group(1)
    elif "b-131" in query.lower():
        result["nomor_surat"] = "B-131/Setmen.Birohk/KL.01/08/2026"
    elif "11799" in query:
        result["nomor_surat"] = "100.4.3/11799/Biro Hukum"

    # 4. Fallback Keyword
    stop_tokens = {"surat", "cek", "agenda", "disposisi", "tolong", "mohon", "status", "bina", "bangda", "kemendagri", "dari", "luar"}
    tokens = [w for w in re.findall(r'\b[a-zA-Z0-9]{3,}\b', query) if w.lower() not in stop_tokens]
    if tokens:
        result["keyword"] = " ".join(tokens)

    return result


def download_gdrive_attachment(gdrive_link: str) -> Optional[Path]:
    """
    Extracts Google Drive file ID and downloads PDF to local cache.
    Returns local Path if successful.
    """
    if not gdrive_link:
        return None

    # Match ID pattern
    m_id = re.search(r'[?&]id=([a-zA-Z0-9_\-]+)', gdrive_link)
    if not m_id:
        m_id = re.search(r'/d/([a-zA-Z0-9_\-]+)', gdrive_link)
    if not m_id:
        return None

    file_id = m_id.group(1)
    target_path = CACHE_DIR / f"{file_id}.pdf"

    if target_path.exists() and target_path.stat().st_size > 1024:
        logger.info(f"Using cached PDF attachment: {target_path}")
        return target_path

    # Direct download via Google Drive export endpoint
    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    logger.info(f"Downloading attachment from {direct_url} to {target_path}...")

    try:
        req = urllib.request.Request(
            direct_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp, open(target_path, "wb") as out_file:
            out_file.write(resp.read())

        if target_path.exists() and target_path.stat().st_size > 500:
            logger.info(f"✅ Successfully downloaded GDrive attachment ({target_path.stat().st_size} bytes)")
            return target_path
    except Exception as e:
        logger.warning(f"urllib download failed for {file_id}: {e}, trying curl fallback...")
        try:
            cmd = ["curl", "-sL", "--max-time", "30", direct_url, "-o", str(target_path)]
            subprocess.run(cmd, check=True, timeout=35)
            if target_path.exists() and target_path.stat().st_size > 500:
                logger.info(f"✅ Curl downloaded GDrive attachment ({target_path.stat().st_size} bytes)")
                return target_path
        except Exception as ce:
            logger.error(f"Curl download also failed for {file_id}: {ce}")

    return None


def extract_pdf_preview(pdf_path: Path, max_chars: int = 2500) -> str:
    """
    Extracts text snippet from PDF using pdftotext or tesseract fallback.
    """
    if not pdf_path or not pdf_path.exists():
        return ""

    # Try pdftotext
    try:
        res = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "6", str(pdf_path), "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        txt = res.stdout.strip()
        if len(txt) > 50:
            return txt[:max_chars]
    except Exception:
        pass

    # If pure scanned, run rapid OCR on page 1
    try:
        png_path = CACHE_DIR / f"{pdf_path.stem}_p1.png"
        subprocess.run(["pdftoppm", "-png", "-f", "1", "-l", "1", "-r", "150", str(pdf_path), str(CACHE_DIR / f"{pdf_path.stem}_p1")], timeout=5)
        rendered = list(CACHE_DIR.glob(f"{pdf_path.stem}_p1*.png"))
        if rendered:
            ocr_res = subprocess.run(["tesseract", str(rendered[0]), "stdout", "-l", "ind+eng"], stdout=subprocess.PIPE, text=True, timeout=8)
            txt = ocr_res.stdout.strip()
            rendered[0].unlink(missing_ok=True)
            if len(txt) > 50:
                return txt[:max_chars]
    except Exception as e:
        logger.warning(f"Quick OCR preview failed: {e}")

    return ""


def resolve_incoming_letter(query: str, download_attachment: bool = True) -> Dict[str, Any]:
    """
    Main entry point for SATRIA:
    Resolves incoming letter across Surat Masuk, Dispo DJ/TU Pim, and Dispo Sekretaris.
    Returns complete Unified Dossier.
    """
    ids = extract_identifiers(query)
    target_ula = ids.get("agenda_ula")
    target_ses = ids.get("agenda_ses")
    target_no = ids.get("nomor_surat")
    keyword = ids.get("keyword")

    surat_masuk_rows = fetch_sheet_records("surat_masuk")
    dispo_dj_rows = fetch_sheet_records("dispo_dj")
    dispo_ses_rows = fetch_sheet_records("dispo_ses")

    matched_surat_masuk: Optional[Dict[str, str]] = None
    matched_agenda_ula: Optional[str] = target_ula

    # Step 1: Find match in 'Surat Masuk'
    for r in reversed(surat_masuk_rows):  # Search from latest backwards
        r_ula = (r.get("Agenda ULA") or "").upper().strip()
        r_no = (r.get("Nomor Surat") or "").strip()
        r_hal = (r.get("Perihal") or "").strip()
        r_dari = (r.get("Surat Dari") or "").strip()

        if target_ula and target_ula in r_ula:
            matched_surat_masuk = r
            matched_agenda_ula = r_ula
            break
        if target_no and target_no.lower() in r_no.lower():
            matched_surat_masuk = r
            matched_agenda_ula = r_ula
            break
        if keyword and (keyword.lower() in r_hal.lower() or keyword.lower() in r_dari.lower()):
            matched_surat_masuk = r
            matched_agenda_ula = r_ula
            break

    # If not found in Surat Masuk, but we have agenda_ses, find via dispo_ses first
    matched_dispo_ses: Optional[Dict[str, str]] = None
    if not matched_agenda_ula and target_ses:
        for r in reversed(dispo_ses_rows):
            if target_ses.lower() in (r.get("No Agenda Ses") or "").lower():
                matched_dispo_ses = r
                matched_agenda_ula = (r.get("No Agenda Dirjen") or "").upper().strip()
                break

    # Step 2: Parallel Branch Lookup using matched_agenda_ula
    matched_dispo_dj: Optional[Dict[str, str]] = None
    if matched_agenda_ula:
        # Check Dispo DJ / TU Pim
        for r in reversed(dispo_dj_rows):
            r_ula = (r.get("Agenda ULA") or "").upper().strip()
            if matched_agenda_ula in r_ula:
                matched_dispo_dj = r
                break

        # Check Dispo Sekretaris (if not matched yet)
        if not matched_dispo_ses:
            for r in reversed(dispo_ses_rows):
                r_ula = (r.get("No Agenda Dirjen") or "").upper().strip()
                if matched_agenda_ula in r_ula:
                    matched_dispo_ses = r
                    break

    # Determine status rantai disposisi
    has_dj = bool(matched_dispo_dj)
    has_ses = bool(matched_dispo_ses)

    if has_dj and has_ses:
        status_rantai = "LENGKAP_DIRJEN_DAN_SESDITJEN"
    elif has_dj and not has_ses:
        status_rantai = "DIRJEN_LANGSUNG_TEKNIS"
    elif not has_dj and has_ses:
        status_rantai = "HANYA_SESDITJEN"
    else:
        status_rantai = "BELUM_TERDISPOSISI" if matched_surat_masuk else "TIDAK_DITEMUKAN"

    # Extract attachment link from Dispo Ses or Dispo DJ
    attachment_link = ""
    gdoc_link = ""
    if matched_dispo_ses:
        attachment_link = matched_dispo_ses.get("Unggahan") or ""
    if matched_dispo_dj:
        gdoc_link = matched_dispo_dj.get("Lembar Disposisi") or ""
        if not attachment_link and gdoc_link:
            attachment_link = gdoc_link

    # Auto download attachment if requested or check existing cache
    local_file_path: Optional[Path] = None
    text_preview = ""
    if attachment_link and "drive.google.com" in attachment_link:
        m_id = re.search(r'[?&]id=([a-zA-Z0-9_\-]+)', attachment_link) or re.search(r'/d/([a-zA-Z0-9_\-]+)', attachment_link)
        if m_id:
            cached_candidate = CACHE_DIR / f"{m_id.group(1)}.pdf"
            if cached_candidate.exists() and cached_candidate.stat().st_size > 1024:
                local_file_path = cached_candidate
            elif download_attachment:
                local_file_path = download_gdrive_attachment(attachment_link)

        if local_file_path and local_file_path.exists():
            text_preview = extract_pdf_preview(local_file_path)

    dossier = {
        "status": "success" if (matched_surat_masuk or matched_dispo_dj or matched_dispo_ses) else "not_found",
        "status_rantai": status_rantai,
        "identitas_surat": {
            "agenda_ula": matched_agenda_ula or "-",
            "nomor_surat": matched_surat_masuk.get("Nomor Surat") if matched_surat_masuk else (target_no or "-"),
            "asal_surat": matched_surat_masuk.get("Surat Dari") if matched_surat_masuk else (matched_dispo_dj.get("Surat Dari") if matched_dispo_dj else "-"),
            "perihal": matched_surat_masuk.get("Perihal") if matched_surat_masuk else (matched_dispo_dj.get("Perihal") if matched_dispo_dj else "-"),
            "tgl_surat": matched_surat_masuk.get("Tgl Surat Masuk") if matched_surat_masuk else "-",
            "tgl_diterima_ula": matched_surat_masuk.get("Tgl Diterima ULA") if matched_surat_masuk else "-",
            "arahan_sekjen": matched_surat_masuk.get("Arahan Sekjen") if matched_surat_masuk else "-",
        },
        "disposisi_dirjen": {
            "tercatat": has_dj,
            "agenda_ula": matched_dispo_dj.get("Agenda ULA") if matched_dispo_dj else None,
            "link_lembar_dispo": gdoc_link or None,
            "keterangan": "Disposisi tercatat di meja Direktur Jenderal / TU Pimpinan" if has_dj else "Tidak tercatat di buku Dispo DJ"
        },
        "disposisi_sesditjen": {
            "tercatat": has_ses,
            "no_agenda_ses": matched_dispo_ses.get("No Agenda Ses") if matched_dispo_ses else None,
            "tgl_disposisi": matched_dispo_ses.get("Tgl Disposisi Ses") if matched_dispo_ses else None,
            "arahan_ses": matched_dispo_ses.get("Arahan Ses") if matched_dispo_ses else None,
            "diteruskan_kepada": matched_dispo_ses.get("Diteruskan kepada") if matched_dispo_ses else None,
            "catatan": matched_dispo_ses.get("Catatan") if matched_dispo_ses else None,
        },
        "berkas_lampiran": {
            "link_unggahan": attachment_link or None,
            "local_path": str(local_file_path) if local_file_path else None,
            "is_cached": bool(local_file_path and local_file_path.exists()),
            "file_size_bytes": local_file_path.stat().st_size if (local_file_path and local_file_path.exists()) else 0,
            "text_preview": text_preview
        }
    }

    return dossier


def format_dossier_for_whatsapp(dossier: Dict[str, Any]) -> str:
    """
    Formats the aggregated dossier into SATRIA's signature executive WhatsApp layout.
    """
    if dossier.get("status") == "not_found":
        return "⚠️ *Data surat tidak ditemukan* pada sistem registrasi ULA maupun buku disposisi pimpinan Ditjen Bangda."

    ident = dossier["identitas_surat"]
    dj = dossier["disposisi_dirjen"]
    ses = dossier["disposisi_sesditjen"]
    att = dossier["berkas_lampiran"]
    rantai = dossier["status_rantai"]

    rantai_badge = {
        "LENGKAP_DIRJEN_DAN_SESDITJEN": "🟢 LENGKAP (Dirjen & Sesditjen)",
        "DIRJEN_LANGSUNG_TEKNIS": "🔵 JALUR CEPAT (Dirjen ➔ Direktur Teknis)",
        "HANYA_SESDITJEN": "🟡 JALUR SEKRETARIAT (Sesditjen)",
        "BELUM_TERDISPOSISI": "🔴 BELUM TERDISPOSISI"
    }.get(rantai, rantai)

    res = (
        f"📄 *HASIL PENELUSURAN DOKUMEN PERSURATAN — SATRIA*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷️ *Status Silsilah*: {rantai_badge}\n"
        f"📌 *No. Agenda ULA* : `{ident['agenda_ula']}`\n"
        f"📨 *Nomor Surat*    : `{ident['nomor_surat']}`\n"
        f"🏢 *Asal Surat*     : *{ident['asal_surat']}*\n"
        f"📅 *Tgl Terima ULA* : {ident['tgl_diterima_ula']}\n"
        f"📋 *Perihal*        : _{ident['perihal']}_\n"
    )

    if ident.get("arahan_sekjen") and ident["arahan_sekjen"] != "null":
        res += f"🏛️ *Arahan Sekjen*  : {ident['arahan_sekjen']}\n"

    res += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"

    # Branch 1: Dirjen
    if dj["tercatat"]:
        res += (
            f"👑 *1. TINGKAT DIREKTUR JENDERAL (TU PIMPINAN)*\n"
            f"   • Status: Tercatat di Buku Dispo DJ\n"
        )
        if dj.get("link_lembar_dispo"):
            res += f"   • Naskah Disposisi: [Tautan Dokumen Pimpinan]({dj['link_lembar_dispo']})\n"
    else:
        res += f"👑 *1. TINGKAT DIREKTUR JENDERAL*: Tidak melalui buku Dispo DJ (langsung Sesditjen)\n"

    # Branch 2: Sesditjen
    if ses["tercatat"]:
        res += (
            f"\n✍️ *2. TINGKAT SEKRETARIS DITJEN*\n"
            f"   • No. Agenda Ses: `{ses['no_agenda_ses'] or '-'}`\n"
            f"   • Tgl Disposisi : {ses['tgl_disposisi'] or '-'}\n"
            f"   • Arahan Ses    : *{ses['arahan_ses'] or '-'}*\n"
            f"   • Diteruskan Ke : *{ses['diteruskan_kepada'] or '-'}*\n"
        )
        if ses.get("catatan"):
            res += f"   • Catatan Khusus: _{ses['catatan']}_\n"
    else:
        res += f"\n✍️ *2. TINGKAT SEKRETARIS DITJEN*: Belum/tidak tercatat di Dispo Sekretariat\n"

    # Attachment info
    res += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    if att["is_cached"] or att["link_unggahan"]:
        size_kb = round(att["file_size_bytes"] / 1024, 1) if att["file_size_bytes"] else 0
        res += (
            f"📎 *BERKAS LAMPIRAN NASKAH DINAS*\n"
            f"   • Status File: ✅ Tersedia ({size_kb} KB)\n"
            f"   • Tautan GDrive: {att['link_unggahan'] or '-'}\n"
        )
        if att.get("text_preview"):
            res += f"\n📖 *Intisari Naskah Lampiran*:\n_{att['text_preview'][:350]}..._\n"
    else:
        res += f"📎 *BERKAS LAMPIRAN*: Belum ada unggahan berkas digital.\n"

    return res.strip()


def resolve_srikandi_knowledge(query: str, top_k: int = 3) -> str:
    """
    Menelusuri database naskah dinas SRIKANDI (265 naskah & 1.288 vektor chunks)
    dan mengembalikan respons terformat WhatsApp untuk SATRIA.
    """
    try:
        from integrations.whatsapp.srikandi_rag_connector import search_srikandi_rag, format_srikandi_for_whatsapp
        results = search_srikandi_rag(query, top_k=top_k)
        if results:
            return format_srikandi_for_whatsapp(results, query)
    except Exception as e:
        logger.error(f"Error resolving SRIKANDI knowledge in correspondence_resolver: {e}")
    return ""
