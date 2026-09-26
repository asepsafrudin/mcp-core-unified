"""
onboarding_manager.py — Proactive Member Onboarding & Self-Service Whitelist Provisioning
for SATRIA WhatsApp AI Co-Pilot (Ditjen Bina Pembangunan Daerah Kemendagri).

Features:
1. Strict 100% NIP validation against official Ditjen Bangda employee database (public.staff_details).
2. Name similarity verification (fuzzy/token matching, title stripping, spaced-letter normalization).
3. Autonomous provisioning to config/legal_bot_whitelist.json and PostgreSQL member_profiles.
4. Intelligent role and permission assignment based on employee unit/function.
5. In-flight session query stashing to answer original questions immediately upon activation.
"""

import os
import re
import difflib
import logging
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

from integrations.whatsapp.whitelist_guard import (
    get_whitelist_user,
    save_whitelist_user,
    normalize_phone_number,
    _resolve_lid_to_phone,
    KNOWN_LIDS
)

logger = logging.getLogger("onboarding_manager")

# In-memory storage for pending queries during onboarding
_PENDING_QUERIES: Dict[str, Dict[str, Any]] = {}

COMMON_TITLES = {
    "dr", "drs", "dra", "prof", "ir",
    "s.ip", "sip", "m.ap", "map",
    "s.h", "sh", "m.h", "mh",
    "s.e", "se", "m.e", "me",
    "s.kom", "skom", "m.kom", "mkom",
    "s.si", "ssi", "m.si", "msi",
    "s.t", "st", "m.t", "mt",
    "s.sos", "ssos", "m.sos", "msos",
    "s.s", "ss", "m.hum", "mhum",
    "s.st.pi", "cpsp",
    "a.md.kom", "a.md", "amd"
}


def _get_db_url() -> str:
    """Mengembalikan URL database PostgreSQL dengan sanitasi host Linux."""
    url = os.getenv("DATABASE_URL")
    if not url:
        pg_user = os.getenv("POSTGRES_USER", "mcp_user")
        pg_pass = os.getenv("POSTGRES_PASSWORD", "")
        pg_host = os.getenv("POSTGRES_HOST", "127.0.0.1")
        pg_port = os.getenv("POSTGRES_PORT", "5433")
        pg_db   = os.getenv("POSTGRES_DB", "mcp_knowledge")
        url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    return url.replace("@localhost:", "@127.0.0.1:")


def clean_nip_digits(nip_str: str) -> str:
    """Membersihkan NIP menjadi deretan angka murni."""
    if not nip_str:
        return ""
    return re.sub(r'\D', '', str(nip_str))


def clean_name_tokens(name_str: str) -> List[str]:
    """
    Membersihkan nama dari gelar akademik, tanda baca, dan menormalisasi spasi
    termasuk nama dengan huruf terpisah seperti 'A M A R Y A D I'.
    """
    if not name_str:
        return []
    
    text = name_str.lower().strip()
    
    # Deteksi huruf terpisah seperti "a m a r y a d i"
    tokens = text.split()
    if len(tokens) >= 3 and all(len(t) == 1 for t in tokens):
        collapsed = "".join(tokens)
        text = collapsed

    # Hapus tanda baca selain spasi
    text = re.sub(r'[,.\-_/()\'\"]', ' ', text)
    raw_tokens = text.split()
    
    cleaned = []
    for t in raw_tokens:
        clean_t = t.strip()
        if clean_t and clean_t not in COMMON_TITLES and len(clean_t) > 1:
            cleaned.append(clean_t)
    return cleaned


def check_name_similarity(input_name: str, db_name: str) -> Tuple[bool, float, str]:
    """
    Memeriksa kemiripan nama antara input pengguna/pushName dengan nama resmi di database.
    Aturan: Nama tidak harus full, asal ada kemiripan teks/token dasar yang kuat.
    """
    tokens_input = clean_name_tokens(input_name)
    tokens_db = clean_name_tokens(db_name)
    
    if not tokens_input or not tokens_db:
        return False, 0.0, "Nama tidak dapat diurai"
    
    str_input = " ".join(tokens_input)
    str_db = " ".join(tokens_db)

    # 1. Exact full token string match
    if str_input == str_db:
        return True, 1.0, "Kecocokan nama sempurna"

    # 2. Cek apakah ada token nama utama (panjang >= 3) yang cocok persis
    for ti in tokens_input:
        if len(ti) >= 3 and ti in tokens_db:
            return True, 0.9, f"Kecocokan kata kunci nama: '{ti}'"

    # 3. Substring containment
    for ti in tokens_input:
        if len(ti) >= 4:
            for td in tokens_db:
                if ti in td or td in ti:
                    return True, 0.85, f"Kecocokan parsial nama: '{ti}' ~ '{td}'"

    # 4. Levenshtein ratio / SequenceMatcher
    ratio = difflib.SequenceMatcher(None, str_input, str_db).ratio()
    if ratio >= 0.55:
        return True, ratio, f"Skor kemiripan teks: {ratio:.2f}"

    return False, ratio, f"Nama tidak menunjukkan kemiripan yang cukup ({ratio:.2f})"


def lookup_employee_by_nip(nip_str: str) -> Optional[Dict[str, Any]]:
    """
    Pencarian data pegawai resmi Ditjen Bina Bangda berdasarkan 18 digit NIP.
    Memeriksa tabel public.staff_details (primer) dan tabel-tabel master pendukung.
    """
    clean_nip = clean_nip_digits(nip_str)
    if len(clean_nip) < 9:
        return None

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url, connect_timeout=4)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Cek di tabel staff_details
        cur.execute("""
            SELECT id, nama, nip, pangkat, status_kepegawaian, jabatan_fungsional, penugasan_tim, unit_id, grade_pppk
            FROM public.staff_details
            WHERE REGEXP_REPLACE(COALESCE(nip, ''), '[^0-9]', '', 'g') = %s
            ORDER BY id ASC LIMIT 1;
        """, (clean_nip,))
        row = cur.fetchone()
        if row:
            cur.close()
            conn.close()
            unit = row.get("unit_id") or "Ditjen Bina Pembangunan Daerah"
            tim = row.get("penugasan_tim") or unit
            return {
                "nama": row["nama"],
                "nip": clean_nip,
                "jabatan": row.get("jabatan_fungsional") or "Staf Teknis",
                "unit_kerja": unit,
                "tim_kerja": tim,
                "status_kepegawaian": row.get("status_kepegawaian") or "PNS",
                "pangkat": row.get("pangkat") or row.get("grade_pppk") or "",
                "source_table": "staff_details"
            }

        # 2. Cek di master_tim_kerja_bangda_2026
        cur.execute("""
            SELECT id, nama_pegawai, nip, jabatan, unit_kerja, tim_kerja
            FROM public.master_tim_kerja_bangda_2026
            WHERE REGEXP_REPLACE(COALESCE(nip, ''), '[^0-9]', '', 'g') = %s
            ORDER BY id ASC LIMIT 1;
        """, (clean_nip,))
        row2 = cur.fetchone()
        if row2:
            cur.close()
            conn.close()
            return {
                "nama": row2["nama_pegawai"],
                "nip": clean_nip,
                "jabatan": row2.get("jabatan") or "Staf Teknis",
                "unit_kerja": row2.get("unit_kerja") or "Ditjen Bina Pembangunan Daerah",
                "tim_kerja": row2.get("tim_kerja") or row2.get("unit_kerja") or "",
                "status_kepegawaian": "PNS",
                "pangkat": "",
                "source_table": "master_tim_kerja_bangda_2026"
            }

        # 3. Cek di master_puu_pegawai
        cur.execute("""
            SELECT id, nama_lengkap, nip, pangkat_gol, jabatan_fungsional, status_kepegawaian
            FROM public.master_puu_pegawai
            WHERE REGEXP_REPLACE(COALESCE(nip, ''), '[^0-9]', '', 'g') = %s
            ORDER BY id ASC LIMIT 1;
        """, (clean_nip,))
        row3 = cur.fetchone()
        cur.close()
        conn.close()
        if row3:
            return {
                "nama": row3["nama_lengkap"],
                "nip": clean_nip,
                "jabatan": row3.get("jabatan_fungsional") or "Analis Hukum",
                "unit_kerja": "Sekretariat Ditjen Bina Bangda",
                "tim_kerja": "Tim PUU & Tata Laksana",
                "status_kepegawaian": row3.get("status_kepegawaian") or "PNS",
                "pangkat": row3.get("pangkat_gol") or "",
                "source_table": "master_puu_pegawai"
            }

    except Exception as e:
        logger.warning(f"Error lookup employee by NIP {clean_nip}: {e}")

    return None


def find_candidate_by_name(name_str: str) -> Optional[Dict[str, Any]]:
    """
    Mencari calon pegawai berdasarkan nama (misal dari WhatsApp PushName).
    Mengembalikan data pegawai jika ditemukan kecocokan tunggal yang meyakinkan.
    """
    tokens = clean_name_tokens(name_str)
    if not tokens:
        return None
    
    # Gunakan token nama terpanjang untuk kueri
    longest_token = max(tokens, key=len)
    if len(longest_token) < 4:
        return None

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url, connect_timeout=4)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT id, nama, nip, pangkat, status_kepegawaian, jabatan_fungsional, penugasan_tim, unit_id
            FROM public.staff_details
            WHERE nama ILIKE %s
            ORDER BY id ASC LIMIT 5;
        """, (f"%{longest_token}%",))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if len(rows) == 1:
            r = rows[0]
            return {
                "nama": r["nama"],
                "nip": r.get("nip") or "",
                "jabatan": r.get("jabatan_fungsional") or "Staf Teknis",
                "unit_kerja": r.get("unit_id") or "Ditjen Bina Pembangunan Daerah",
                "penugasan_tim": r.get("penugasan_tim") or ""
            }
        elif len(rows) > 1:
            best_r = None
            best_score = 0.0
            for r in rows:
                is_match, score, _ = check_name_similarity(name_str, r["nama"])
                if is_match and score > best_score:
                    best_score = score
                    best_r = r
            if best_r and best_score >= 0.7:
                return {
                    "nama": best_r["nama"],
                    "nip": best_r.get("nip") or "",
                    "jabatan": best_r.get("jabatan_fungsional") or "Staf Teknis",
                    "unit_kerja": best_r.get("unit_id") or "Ditjen Bina Pembangunan Daerah",
                    "penugasan_tim": best_r.get("penugasan_tim") or ""
                }
    except Exception as e:
        logger.warning(f"Error candidate lookup by name {name_str}: {e}")

    return None


def extract_nip_from_text(text: str) -> Optional[str]:
    """Mendeteksi dan mengekstrak NIP 18 digit dari pesan teks dalam berbagai format."""
    if not text:
        return None
    
    # 1. Format eksplisit 18 digit kontinu (dimulai 19xx atau 20xx)
    match = re.search(r'\b(19\d{16}|20\d{16})\b', text)
    if match:
        return match.group(1)

    # 2. Format NIP standar ber-spasi / titik: e.g. 19771112 200614 1 001
    match_spaced = re.search(r'\b(19\d{6}|20\d{6})[\s\.\-]?(\d{6})[\s\.\-]?(\d{1})[\s\.\-]?(\d{3})\b', text)
    if match_spaced:
        return "".join(match_spaced.groups())

    # 3. Format 'DAFTAR#NIP#...'
    if "#" in text:
        parts = [p.strip() for p in text.split("#")]
        for p in parts:
            clean = clean_nip_digits(p)
            if len(clean) == 18 and (clean.startswith("19") or clean.startswith("20")):
                return clean

    # 4. Angka murni 18 digit di seluruh teks jika teks pendek
    all_digits = clean_nip_digits(text)
    if len(all_digits) == 18 and (all_digits.startswith("19") or all_digits.startswith("20")):
        return all_digits

    return None


def determine_user_role(employee: Dict[str, Any]) -> str:
    """Menentukan peran otorisasi SATRIA berdasarkan unit kerja dan jabatan pegawai."""
    unit = str(employee.get("unit_kerja", "")).upper()
    jabatan = str(employee.get("jabatan", "")).upper()
    tim = str(employee.get("tim_kerja", "")).upper()
    combined = f"{unit} {jabatan} {tim}"

    if any(k in combined for k in ["HUKUM", "PUU", "PERANCANG", "ANALIS HUKUM"]):
        return "LEGAL_ANALYST"
    if any(k in combined for k in ["DIREKTUR", "DIRJEN", "SESDITJEN", "KASUBBAG"]):
        return "LEGAL_REVIEWER_LEAD"
    if any(k in combined for k in ["SUPD", "PEIPD", "KORWIL", "SUBDIT"]):
        return "REGIONAL_SUPPORT"
    if any(k in combined for k in ["PERENCANAAN", "PRANATA KOMPUTER", "SISTEM"]):
        return "PLANNING_SUPPORT"
    return "OFFICE_STAFF"


def stash_pending_query(phone_or_lid: str, query: str):
    """Menyimpan pertanyaan awal pengguna baru agar dapat dijawab setelah verifikasi."""
    clean_key = phone_or_lid.split("@")[0].strip()
    import time
    _PENDING_QUERIES[clean_key] = {
        "query": query,
        "timestamp": time.time()
    }


def pop_pending_query(phone_or_lid: str) -> Optional[str]:
    """Mengambil dan menghapus pertanyaan awal yang tertunda."""
    clean_key = phone_or_lid.split("@")[0].strip()
    data = _PENDING_QUERIES.pop(clean_key, None)
    if data:
        import time
        if time.time() - data.get("timestamp", 0) < 86400:
            return data.get("query")
    return None


def verify_and_provision(
    sender_phone: str,
    sender_name: Optional[str],
    message_text: str
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Memvalidasi NIP dan kemiripan nama pengguna, lalu memutakhirkan whitelist secara mandiri.
    Syarat:
    1. NIP 100% valid (terdaftar di database kepegawaian Bangda).
    2. Nama pengguna (dari input teks atau PushName WhatsApp) memiliki kemiripan dengan nama di DB.
    """
    nip = extract_nip_from_text(message_text)
    if not nip:
        return False, "⚠️ Format NIP tidak valid. NIP harus terdiri dari 18 digit angka.", None

    employee = lookup_employee_by_nip(nip)
    if not employee:
        return (
            False,
            f"❌ NIP *{nip}* tidak ditemukan dalam Pangkalan Data Pegawai Ditjen Bina Bangda Kemendagri.\n\n"
            "Mohon periksa kembali nomor NIP Anda atau hubungi Bagian Kepegawaian/Admin Sistem.",
            None
        )

    # Verifikasi kemiripan nama
    candidate_names = []
    if sender_name:
        candidate_names.append(sender_name)
    
    # Cek apakah user menuliskan nama di teks (misal: DAFTAR#NIP#NAMA...)
    if "#" in message_text:
        parts = [p.strip() for p in message_text.split("#")]
        for p in parts:
            if p and not p.isdigit() and len(p) >= 3 and p.lower() not in ["daftar", "registrasi", "satria"]:
                candidate_names.append(p)
    
    name_match = re.search(r'(?:nama|nama\s+lengkap)\s*[:=]\s*([a-zA-Z\s.,]+)', message_text, re.IGNORECASE)
    if name_match:
        candidate_names.append(name_match.group(1).strip())

    db_name = employee["nama"]
    name_matched = False
    best_reason = ""
    
    for cn in candidate_names:
        is_sim, score, reason = check_name_similarity(cn, db_name)
        if is_sim:
            name_matched = True
            best_reason = reason
            break

    # Jika nama sama sekali tidak cocok, tolak demi keamanan data
    if not name_matched:
        return (
            False,
            f"⚠️ *VERIFIKASI NAMA TIDAK COCOK*\n\n"
            f"NIP *{nip}* valid atas nama pegawai: *{db_name}*.\n"
            f"Namun nama pada profil/pesan Anda (*{sender_name or 'tidak terdeteksi'}*) tidak menunjukkan kemiripan dengan nama resmi di database.\n\n"
            "📌 *Langkah Perbaikan:*\n"
            f"Ketik: `DAFTAR#{nip}#{db_name}#{employee['unit_kerja']}` untuk konfirmasi identitas yang sah.",
            None
        )

    # Identifikasi LID dan Nomor Telepon
    raw_id = str(sender_phone).strip()
    is_lid = "@lid" in raw_id or (raw_id.isdigit() and len(raw_id) >= 14 and not raw_id.startswith(("62", "08")))
    clean_lid = raw_id.split("@")[0].strip() if is_lid else None

    linked_phone = None
    if is_lid:
        linked_phone = _resolve_lid_to_phone(clean_lid)
    else:
        linked_phone = normalize_phone_number(raw_id)

    assigned_role = determine_user_role(employee)

    # Eksekusi penambahan ke Whitelist via whitelist_guard
    success, action_desc, user_data = save_whitelist_user(
        identifier=sender_phone,
        full_name=employee["nama"],
        jabatan=employee["jabatan"],
        unit_kerja=employee["unit_kerja"],
        role=assigned_role,
        nip=employee["nip"],
        pangkat_golongan=employee.get("pangkat"),
        tim_kerja=employee.get("tim_kerja"),
        linked_phone=linked_phone
    )

    if not success:
        return False, f"❌ Gagal menyimpan data whitelist: {action_desc}", None

    success_msg = (
        "✅ *VERIFIKASI BERHASIL & WHITELIST DIAKTIFKAN*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Selamat datang di *SATRIA (Asisten Ahli Madya Bangda)*, Bapak/Ibu *{employee['nama']}*!\n\n"
        "Data identitas Anda telah terverifikasi secara sah dengan database kepegawaian Ditjen Bina Pembangunan Daerah:\n"
        f"• *NIP:* {employee['nip']}\n"
        f"• *Jabatan:* {employee['jabatan']}\n"
        f"• *Unit Kerja:* {employee['unit_kerja']}\n"
        f"• *Penugasan:* {employee['tim_kerja']}\n"
        f"• *Hak Akses:* {assigned_role} (Aktif)\n\n"
        "Nomor WhatsApp Anda kini telah resmi terdaftar dalam Whitelist SATRIA. Anda dapat langsung menanyakan regulasi daerah, urusan konkuren, disposisi persuratan, atau telaah dokumen PUU."
    )

    return True, success_msg, employee


def format_proactive_invitation(
    sender_phone: str,
    sender_name: Optional[str]
) -> str:
    """
    Menyusun sapaan proaktif edukatif pada interaksi pertama untuk pengguna belum terdaftar.
    Jika PushName memiliki calon kecocokan pegawai di database, sapa secara personal.
    """
    candidate = find_candidate_by_name(sender_name) if sender_name else None
    
    if candidate:
        return (
            "👋 *SELAMAT DATANG DI SATRIA — DITJEN BINA BANGDA*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Salam hormat Bapak/Ibu *{candidate['nama']}*,\n\n"
            "Sistem AI SATRIA mendeteksi profil Anda terdaftar di database kepegawaian Ditjen Bina Pembangunan Daerah sebagai:\n"
            f"• *Jabatan:* {candidate['jabatan']}\n"
            f"• *Unit Kerja:* {candidate['unit_kerja']}\n\n"
            "Namun, nomor WhatsApp ini saat ini belum terhubung aktif dalam *Whitelist Resmi SATRIA*.\n\n"
            "🔐 *Aktivasi Mandiri Akses SATRIA:*\n"
            "Untuk mengaktifkan akses layanan kedinasan Anda dan mendapatkan telaah regulasi resmi secara instan, "
            "silakan konfirmasi **NIP 18 digit** Anda (cukup balas pesan ini dengan mengetikkan NIP Anda)."
        )
    
    return (
        "👋 *SELAMAT DATANG DI SATRIA — DITJEN BINA BANGDA*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Layanan Asisten AI Ahli Madya *SATRIA (Sistem Analisis Tata Kelola, Regulasi, & Insan Aparatur)* "
        "Ditjen Bina Pembangunan Daerah Kemendagri dikhususkan bagi jajaran pejabat dan staf Ditjen Bangda.\n\n"
        "Nomor WhatsApp Anda belum terdaftar dalam *Whitelist Resmi SATRIA*.\n\n"
        "📋 *Pendaftaran & Verifikasi Mandiri:*\n"
        "Jika Anda adalah pegawai/staf di lingkungan Ditjen Bina Pembangunan Daerah, silakan aktifkan akun Anda dengan membalas pesan ini:\n\n"
        "Ketik:\n"
        "*DAFTAR#NIP#NAMA LENGKAP#UNIT KERJA*\n"
        "_Contoh:_ `DAFTAR#197711122006141001#AMARYADI#SUPD IV`\n\n"
        "_(Atau cukup kirimkan **NIP 18 digit** Anda untuk pencocokan otomatis dengan Pangkalan Data Pegawai Ditjen Bangda)._"
    )
