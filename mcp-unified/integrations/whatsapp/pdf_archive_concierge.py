"""
pdf_archive_concierge.py — Intelligent Archive Concierge (SATRIA WhatsApp Bot)
untuk Permohonan Preview Berkas PDF Sumber Asli & Whitelist Administrator (TASK-301).

Fitur Utama:
1. Fast-Track VIP/Admin Bypass untuk SUPER_ADMIN (+6285717223889 / Asep Safrudin, S.Kom):
   Langsung menerbitkan One-Time Token Canvas Preview (/preview/canvas/{slug}?auth=...)
   tanpa hambatan OTP atau persetujuan manual.
2. Alur Verifikasi Berlapis bagi Pengguna Non-Admin (ASN/Analis):
   - Identifikasi NIP (18 digit) + Email Kedinasan (.go.id)
   - Persetujuan Pakta Integritas Kepatuhan UU PDP No. 27 Tahun 2022 (balas: SETUJU)
   - Disposisi Otomatis (Human-in-the-Loop) ke Administrator +6285717223889
3. One-Click / One-Command Approval oleh Administrator (via WhatsApp atau URL).
4. Pencatatan Audit Trail Lengkap ke SQLite `storage/admin_data/satria_access.db`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

from integrations.whatsapp.whitelist_guard import (
    SUPER_ADMIN_DISPOSITION_PHONE,
    can_approve_pdf_request,
    can_preview_pdf_canvas,
    get_pdf_disposition_admin,
    get_whitelist_user,
    get_whitelist_user_by_nip,
    is_admin_user,
    normalize_phone_number,
)

logger = logging.getLogger("pdf_archive_concierge")

MCP_ROOT = Path("/home/aseps/MCP")
PROJECT_DIR = MCP_ROOT / "workspace/evaluasi-uu23-2014"
MANIFEST_PATH = PROJECT_DIR / "manifests/dokumen_sumber.json"
DAERAH_MANIFEST_PATH = MCP_ROOT / "storage/reports/saran_masukan_daerah_extracted/manifest_ekstraksi.json"
KL_MANIFEST_PATH = MCP_ROOT / "storage/reports/saran_masukan_kl_extracted/manifest_ekstraksi.json"
DAERAH_PDF_BASE = MCP_ROOT / "storage/reports/gdrive_materi_uu23/Sarmak Pemerintah Daerah"
GDRIVE_RAW_BASE = MCP_ROOT / "storage/raw_documents/gdrive_data"
REVIEW_SUMBER_DIR = MCP_ROOT / "storage/reports/review_html_arsip/sumber"
SUMBER_PDF_DIR = MCP_ROOT / "storage/sumber_pdf"
MARKDOWN_CLUSTER_DIR = MCP_ROOT / "storage/processed/saran_masukan_atomik/markdown"

DEFAULT_DB_PATH = MCP_ROOT / "storage/admin_data/satria_access.db"
PUBLIC_BASE_URL = os.getenv("UU23_PUBLIC_BASE", os.getenv("ACCESS_PUBLIC_BASE", "https://uu23.supd2.net")).rstrip("/")
SATRIA_WA_NUMBER = os.getenv("SATRIA_WHATSAPP_NUMBER", "6285217973038")

CANVAS_TOKEN_TTL_SEC = int(os.getenv("SATRIA_CANVAS_TOKEN_TTL", "3600"))       # 1 jam untuk buka link
RENDER_TOKEN_TTL_SEC = int(os.getenv("SATRIA_RENDER_TOKEN_TTL", "1800"))       # 30 menit sesi render halaman
REQUEST_TTL_SEC = int(os.getenv("SATRIA_PDF_REQUEST_TTL", "86400"))            # 24 jam masa berlaku state

ARCHIVE_DDL = """
CREATE TABLE IF NOT EXISTS pdf_preview_requests (
  request_id       TEXT PRIMARY KEY,
  phone            TEXT NOT NULL,
  slug             TEXT NOT NULL,
  doc_title        TEXT,
  state            TEXT NOT NULL
                   CHECK (state IN (
                     'AWAIT_IDENTITY',
                     'AWAIT_PAKTA',
                     'PENDING_ADMIN_APPROVAL',
                     'APPROVED',
                     'REJECTED',
                     'EXPIRED'
                   )),
  nip              TEXT,
  full_name        TEXT,
  email_goid       TEXT,
  pakta_signed_at  TEXT,
  approve_key_hash TEXT,
  approved_by      TEXT,
  approved_at      TEXT,
  canvas_token_id  TEXT,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  expires_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pdf_req_phone ON pdf_preview_requests(phone, state);

CREATE TABLE IF NOT EXISTS pdf_canvas_tokens (
  token_id          TEXT PRIMARY KEY,
  token_hash        TEXT NOT NULL UNIQUE,
  render_token_hash TEXT NOT NULL,
  slug              TEXT NOT NULL,
  phone             TEXT NOT NULL,
  user_id           TEXT NOT NULL,
  full_name         TEXT NOT NULL,
  nip               TEXT NOT NULL,
  email_goid        TEXT,
  role              TEXT NOT NULL,
  is_admin          INTEGER NOT NULL DEFAULT 0,
  request_id        TEXT,
  created_at        TEXT NOT NULL,
  expires_at        TEXT NOT NULL,
  render_expires_at TEXT NOT NULL,
  used_at           TEXT,
  open_count        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_canvas_token_hash ON pdf_canvas_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_canvas_render_hash ON pdf_canvas_tokens(render_token_hash);

CREATE TABLE IF NOT EXISTS pdf_preview_audit (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  at          TEXT NOT NULL,
  action      TEXT NOT NULL,
  slug        TEXT,
  phone_mask  TEXT,
  nip_mask    TEXT,
  full_name   TEXT,
  email_goid  TEXT,
  role        TEXT,
  token_id    TEXT,
  client_ip   TEXT,
  result      TEXT NOT NULL,
  detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_pdf_audit_slug ON pdf_preview_audit(slug, at);

CREATE TABLE IF NOT EXISTS access_audit (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  at          TEXT NOT NULL,
  action      TEXT NOT NULL,
  phone_mask  TEXT,
  nip_mask    TEXT,
  result      TEXT NOT NULL,
  detail      TEXT
);
"""


def _now_wib_str() -> str:
    wib = timezone(timedelta(hours=7))
    return datetime.now(wib).strftime("%Y-%m-%d %H:%M:%S WIB")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _hash_token(raw: str) -> str:
    return hashlib.sha256(f"satria-canvas-v1:{raw}".encode("utf-8")).hexdigest()


def _mask_phone(phone: Optional[str]) -> str:
    if not phone:
        return "***"
    digits = "".join(c for c in str(phone) if c.isdigit() or c == "+")
    if len(digits) <= 7:
        return "***"
    return f"{digits[:5]}***{digits[-3:]}"


def _mask_nip(nip: Optional[str]) -> str:
    if not nip:
        return "-"
    clean = "".join(c for c in str(nip) if c.isdigit())
    if len(clean) <= 7:
        return "***"
    return f"{clean[:4]}***{clean[-3:]}"


def _get_db_path() -> Path:
    custom = os.getenv("SATRIA_ACCESS_DB")
    return Path(custom) if custom else DEFAULT_DB_PATH


@contextmanager
def _db_conn(db_path: Optional[Path] = None):
    target = Path(db_path) if db_path else _get_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(ARCHIVE_DDL)
        yield conn
        conn.commit()
    finally:
        conn.close()


def record_pdf_audit(
    action: str,
    slug: Optional[str],
    phone: Optional[str],
    nip: Optional[str],
    full_name: Optional[str],
    role: Optional[str],
    result: str,
    detail: str = "",
    email_goid: Optional[str] = None,
    token_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Mencatat aktivitas permohonan/pembukaan preview ke pdf_preview_audit dan access_audit."""
    at = _iso(_now_utc())
    p_mask = _mask_phone(phone) if phone else None
    n_mask = _mask_nip(nip) if nip else None
    with _db_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO pdf_preview_audit(
              at, action, slug, phone_mask, nip_mask, full_name,
              email_goid, role, token_id, client_ip, result, detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                at,
                action,
                slug,
                p_mask,
                n_mask,
                full_name,
                email_goid,
                role,
                token_id,
                client_ip,
                result,
                detail,
            ),
        )
        audit_detail = f"slug={slug or '-'} name={full_name or '-'} {detail}".strip()
        conn.execute(
            """
            INSERT INTO access_audit(at, action, phone_mask, nip_mask, result, detail)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (at, f"pdf_{action}", p_mask, n_mask, result, audit_detail),
        )


# ==============================================================================
# KATALOG DOKUMEN & RESOLUSI BERKAS PDF SUMBER
# ==============================================================================

def _slug_of_md(md_name: str) -> str:
    stem = Path(md_name).stem
    return stem[:-6] if stem.endswith("_clean") else stem


def load_document_catalog() -> Dict[str, Dict[str, Any]]:
    """Memuat katalog 43 dokumen klaster beserta metadata instansi dan path berkas."""
    catalog: Dict[str, Dict[str, Any]] = {}
    entries_by_clean: Dict[str, List[Dict[str, Any]]] = {}
    if MANIFEST_PATH.exists():
        try:
            data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            for d in data.get("dokumen", []):
                clean_name = Path(d.get("berkas_bersih", "")).name
                if clean_name:
                    entries_by_clean.setdefault(clean_name, []).append(d)
        except Exception as e:
            logger.warning(f"Gagal membaca manifest dokumen_sumber.json: {e}")

    md_files: List[Tuple[str, Path]] = []
    if MARKDOWN_CLUSTER_DIR.exists():
        for sub in ("kl", "daerah"):
            for p in sorted((MARKDOWN_CLUSTER_DIR / sub).glob("*.md")):
                md_files.append((sub.upper(), p))

    for kategori_default, md_path in md_files:
        slug = _slug_of_md(md_path.name)
        group = entries_by_clean.get(md_path.name, [])
        instansi = ", ".join(
            dict.fromkeys(e.get("asal_instansi") or "" for e in group if e.get("asal_instansi"))
        )
        if not instansi:
            instansi = slug.replace("_", " ")
        family = group[0].get("artefak_komparasi", "TANPA_RECORD") if group else "TANPA_RECORD"
        kategori = group[0].get("kategori", kategori_default) if group else kategori_default
        n_record = sum(int(e.get("n_record", 0)) for e in group)
        dokumen_sumber_list = [e.get("dokumen_sumber", "") for e in group if e.get("dokumen_sumber")]
        catalog[slug] = {
            "slug": slug,
            "instansi": instansi,
            "kategori": kategori,
            "family": family,
            "n_record": n_record,
            "md_path": md_path,
            "dokumen_sumber": dokumen_sumber_list,
        }
    return catalog


def resolve_document_slug(raw_slug: str) -> Optional[Dict[str, Any]]:
    """Mencocokkan input kode slug (case-insensitive, toleran .html/.pdf) ke katalog resmi."""
    if not raw_slug:
        return None
    cleaned = raw_slug.strip().strip("`'\".:;()[]{}")
    for ext in (".html", ".pdf", ".md", "_clean"):
        if cleaned.lower().endswith(ext):
            cleaned = cleaned[: -len(ext)]

    catalog = load_document_catalog()
    if cleaned in catalog:
        return catalog[cleaned]

    low = cleaned.lower()
    for slug, info in catalog.items():
        if slug.lower() == low:
            return info

    # Partial match jika pengguna mengetik misal DAERAH_01_Jatim atau SARM_KL_01
    for slug, info in catalog.items():
        if low in slug.lower() and len(low) >= 6:
            return info
    return None


def _find_original_pdf_for_slug(doc_info: Dict[str, Any]) -> Optional[Path]:
    """Mencari berkas PDF asli untuk slug dari berbagai lokasi penyimpanan lokal."""
    slug = doc_info["slug"]

    # 1. Cek di storage/sumber_pdf/{slug}.pdf
    direct = SUMBER_PDF_DIR / f"{slug}.pdf"
    if direct.is_file() and direct.stat().st_size > 100:
        return direct

    # 2. Cek di storage/reports/review_html_arsip/sumber/{slug}_clean.pdf
    rev_pdf = REVIEW_SUMBER_DIR / f"{slug}_clean.pdf"
    if rev_pdf.is_file() and rev_pdf.stat().st_size > 100:
        return rev_pdf

    # 3. Cek dari manifest Daerah
    dok_sumber = set(doc_info.get("dokumen_sumber") or [])
    if DAERAH_MANIFEST_PATH.exists() and dok_sumber:
        try:
            d_man = json.loads(DAERAH_MANIFEST_PATH.read_text(encoding="utf-8"))
            for item in d_man.get("dokumen", []):
                if item.get("filename_md") in dok_sumber:
                    folder = item.get("gdrive_folder") or ""
                    fname = item.get("gdrive_filename") or ""
                    cand = DAERAH_PDF_BASE / folder / fname
                    if cand.is_file() and cand.suffix.lower() == ".pdf":
                        return cand
        except Exception:
            pass

    # 4. Cek dari manifest KL & storage/raw_documents/gdrive_data
    if KL_MANIFEST_PATH.exists() and dok_sumber:
        try:
            kl_man = json.loads(KL_MANIFEST_PATH.read_text(encoding="utf-8"))
            for item in kl_man:
                if item.get("file_markdown") in dok_sumber:
                    orig_rel = item.get("nama_file_asli") or ""
                    if orig_rel:
                        cand = GDRIVE_RAW_BASE / orig_rel
                        if cand.is_file() and cand.suffix.lower() == ".pdf":
                            return cand
                        fname = Path(orig_rel).name
                        for found in GDRIVE_RAW_BASE.rglob(fname):
                            if found.is_file() and found.suffix.lower() == ".pdf":
                                return found
        except Exception:
            pass

    return None


def ensure_sumber_pdf(slug: str) -> Optional[Path]:
    """
    Memastikan berkas PDF untuk `slug` tersedia di `storage/sumber_pdf/{slug}.pdf`.
    Jika sumber asli berupa PDF di repositori lokal, disalin/ditautkan.
    Jika sumber asli berupa DOCX/Markdown tanpa PDF, dibuatkan PDF pratinjau kanonik via PyMuPDF.
    """
    doc_info = resolve_document_slug(slug)
    if not doc_info:
        return None

    canonical_slug = doc_info["slug"]
    SUMBER_PDF_DIR.mkdir(parents=True, exist_ok=True)
    target_pdf = SUMBER_PDF_DIR / f"{canonical_slug}.pdf"
    if target_pdf.is_file() and target_pdf.stat().st_size > 100:
        return target_pdf

    found_pdf = _find_original_pdf_for_slug(doc_info)
    if found_pdf and found_pdf.is_file():
        if found_pdf.resolve() != target_pdf.resolve():
            shutil.copy2(found_pdf, target_pdf)
        return target_pdf

    # Buat PDF kanonik dari berkas klaster markdown menggunakan PyMuPDF (fitz)
    md_path: Path = doc_info["md_path"]
    if not md_path.is_file():
        return None

    try:
        import fitz

        raw_text = md_path.read_text(encoding="utf-8", errors="replace")
        pdf_doc = fitz.open()
        header_banner = (
            f"DOKUMEN SUMBER EVALUASI UU NO. 23 TAHUN 2014\n"
            f"Kode Dokumen : {canonical_slug}\n"
            f"Asal Instansi: {doc_info['instansi']}\n"
            f"Kategori     : {doc_info['kategori']} ({doc_info['family']})\n"
            + ("=" * 78)
            + "\n\n"
        )
        full_content = header_banner + raw_text
        lines = full_content.splitlines()
        lines_per_page = 52
        for i in range(0, max(1, len(lines)), lines_per_page):
            chunk = "\n".join(lines[i : i + lines_per_page])
            page = pdf_doc.new_page(width=595, height=842)  # A4
            rect = fitz.Rect(42, 42, 553, 800)
            page.insert_textbox(
                rect,
                chunk,
                fontsize=9.5,
                fontname="helv",
                color=(0.1, 0.12, 0.16),
            )
        pdf_doc.save(str(target_pdf))
        pdf_doc.close()
        return target_pdf
    except Exception as e:
        logger.error(f"Gagal membuat PDF fallback untuk {canonical_slug}: {e}")
        return None


# ==============================================================================
# MANAJEMEN TOKEN CANVAS & PERSETUJUAN (SATRIA ACCESS DB)
# ==============================================================================

def issue_canvas_token(
    slug: str,
    phone: str,
    user_id: str,
    full_name: str,
    nip: str,
    role: str,
    is_admin: bool = False,
    email_goid: Optional[str] = None,
    request_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Menerbitkan One-Time Token untuk membuka Secure View-Only Canvas."""
    now = _now_utc()
    token_id = f"ctk_{secrets.token_hex(8)}"
    raw_token = f"{ 'adm' if is_admin else 'usr' }_{secrets.token_urlsafe(24)}"
    raw_render_token = f"rnd_{secrets.token_urlsafe(24)}"

    token_hash = _hash_token(raw_token)
    render_hash = _hash_token(raw_render_token)
    expires_at = _iso(now + timedelta(seconds=CANVAS_TOKEN_TTL_SEC))
    render_expires_at = _iso(now + timedelta(seconds=RENDER_TOKEN_TTL_SEC))

    with _db_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO pdf_canvas_tokens(
              token_id, token_hash, render_token_hash, slug, phone, user_id,
              full_name, nip, email_goid, role, is_admin, request_id,
              created_at, expires_at, render_expires_at, open_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                token_id,
                token_hash,
                render_hash,
                slug,
                normalize_phone_number(phone),
                user_id,
                full_name,
                nip or "-",
                email_goid,
                role,
                1 if is_admin else 0,
                request_id,
                _iso(now),
                expires_at,
                render_expires_at,
            ),
        )

    record_pdf_audit(
        action="token_issued",
        slug=slug,
        phone=phone,
        nip=nip,
        full_name=full_name,
        role=role,
        result="ok",
        detail=f"is_admin={is_admin} token_id={token_id}",
        email_goid=email_goid,
        token_id=token_id,
        db_path=db_path,
    )

    rel_link = f"/preview/canvas/{slug}?auth={raw_token}"
    full_link = f"{PUBLIC_BASE_URL}{rel_link}"
    return {
        "token_id": token_id,
        "token": raw_token,
        "render_token": raw_render_token,
        "slug": slug,
        "expires_at": expires_at,
        "relative_url": rel_link,
        "url": full_link,
    }


def verify_and_consume_canvas_token(
    slug: str,
    raw_token: str,
    client_ip: str = "unknown",
    consume: bool = True,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    Memvalidasi token `auth` pada `/preview/canvas/{slug}?auth=...` dan mencatat ke log audit.
    Token bersifat one-time (sekali pakai untuk membuka sesi Canvas Viewer).
    """
    if not raw_token or not slug:
        return None

    doc_info = resolve_document_slug(slug)
    canonical_slug = doc_info["slug"] if doc_info else slug
    t_hash = _hash_token(raw_token.strip())
    now = _now_utc()
    now_iso = _iso(now)

    with _db_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM pdf_canvas_tokens WHERE token_hash=?", (t_hash,)
        ).fetchone()
        if not row:
            record_pdf_audit(
                action="canvas_open",
                slug=canonical_slug,
                phone=None,
                nip=None,
                full_name=None,
                role=None,
                result="invalid_token",
                client_ip=client_ip,
                db_path=db_path,
            )
            return None

        data = dict(row)
        if data["slug"].lower() != canonical_slug.lower():
            record_pdf_audit(
                action="canvas_open",
                slug=canonical_slug,
                phone=data["phone"],
                nip=data["nip"],
                full_name=data["full_name"],
                role=data["role"],
                result="slug_mismatch",
                token_id=data["token_id"],
                client_ip=client_ip,
                db_path=db_path,
            )
            return None

        if data["expires_at"] < now_iso:
            record_pdf_audit(
                action="canvas_open",
                slug=canonical_slug,
                phone=data["phone"],
                nip=data["nip"],
                full_name=data["full_name"],
                role=data["role"],
                result="expired",
                token_id=data["token_id"],
                client_ip=client_ip,
                db_path=db_path,
            )
            return None

        if data.get("used_at") is not None:
            record_pdf_audit(
                action="canvas_open",
                slug=canonical_slug,
                phone=data["phone"],
                nip=data["nip"],
                full_name=data["full_name"],
                role=data["role"],
                result="already_used",
                token_id=data["token_id"],
                client_ip=client_ip,
                db_path=db_path,
            )
            return None

        # Buat render_token baru untuk pemuatan halaman-halaman canvas pada sesi ini
        session_render_token = f"rnd_{secrets.token_urlsafe(24)}"
        session_render_hash = _hash_token(session_render_token)
        render_exp = _iso(now + timedelta(seconds=RENDER_TOKEN_TTL_SEC))

        if consume:
            conn.execute(
                """
                UPDATE pdf_canvas_tokens
                SET used_at=?, open_count=open_count+1,
                    render_token_hash=?, render_expires_at=?
                WHERE token_id=?
                """,
                (now_iso, session_render_hash, render_exp, data["token_id"]),
            )

    wib_time = _now_wib_str()
    watermark = f"PREVIEW TERBATAS KEMENDAGRI — {data['full_name']} / {data['nip']} — {wib_time}"

    record_pdf_audit(
        action="canvas_open",
        slug=canonical_slug,
        phone=data["phone"],
        nip=data["nip"],
        full_name=data["full_name"],
        role=data["role"],
        result="opened",
        detail=f"watermark={watermark}",
        email_goid=data.get("email_goid"),
        token_id=data["token_id"],
        client_ip=client_ip,
        db_path=db_path,
    )

    data["render_token"] = session_render_token
    data["watermark_text"] = watermark
    data["opened_at_wib"] = wib_time
    return data


def verify_canvas_render_token(
    slug: str,
    raw_render_token: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Memvalidasi token sesi render halaman gambar Canvas (`?rt=...`)."""
    if not raw_render_token or not slug:
        return None
    doc_info = resolve_document_slug(slug)
    canonical_slug = doc_info["slug"] if doc_info else slug
    r_hash = _hash_token(raw_render_token.strip())
    now_iso = _iso(_now_utc())

    with _db_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM pdf_canvas_tokens WHERE render_token_hash=?", (r_hash,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        if data["slug"].lower() != canonical_slug.lower():
            return None
        if data["render_expires_at"] < now_iso:
            return None
        return data


# ==============================================================================
# DETEKSI INTENT & PERCAKAPAN INTERAKTIF SATRIA WHATSAPP CONCIERGE
# ==============================================================================

_SLUG_PATTERN = re.compile(r"\b(SARM_(?:DAERAH|KL)_[A-Za-z0-9_]+)\b", re.IGNORECASE)
_CODE_COLON_PATTERN = re.compile(
    r"(?:kode|slug|dokumen)\s*[:=]\s*([A-Za-z0-9_.\-]+)", re.IGNORECASE
)
_EMAIL_GOID_PATTERN = re.compile(
    r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.go\.id)\b", re.IGNORECASE
)
_NIP_18_PATTERN = re.compile(r"\b(19\d{16}|20\d{16})\b")
_NIP_SPACED_PATTERN = re.compile(
    r"\b(19\d{6}|20\d{6})[\s.\-]?(\d{6})[\s.\-]?(\d{1})[\s.\-]?(\d{3})\b"
)
_APPROVE_CMD_PATTERN = re.compile(
    r"^(?:!|\b)(?:setujui|approve|acc)\s+(REQ-[A-Za-z0-9\-]+)\b", re.IGNORECASE
)
_REJECT_CMD_PATTERN = re.compile(
    r"^(?:!|\b)(?:tolak|reject)\s+(REQ-[A-Za-z0-9\-]+)(?:\s+(.+))?$", re.IGNORECASE
)


def extract_slug_from_message(text: str) -> Optional[str]:
    """Mengekstrak kode slug dokumen (mis. SARM_DAERAH_01_Jatim) dari pesan WhatsApp."""
    if not text:
        return None
    m = _SLUG_PATTERN.search(text)
    if m:
        return m.group(1).strip()
    m2 = _CODE_COLON_PATTERN.search(text)
    if m2:
        cand = m2.group(1).strip().rstrip(".,;)")
        resolved = resolve_document_slug(cand)
        if resolved:
            return resolved["slug"]
        if cand.upper().startswith("SARM_"):
            return cand
    return None


def extract_nip(text: str) -> Optional[str]:
    if not text:
        return None
    m = _NIP_18_PATTERN.search(text)
    if m:
        return m.group(1)
    m2 = _NIP_SPACED_PATTERN.search(text)
    if m2:
        return "".join(m2.groups())
    return None


def extract_goid_email(text: str) -> Optional[str]:
    if not text:
        return None
    m = _EMAIL_GOID_PATTERN.search(text)
    return m.group(1).lower() if m else None


def get_active_pdf_request(phone: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Mengambil permohonan PDF aktif (AWAIT_IDENTITY / AWAIT_PAKTA) untuk nomor pemohon."""
    clean_phone = normalize_phone_number(phone)
    if not clean_phone:
        return None
    now_iso = _iso(_now_utc())
    with _db_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM pdf_preview_requests
            WHERE phone=? AND state IN ('AWAIT_IDENTITY', 'AWAIT_PAKTA')
            ORDER BY updated_at DESC LIMIT 1
            """,
            (clean_phone,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        if data["expires_at"] < now_iso:
            conn.execute(
                "UPDATE pdf_preview_requests SET state='EXPIRED', updated_at=? WHERE request_id=?",
                (now_iso, data["request_id"]),
            )
            return None
        return data


def is_pdf_archive_intent(
    sender_phone: str,
    message_text: str,
    db_path: Optional[Path] = None,
) -> bool:
    """
    Mendeteksi apakah pesan masuk merupakan:
    1. Permohonan baru preview PDF sumber (memuat kata kunci preview/PDF sumber/slug SARM_*),
    2. Perintah persetujuan Administrator (SETUJUI REQ-... / TOLAK REQ-...), atau
    3. Kelanjutan sesi verifikasi NIP+Email (.go.id) / Pakta Integritas (SETUJU) yang sedang aktif.
    """
    if not message_text:
        return False
    cleaned = message_text.strip()
    for prefix in ("!satria", "@satria", "tanya satria:", "tanya satria", "satria,", "satria:"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break

    low = cleaned.lower()

    # 1. Perintah Admin Approve / Reject
    if _APPROVE_CMD_PATTERN.match(cleaned) or _REJECT_CMD_PATTERN.match(cleaned):
        return True

    # 2. Permohonan eksplisit preview PDF sumber / kode slug
    slug = extract_slug_from_message(cleaned)
    has_preview_kw = any(
        kw in low
        for kw in (
            "preview pdf",
            "pdf sumber",
            "naskah asli",
            "berkas pdf",
            "minta akses preview",
            "preview naskah",
            "canvas preview",
            "sumber kode:",
            "sumber kode :",
        )
    )
    if slug and (has_preview_kw or "preview" in low or "pdf" in low or "kode" in low):
        return True
    if has_preview_kw:
        return True

    # 3. Cek state aktif untuk pengguna non-admin yang sedang dalam alur verifikasi
    active_req = get_active_pdf_request(sender_phone, db_path=db_path)
    if active_req:
        if active_req["state"] == "AWAIT_IDENTITY":
            if extract_nip(cleaned) or extract_goid_email(cleaned) or "@" in cleaned or "batal" in low:
                return True
        elif active_req["state"] == "AWAIT_PAKTA":
            if low in ("setuju", "ya setuju", "saya setuju", "tidak", "batal") or "setuju" in low:
                return True

    return False


async def _send_wa_notification(
    phone: str,
    message: str,
    notify_fn: Optional[Callable[[str, str], Coroutine[Any, Any, bool]]] = None,
) -> bool:
    """Mengirim pesan WhatsApp ke penerima (Admin atau Pemohon) via notifier atau Baileys gateway."""
    if notify_fn is not None:
        try:
            return await notify_fn(phone, message)
        except Exception as e:
            logger.warning(f"Custom notify_fn gagal ke {phone}: {e}")
            return False

    try:
        from integrations.whatsapp.client import WhatsAppClient

        digits = "".join(c for c in normalize_phone_number(phone) if c.isdigit())
        if not digits:
            return False
        jid = f"{digits}@s.whatsapp.net"
        client = WhatsAppClient()
        await client.send_message(chat_id=jid, text=message)
        return True
    except Exception as e:
        logger.warning(f"Pengiriman WA langsung ke {phone} dilewati/offline: {e}")
        return False


def approve_pdf_request_by_id(
    request_id: str,
    approver_phone: str,
    approve_key: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Menyetujui permohonan preview PDF (`request_id`), menerbitkan One-Time Token Canvas,
    dan mencatat audit trail. Dapat dipanggil via perintah WhatsApp Admin maupun One-Click Link.
    """
    req_id_clean = (request_id or "").strip().upper()
    with _db_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM pdf_preview_requests WHERE UPPER(request_id)=?",
            (req_id_clean,),
        ).fetchone()
        if not row:
            return False, f"Permohonan dengan nomor `{req_id_clean}` tidak ditemukan.", None
        req_data = dict(row)

    # Validasi hak akses admin atau approve_key
    if approve_key is not None:
        if not req_data.get("approve_key_hash") or not hmac.compare_digest(
            _hash_token(approve_key), req_data["approve_key_hash"]
        ):
            return False, "Kunci persetujuan (approve key) tidak valid.", None
    else:
        if not can_approve_pdf_request(approver_phone):
            return False, "Anda tidak memiliki izin `pdf_archive_approve_request`.", None

    if req_data["state"] == "APPROVED":
        return False, f"Permohonan `{req_id_clean}` sudah pernah disetujui sebelumnya.", req_data

    token_info = issue_canvas_token(
        slug=req_data["slug"],
        phone=req_data["phone"],
        user_id=f"asn_{req_data.get('nip') or req_data['phone'][-4:]}",
        full_name=req_data.get("full_name") or "Pemohon ASN",
        nip=req_data.get("nip") or "-",
        role="ASN_VERIFIED_VIEWER",
        is_admin=False,
        email_goid=req_data.get("email_goid"),
        request_id=req_data["request_id"],
        db_path=db_path,
    )

    now_iso = _iso(_now_utc())
    admin_norm = normalize_phone_number(approver_phone) or SUPER_ADMIN_DISPOSITION_PHONE
    with _db_conn(db_path) as conn:
        conn.execute(
            """
            UPDATE pdf_preview_requests
            SET state='APPROVED', approved_by=?, approved_at=?,
                canvas_token_id=?, updated_at=?
            WHERE request_id=?
            """,
            (
                admin_norm,
                now_iso,
                token_info["token_id"],
                now_iso,
                req_data["request_id"],
            ),
        )

    record_pdf_audit(
        action="request_approved",
        slug=req_data["slug"],
        phone=req_data["phone"],
        nip=req_data.get("nip"),
        full_name=req_data.get("full_name"),
        role="ASN_VERIFIED_VIEWER",
        result="approved",
        detail=f"request_id={req_data['request_id']} approved_by={admin_norm}",
        email_goid=req_data.get("email_goid"),
        token_id=token_info["token_id"],
        db_path=db_path,
    )

    req_data["token_info"] = token_info
    req_data["state"] = "APPROVED"
    return True, "Permohonan disetujui.", req_data


async def intent_pdf_archive_request(
    sender_phone: str,
    message_text: str,
    sender_name: Optional[str] = None,
    notify_fn: Optional[Callable[[str, str], Coroutine[Any, Any, bool]]] = None,
    db_path: Optional[Path] = None,
) -> str:
    """
    Intent Handler Utama: `intent_pdf_archive_request` pada SATRIA WhatsApp Bot.
    Menangani:
    - Fast-track Canvas Preview Link untuk Super Admin (`085717223889`).
    - Alur verifikasi NIP + Email `.go.id` + Pakta Integritas UU PDP No. 27/2022 untuk pengguna non-admin.
    - Notifikasi disposisi otomatis & persetujuan one-click/command oleh Administrator.
    """
    clean_phone = normalize_phone_number(sender_phone)
    cleaned = (message_text or "").strip()
    for prefix in ("!satria", "@satria", "tanya satria:", "tanya satria", "satria,", "satria:"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break
    low = cleaned.lower()

    # ------------------------------------------------------------------
    # 1. Perintah Persetujuan / Penolakan oleh Administrator
    # ------------------------------------------------------------------
    m_app = _APPROVE_CMD_PATTERN.match(cleaned)
    if m_app:
        if not can_approve_pdf_request(clean_phone):
            return (
                "⛔ *AKSES DITOLAK*\n\n"
                "Hanya Administrator Sistem (`SUPER_ADMIN`) yang memiliki izin "
                "`pdf_archive_approve_request` untuk menyetujui permohonan preview PDF sumber."
            )
        req_id = m_app.group(1).upper()
        ok, msg, req_data = approve_pdf_request_by_id(
            req_id, approver_phone=clean_phone, db_path=db_path
        )
        if not ok or not req_data:
            return f"⚠️ *GAGAL MENYETUJUI PERMOHONAN*\n\n{msg}"

        token_info = req_data["token_info"]
        user_notif = (
            "✅ *PERMOHONAN PREVIEW PDF DISETUJUI ADMINISTRATOR*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Yth. Bapak/Ibu *{req_data.get('full_name')}* (`{req_data.get('nip')}`),\n\n"
            f"Permohonan akses preview naskah sumber kode *`{req_data['slug']}`* "
            f"telah disetujui oleh Administrator Sistem.\n\n"
            f"🔗 *Tautan Sekali-Pakai (Secure View-Only Canvas):*\n"
            f"{token_info['url']}\n"
            f"_(Path internal: `{token_info['relative_url']}`)_\n\n"
            "🛡️ *Ketentuan Keamanan Canvas:*\n"
            "• Beroperasi dalam mode *View-Only / Print-Disabled* (tanpa tombol unduh).\n"
            "• Dilengkapi *Dynamic Watermark Overlay* beridentitas NIP & waktu akses.\n"
            "• Tautan hanya berlaku untuk 1 (satu) kali pembukaan sesi."
        )
        await _send_wa_notification(req_data["phone"], user_notif, notify_fn=notify_fn)
        return (
            f"✅ *DISPOSISI PERSETUJUAN BERHASIL ({req_id})*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Pemohon:* {req_data.get('full_name')} ({req_data['phone']})\n"
            f"• *NIP / Email:* {req_data.get('nip')} / {req_data.get('email_goid')}\n"
            f"• *Dokumen:* `{req_data['slug']}`\n"
            f"• *Token Canvas:* `{token_info['token_id']}`\n\n"
            f"Tautan *One-Time View-Only Canvas* telah dikirimkan ke WhatsApp pemohon:\n"
            f"{token_info['url']}"
        )

    m_rej = _REJECT_CMD_PATTERN.match(cleaned)
    if m_rej:
        if not can_approve_pdf_request(clean_phone):
            return "⛔ *AKSES DITOLAK*: Anda tidak memiliki izin `pdf_archive_approve_request`."
        req_id = m_rej.group(1).upper()
        reason = (m_rej.group(2) or "Tidak memenuhi kriteria verifikasi kedinasan").strip()
        now_iso = _iso(_now_utc())
        with _db_conn(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM pdf_preview_requests WHERE UPPER(request_id)=?", (req_id,)
            ).fetchone()
            if not row:
                return f"⚠️ Permohonan `{req_id}` tidak ditemukan."
            req_data = dict(row)
            conn.execute(
                "UPDATE pdf_preview_requests SET state='REJECTED', approved_by=?, updated_at=? WHERE request_id=?",
                (clean_phone, now_iso, req_data["request_id"]),
            )
        record_pdf_audit(
            action="request_rejected",
            slug=req_data["slug"],
            phone=req_data["phone"],
            nip=req_data.get("nip"),
            full_name=req_data.get("full_name"),
            role="ASN_APPLICANT",
            result="rejected",
            detail=reason,
            db_path=db_path,
        )
        await _send_wa_notification(
            req_data["phone"],
            f"⚠️ Permohonan preview PDF kode `{req_data['slug']}` (`{req_id}`) belum dapat disetujui: {reason}.",
            notify_fn=notify_fn,
        )
        return f"✅ Permohonan `{req_id}` (`{req_data['slug']}`) telah ditolak dan pemohon telah diberitahu."

    # ------------------------------------------------------------------
    # 2. Cek apakah pemohon adalah Administrator / Pemegang Hak Canvas Preview
    # ------------------------------------------------------------------
    is_vip_admin = is_admin_user(clean_phone) or can_preview_pdf_canvas(clean_phone)
    raw_slug = extract_slug_from_message(cleaned)

    if is_vip_admin:
        admin_profile = get_whitelist_user(clean_phone) or get_pdf_disposition_admin()
        admin_name = admin_profile.get("full_name", "Asep Safrudin, S.Kom")
        admin_nip = admin_profile.get("nip", "197809112025211014")
        admin_uid = admin_profile.get("user_id", "asep_safrudin")
        admin_role = admin_profile.get("role", "SUPER_ADMIN")

        if not raw_slug:
            return (
                f"👑 *LAYANAN VIP CONCIERGE ARSIP PDF — SATRIA*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Selamat bertugas, Bapak *{admin_name}* (`{admin_role}`).\n\n"
                f"Akun Anda memiliki hak istimewa *`pdf_archive_canvas_preview`* & *`pdf_archive_approve_request`* "
                f"(Bypass OTP & Persetujuan Manual).\n\n"
                f"📌 *Cara Membuka Canvas Preview Instan:*\n"
                f"Kirimkan kode dokumen (`slug`), misalnya:\n"
                f"`Halo SATRIA, saya ingin preview PDF sumber kode: SARM_DAERAH_01_Jatim`"
            )

        doc_info = resolve_document_slug(raw_slug)
        canonical_slug = doc_info["slug"] if doc_info else raw_slug
        instansi_label = doc_info["instansi"] if doc_info else canonical_slug
        ensure_sumber_pdf(canonical_slug)

        token_info = issue_canvas_token(
            slug=canonical_slug,
            phone=clean_phone,
            user_id=admin_uid,
            full_name=admin_name,
            nip=admin_nip,
            role=admin_role,
            is_admin=True,
            db_path=db_path,
        )

        return (
            f"👑 *AKSES VIP SUPER ADMIN — CANVAS PREVIEW INSTAN*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Selamat bertugas, Bapak *{admin_name}* (*{admin_role}*).\n"
            f"Otorisasi Whitelist Administrator (`{clean_phone}`) terverifikasi — *Bypass OTP & Persetujuan Manual Aktif*.\n\n"
            f"📄 *Detail Naskah Sumber:*\n"
            f"• *Kode Dokumen:* `{canonical_slug}`\n"
            f"• *Asal Instansi:* {instansi_label}\n"
            f"• *Mode Tampilan:* *View-Only / Print-Disabled Canvas Mode* (Tanpa Unduh Publik)\n\n"
            f"🔗 *Tautan Sekali-Pakai (One-Time Token Canvas Link):*\n"
            f"{token_info['url']}\n"
            f"_(Path Portal: `{token_info['relative_url']}`)_\n\n"
            f"🛡️ _Catatan Audit: Pembukaan tautan ini dilindungi Dynamic Watermark dan tercatat otomatis pada `satria_access.db`._"
        )

    # ------------------------------------------------------------------
    # 3. Alur Pengguna Non-Admin (ASN / Analis Luar)
    # ------------------------------------------------------------------
    active_req = get_active_pdf_request(clean_phone, db_path=db_path)

    # Jika pengguna mengirim permohonan baru dengan slug dokumen:
    if raw_slug:
        doc_info = resolve_document_slug(raw_slug)
        if not doc_info:
            return (
                f"⚠️ *KODE DOKUMEN TIDAK DITEMUKAN*\n\n"
                f"Kode dokumen *`{raw_slug}`* tidak terdaftar dalam katalog Evaluasi UU No. 23 Tahun 2014.\n"
                f"Pastikan Anda menekan tombol *Minta Akses Preview Asli via WhatsApp SATRIA* langsung dari halaman `/dokumen/{{slug}}.html`."
            )

        canonical_slug = doc_info["slug"]
        ensure_sumber_pdf(canonical_slug)
        now = _now_utc()
        req_id = f"REQ-{now.strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

        # Cek apakah di pesan pertama sudah disertakan NIP + email .go.id
        nip_in_msg = extract_nip(cleaned)
        email_in_msg = extract_goid_email(cleaned)
        wl_user = get_whitelist_user(clean_phone)
        resolved_name = (
            (wl_user.get("full_name") if wl_user else None)
            or sender_name
            or "Aparatur Sipil Negara"
        )

        initial_state = "AWAIT_PAKTA" if (nip_in_msg and email_in_msg) else "AWAIT_IDENTITY"

        with _db_conn(db_path) as conn:
            # Batalkan permohonan menggantung sebelumnya dari nomor yang sama
            conn.execute(
                """
                UPDATE pdf_preview_requests
                SET state='EXPIRED', updated_at=?
                WHERE phone=? AND state IN ('AWAIT_IDENTITY', 'AWAIT_PAKTA')
                """,
                (_iso(now), clean_phone),
            )
            conn.execute(
                """
                INSERT INTO pdf_preview_requests(
                  request_id, phone, slug, doc_title, state, nip, full_name, email_goid,
                  created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    req_id,
                    clean_phone,
                    canonical_slug,
                    doc_info["instansi"],
                    initial_state,
                    nip_in_msg,
                    resolved_name,
                    email_in_msg,
                    _iso(now),
                    _iso(now),
                    _iso(now + timedelta(seconds=REQUEST_TTL_SEC)),
                ),
            )

        record_pdf_audit(
            action="request_initiated",
            slug=canonical_slug,
            phone=clean_phone,
            nip=nip_in_msg,
            full_name=resolved_name,
            role="ASN_APPLICANT",
            result="await_pakta" if initial_state == "AWAIT_PAKTA" else "await_identity",
            detail=f"request_id={req_id}",
            email_goid=email_in_msg,
            db_path=db_path,
        )

        if initial_state == "AWAIT_PAKTA":
            return _format_pakta_integritas_prompt(
                req_id=req_id,
                slug=canonical_slug,
                instansi=doc_info["instansi"],
                nip=nip_in_msg or "",
                email_goid=email_in_msg or "",
                full_name=resolved_name,
            )

        return (
            f"🏛️ *SATRIA ARCHIVE CONCIERGE — VERIFIKASI AKSES PDF SUMBER*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Halo! Permohonan pratinjau naskah fisik asli telah diterima:\n"
            f"• *Nomor Tiket:* `{req_id}`\n"
            f"• *Kode Dokumen:* `{canonical_slug}`\n"
            f"• *Asal Instansi:* {doc_info['instansi']}\n\n"
            f"🔐 *Tahap 1/2 — Identifikasi Aparatur (ASN):*\n"
            f"Sesuai kebijakan Tata Kelola & Pelindungan Data Pribadi (UU No. 27/2022), "
            f"mohon balas pesan ini dengan mencantumkan **NIP (18 digit)** dan **Email Kedinasan (`.go.id`)** Anda.\n\n"
            f"📌 *Contoh Format Balasan:*\n"
            f"`198501012010011001#nama.anda@kemendagri.go.id`"
        )

    # Jika tidak ada slug baru, periksa apakah pengguna sedang dalam sesi `active_req`
    if not active_req:
        return (
            "🏛️ *SATRIA ARCHIVE CONCIERGE*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Untuk mengajukan permohonan pratinjau berkas PDF sumber asli, "
            "silakan klik tombol *💬 Minta Akses Preview Asli via WhatsApp SATRIA* pada halaman dokumen di portal, "
            "atau ketik:\n"
            "`Halo SATRIA, saya ingin preview PDF sumber kode: SARM_DAERAH_01_Jatim`"
        )

    if low in ("batal", "cancel", "batalkan"):
        with _db_conn(db_path) as conn:
            conn.execute(
                "UPDATE pdf_preview_requests SET state='EXPIRED', updated_at=? WHERE request_id=?",
                (_iso(_now_utc()), active_req["request_id"]),
            )
        return f"❌ Permohonan preview PDF `{active_req['request_id']}` (`{active_req['slug']}`) telah dibatalkan."

    # ------------------------------------------------------------------
    # Tahap 1 -> Tahap 2: Verifikasi NIP + Email Kedinasan (.go.id)
    # ------------------------------------------------------------------
    if active_req["state"] == "AWAIT_IDENTITY":
        nip = extract_nip(cleaned) or active_req.get("nip")
        email_goid = extract_goid_email(cleaned) or active_req.get("email_goid")

        if not nip or not email_goid:
            missing = []
            if not nip:
                missing.append("*NIP 18 digit*")
            if not email_goid:
                missing.append("*Email Kedinasan resmi berakhiran `.go.id`*")
            return (
                f"⚠️ *DATA IDENTITAS BELUM LENGKAP ({active_req['request_id']})*\n\n"
                f"Mohon lengkapi {' dan '.join(missing)} Anda untuk melanjutkan permohonan preview `{active_req['slug']}`.\n\n"
                f"📌 *Contoh Balasan:*\n"
                f"`198501012010011001#nama@kemendagri.go.id`"
            )

        # Coba perkaya nama dari whitelist atau database kepegawaian jika tersedia
        full_name = active_req.get("full_name") or sender_name or ""
        wl_by_nip = get_whitelist_user_by_nip(nip)
        if wl_by_nip and wl_by_nip.get("full_name"):
            full_name = wl_by_nip["full_name"]
        else:
            try:
                from integrations.whatsapp.onboarding_manager import lookup_employee_by_nip

                emp = lookup_employee_by_nip(nip)
                if emp and emp.get("nama"):
                    full_name = emp["nama"]
            except Exception:
                pass
        if not full_name or full_name == "Aparatur Sipil Negara":
            # Ambil dari bagian teks jika ada format NIP#EMAIL#NAMA atau prefix email
            local_part = email_goid.split("@")[0].replace(".", " ").replace("_", " ").title()
            full_name = sender_name or local_part or f"ASN {nip[:6]}"

        now_iso = _iso(_now_utc())
        with _db_conn(db_path) as conn:
            conn.execute(
                """
                UPDATE pdf_preview_requests
                SET state='AWAIT_PAKTA', nip=?, email_goid=?, full_name=?, updated_at=?
                WHERE request_id=?
                """,
                (nip, email_goid, full_name, now_iso, active_req["request_id"]),
            )

        record_pdf_audit(
            action="identity_verified",
            slug=active_req["slug"],
            phone=clean_phone,
            nip=nip,
            full_name=full_name,
            role="ASN_APPLICANT",
            result="ok",
            detail=f"request_id={active_req['request_id']}",
            email_goid=email_goid,
            db_path=db_path,
        )

        return _format_pakta_integritas_prompt(
            req_id=active_req["request_id"],
            slug=active_req["slug"],
            instansi=active_req.get("doc_title") or active_req["slug"],
            nip=nip,
            email_goid=email_goid,
            full_name=full_name,
        )

    # ------------------------------------------------------------------
    # Tahap 2: Persetujuan Pakta Integritas UU PDP No. 27/2022 ("SETUJU")
    # ------------------------------------------------------------------
    if active_req["state"] == "AWAIT_PAKTA":
        if "setuju" not in low:
            return (
                f"📜 *KONFIRMASI PAKTA INTEGRITAS DIPERLUKAN ({active_req['request_id']})*\n\n"
                f"Untuk melanjutkan permohonan preview naskah `{active_req['slug']}`, "
                f"mohon balas dengan mengetik:\n"
                f"*`SETUJU`*\n\n"
                f"_(Atau ketik `BATAL` untuk membatalkan permohonan)._"
            )

        now = _now_utc()
        now_iso = _iso(now)
        raw_approve_key = secrets.token_urlsafe(18)
        approve_key_hash = _hash_token(raw_approve_key)

        with _db_conn(db_path) as conn:
            conn.execute(
                """
                UPDATE pdf_preview_requests
                SET state='PENDING_ADMIN_APPROVAL',
                    pakta_signed_at=?,
                    approve_key_hash=?,
                    updated_at=?
                WHERE request_id=?
                """,
                (now_iso, approve_key_hash, now_iso, active_req["request_id"]),
            )

        record_pdf_audit(
            action="pakta_signed",
            slug=active_req["slug"],
            phone=clean_phone,
            nip=active_req.get("nip"),
            full_name=active_req.get("full_name"),
            role="ASN_APPLICANT",
            result="pending_admin_approval",
            detail=f"request_id={active_req['request_id']}",
            email_goid=active_req.get("email_goid"),
            db_path=db_path,
        )

        # Kirim notifikasi disposisi otomatis ke Administrator (085717223889)
        admin_info = get_pdf_disposition_admin()
        admin_phone = admin_info.get("phone_number") or SUPER_ADMIN_DISPOSITION_PHONE
        one_click_url = (
            f"{PUBLIC_BASE_URL}/preview/approve/{active_req['request_id']}?key={raw_approve_key}"
        )

        admin_notif = (
            "🔔 *DISPOSISI PERMOHONAN PREVIEW PDF SUMBER — SATRIA*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Yth. Administrator (*{admin_info.get('full_name', 'Asep Safrudin, S.Kom')}*),\n"
            "Terdapat permohonan akses *In-App Canvas Preview* naskah asli yang telah menandatangani Pakta Integritas UU PDP No. 27/2022:\n\n"
            f"• *ID Tiket:* `{active_req['request_id']}`\n"
            f"• *Kode Dokumen:* `{active_req['slug']}` ({active_req.get('doc_title')})\n"
            f"• *Nama Pemohon:* {active_req.get('full_name')}\n"
            f"• *NIP:* `{active_req.get('nip')}`\n"
            f"• *Email Dinas:* `{active_req.get('email_goid')}`\n"
            f"• *WhatsApp:* `{clean_phone}`\n"
            f"• *Pakta Integritas UU PDP:* ✅ DISETUJUI ({_now_wib_str()})\n\n"
            "⚡ *Opsi Persetujuan Cepat (Human-in-the-Loop):*\n"
            f"1. *One-Click Approval URL:*\n{one_click_url}\n"
            f"2. *Balas Chat WhatsApp Ini:*\n"
            f"   Ketik: `SETUJUI {active_req['request_id']}`\n"
            f"   _(Atau ketik `TOLAK {active_req['request_id']}` untuk menolak)_"
        )
        await _send_wa_notification(admin_phone, admin_notif, notify_fn=notify_fn)

        record_pdf_audit(
            action="admin_notified",
            slug=active_req["slug"],
            phone=admin_phone,
            nip=active_req.get("nip"),
            full_name=active_req.get("full_name"),
            role="SUPER_ADMIN",
            result="sent",
            detail=f"request_id={active_req['request_id']} to={admin_phone}",
            email_goid=active_req.get("email_goid"),
            db_path=db_path,
        )

        return (
            f"✅ *PAKTA INTEGRITAS DITERIMA — MENUNGGU OTORISASI ADMIN*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Terima kasih, Bapak/Ibu *{active_req.get('full_name')}*.\n\n"
            f"• *Nomor Tiket:* `{active_req['request_id']}`\n"
            f"• *Dokumen:* `{active_req['slug']}`\n"
            f"• *NIP & Email:* `{active_req.get('nip')}` / `{active_req.get('email_goid')}`\n"
            f"• *Pakta Integritas UU PDP No. 27/2022:* *TERCATAT*\n\n"
            f"📨 Notifikasi persetujuan telah dikirimkan secara otomatis ke Administrator Sistem "
            f"(`085717223889`). Begitu disetujui, tautan *Secure View-Only Canvas* akan langsung dikirimkan ke WhatsApp Anda."
        )

    return "Permohonan Anda sedang diproses."


def _format_pakta_integritas_prompt(
    req_id: str,
    slug: str,
    instansi: str,
    nip: str,
    email_goid: str,
    full_name: str,
) -> str:
    return (
        f"📜 *TAHAP 2/2 — PAKTA INTEGRITAS KEPATUHAN UU PDP NO. 27/2022*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• *Nomor Tiket:* `{req_id}`\n"
        f"• *Pemohon:* {full_name} (NIP: `{nip}`)\n"
        f"• *Email Kedinasan:* `{email_goid}`\n"
        f"• *Dokumen Sasaran:* `{slug}` ({instansi})\n\n"
        f"Dengan mengakses pratinjau naskah fisik asli ini, saya menyatakan sanggup mematuhi ketentuan "
        f"**UU Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi (UU PDP)**:\n"
        f"1. Menggunakan pratinjau naskah semata-mata untuk kepentingan telaah kedinasan internal;\n"
        f"2. Tidak menggandakan, menyebarluaskan, atau mempublikasikan data pribadi aparatur (NIP, nomor kontak, tanda tangan basah) yang tercantum di dalam berkas asli;\n"
        f"3. Memahami bahwa layar pratinjau dilengkapi *Dynamic Watermark* atas nama & NIP saya serta tercatat dalam log audit keamanan.\n\n"
        f"✅ Balas pesan ini dengan mengetik:\n"
        f"*`SETUJU`*"
    )
