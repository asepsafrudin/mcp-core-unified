"""
delegation_manager.py — Executive Delegated Messaging & Outbound Task Dispatch
for SATRIA WhatsApp AI Co-Pilot (Ditjen Bina Pembangunan Daerah Kemendagri).

Enables Leaders / Structural Officials (e.g., Ahli Madya, Penanggung Jawab Subdit)
to delegate official operational instructions to their team members with
Human-in-the-Loop confirmation and PostgreSQL audit trails.
"""

import os
import re
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone, timedelta

import aiohttp

from integrations.whatsapp.whitelist_guard import (
    get_whitelist_user,
    normalize_phone_number,
    _load_whitelist
)

logger = logging.getLogger("delegation_manager")

# In-memory storage for pending dispatches awaiting leader confirmation
# Key: clean sender phone / identifier, Value: dispatch payload dict
_PENDING_DISPATCHES: Dict[str, Dict[str, Any]] = {}
PENDING_FILE_BACKUP = Path("/tmp/satria_pending_dispatches.json")
DEFAULT_TTL_SECONDS = 1800  # 30 menit


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


def _load_pending_from_disk():
    """Memuat cadangan state pending dari disk jika ada."""
    global _PENDING_DISPATCHES
    if PENDING_FILE_BACKUP.exists():
        try:
            with open(PENDING_FILE_BACKUP, "r", encoding="utf-8") as f:
                data = json.load(f)
                now = time.time()
                for k, v in data.items():
                    if v.get("expires_at", 0) > now:
                        _PENDING_DISPATCHES[k] = v
        except Exception as e:
            logger.warning(f"Gagal memuat pending dispatches dari disk: {e}")


def _save_pending_to_disk():
    """Menyimpan state pending ke disk untuk persistensi sementara."""
    try:
        with open(PENDING_FILE_BACKUP, "w", encoding="utf-8") as f:
            json.dump(_PENDING_DISPATCHES, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Gagal menyimpan pending dispatches ke disk: {e}")


# Muat state saat modul diimpor
_load_pending_from_disk()


def clean_phone_for_jid(phone_str: str) -> str:
    """Membersihkan nomor telepon menjadi format JID WhatsApp (e.g. 628123456789@s.whatsapp.net)."""
    digits = re.sub(r'\D', '', str(phone_str or ""))
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif not digits.startswith("62") and len(digits) >= 9:
        digits = "62" + digits
    return f"{digits}@s.whatsapp.net" if digits else ""


def format_phone_display(phone_str: str) -> str:
    """Format nomor telepon untuk tampilan manusia (+62 812-xxxx-xxxx)."""
    digits = re.sub(r'\D', '', str(phone_str or ""))
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif not digits.startswith("62") and len(digits) >= 9:
        digits = "62" + digits
    if len(digits) >= 10:
        return f"+{digits[:2]} {digits[2:5]}-{digits[5:9]}-{digits[9:]}"
    elif digits:
        return f"+{digits}"
    return ""


def lookup_recipient_in_bangda(identifier: str) -> Optional[Dict[str, Any]]:
    """
    Mencari data pegawai sasaran penerima di database Bangda:
    1. master_tim_kerja_bangda_2026 (SK Tim Kerja 2026)
    2. public.staff_details
    3. config/legal_bot_whitelist.json & member_profiles
    """
    if not identifier:
        return None

    clean_id = identifier.strip()
    digits = re.sub(r'\D', '', clean_id)
    is_phone_or_nip = len(digits) >= 8

    # 1. Cek di whitelist JSON
    wl = _load_whitelist()
    for u in wl.get("users", []):
        u_phone_digits = re.sub(r'\D', '', u.get("phone_number", ""))
        u_nip = re.sub(r'\D', '', u.get("nip", ""))
        u_name = u.get("full_name", "").lower()
        if (is_phone_or_nip and (digits == u_phone_digits or (u_nip and digits == u_nip))) or (not is_phone_or_nip and clean_id.lower() in u_name):
            return {
                "full_name": u.get("full_name"),
                "nip": u.get("nip", ""),
                "jabatan": u.get("jabatan", "Staf"),
                "unit_kerja": u.get("unit_kerja", "Ditjen Bina Pembangunan Daerah"),
                "tim_kerja": u.get("tim_kerja", ""),
                "phone_number": u.get("phone_number"),
                "phone_aliases": u.get("phone_aliases", []),
                "source": "whitelist"
            }

    # 2. Cek di database PostgreSQL
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(_get_db_url(), connect_timeout=4)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Cek master_tim_kerja_bangda_2026
        if is_phone_or_nip and len(digits) >= 12:
            # Cari by NIP
            cur.execute("""
                SELECT nama_pegawai, nip, peran, tim_kerja, sub_unit, unit_kerja, jabatan, status_asn
                FROM master_tim_kerja_bangda_2026
                WHERE REGEXP_REPLACE(COALESCE(nip, ''), '[^0-9]', '', 'g') = %s
                LIMIT 1;
            """, (digits,))
        else:
            # Cari by Nama Pegawai (ILIKE)
            search_query = f"%{clean_id}%"
            cur.execute("""
                SELECT nama_pegawai, nip, peran, tim_kerja, sub_unit, unit_kerja, jabatan, status_asn
                FROM master_tim_kerja_bangda_2026
                WHERE nama_pegawai ILIKE %s
                ORDER BY CASE WHEN peran ILIKE '%%Ketua%%' OR peran ILIKE '%%Penanggung%%' THEN 1 ELSE 2 END
                LIMIT 1;
            """, (search_query,))
        
        row = cur.fetchone()
        if row:
            cur.close()
            conn.close()
            jabatan_clean = row.get("jabatan") or ""
            if jabatan_clean.startswith(":"):
                jabatan_clean = jabatan_clean[1:].strip()
            return {
                "full_name": row["nama_pegawai"],
                "nip": row.get("nip") or "",
                "jabatan": jabatan_clean or row.get("peran") or "Anggota Tim Kerja",
                "unit_kerja": row.get("unit_kerja") or row.get("sub_unit") or "Ditjen Bina Bangda",
                "tim_kerja": row.get("tim_kerja") or "",
                "peran": row.get("peran") or "",
                "source": "master_tim_kerja_bangda_2026"
            }

        # 3. Cek staff_details
        if is_phone_or_nip and len(digits) >= 12:
            cur.execute("""
                SELECT nama, nip, pangkat, status_kepegawaian, jabatan_fungsional, penugasan_tim, unit_id
                FROM public.staff_details
                WHERE REGEXP_REPLACE(COALESCE(nip, ''), '[^0-9]', '', 'g') = %s
                LIMIT 1;
            """, (digits,))
        else:
            search_query = f"%{clean_id}%"
            cur.execute("""
                SELECT nama, nip, pangkat, status_kepegawaian, jabatan_fungsional, penugasan_tim, unit_id
                FROM public.staff_details
                WHERE nama ILIKE %s
                LIMIT 1;
            """, (search_query,))

        row_staff = cur.fetchone()
        cur.close()
        conn.close()

        if row_staff:
            return {
                "full_name": row_staff["nama"],
                "nip": row_staff.get("nip") or "",
                "jabatan": row_staff.get("jabatan_fungsional") or row_staff.get("pangkat") or "Staf Teknis",
                "unit_kerja": row_staff.get("unit_id") or "Ditjen Bina Bangda",
                "tim_kerja": row_staff.get("penugasan_tim") or "",
                "source": "staff_details"
            }

    except Exception as e:
        logger.error(f"Error query lookup recipient: {e}")

    return None


def extract_delegation_intent(text: str) -> Optional[Dict[str, Any]]:
    """
    Menganalisis apakah pesan merupakan instruksi delegasi atau pengiriman kartu kontak.
    Mengekstrak penerima (nama / nomor) dan poin instruksi dinas.
    """
    if not text:
        return None

    raw = text.strip()
    contact_card_info = None

    # 1. Cek Lampiran Kartu Kontak: [KARTU KONTAK DILAMPIRKAN]: Nama: {name}, Nomor: {phone}
    card_match = re.search(r'\[KARTU KONTAK DILAMPIRKAN\]:\s*Nama:\s*([^,\n]+)(?:,\s*Nomor:\s*([^\n\r]+))?', raw)
    if card_match:
        card_name = card_match.group(1).strip()
        card_phone = card_match.group(2).strip() if card_match.group(2) else ""
        contact_card_info = {
            "name": card_name,
            "phone": card_phone
        }
        # Hapus tag kartu kontak dari sisa teks instruksi
        remaining_text = re.sub(r'\[KARTU KONTAK DILAMPIRKAN\]:[^\n\r]+', '', raw).strip()
    else:
        remaining_text = raw

    # 2. Pola Delegasi Pesan Bahasa Alami
    # Contoh: "Tolong sampaikan ke Pak Wisnu Hartawan besok jam 09.00 rapat..."
    # Contoh: "Kirimkan arahan ke Bpk Wisnu: mohon segera siapkan materi..."
    delegation_patterns = [
        r'^(?:tolong\s+)?(?:sampaikan|kirimkan|teruskan|arahkan|instruksikan|infokan|beritahu)\s+(?:pesan|arahan|tugas|catatan)?\s*(?:ke|kepada)\s+([^\n:,]+?)[:,\s]+(?:bahwa|untuk|agar)?\s*(.+)$',
        r'^(?:tolong\s+)?(?:hubungi|kontak)\s+([^\n:,]+?)[:,\s]+(?:dan\s+)?(?:sampaikan|katakan|minta)\s*(.+)$',
    ]

    target_name_or_id = None
    instruction_content = None

    if contact_card_info:
        target_name_or_id = contact_card_info["name"]
        instruction_content = remaining_text or "Mohon segera berkoordinasi dengan pimpinan terkait tindak lanjut tugas dinas."
    else:
        # Pola A: dengan tanda baca koma atau titik dua pemisah nama dan pesan
        # contoh: "Tolong sampaikan ke Pak Wisnu Hartawan, besok jam 09.00 rapat..."
        # contoh: "Kirimkan arahan ke Pak Wisnu Hartawan: mohon disiapkan materi..."
        pat_punct = r'^(?:tolong\s+)?(?:sampaikan|kirimkan|teruskan|arahkan|instruksikan|infokan|beritahu|hubungi|kontak)\s+(?:pesan|arahan|tugas|catatan|ke|kepada)?\s*(?:ke|kepada)?\s*([^,:\n]+?)\s*[,:]\s*(.+)$'
        m_punct = re.match(pat_punct, remaining_text, re.IGNORECASE | re.DOTALL)
        if m_punct:
            target_name_or_id = m_punct.group(1).strip()
            instruction_content = m_punct.group(2).strip()
        else:
            # Pola B: dengan kata sambung bahwa / untuk / agar / supaya
            # contoh: "Sampaikan ke Pak Wisnu Hartawan bahwa besok ada rapat"
            pat_conj = r'^(?:tolong\s+)?(?:sampaikan|kirimkan|teruskan|arahkan|instruksikan|infokan|beritahu|hubungi|kontak)\s+(?:pesan|arahan|tugas|catatan|ke|kepada)?\s*(?:ke|kepada)?\s*(.+?)\s+(?:bahwa|untuk|agar|supaya)\s+(.+)$'
            m_conj = re.match(pat_conj, remaining_text, re.IGNORECASE | re.DOTALL)
            if m_conj:
                target_name_or_id = m_conj.group(1).strip()
                instruction_content = m_conj.group(2).strip()
            else:
                # Pola C: fallback kata transisi waktu/instruksi
                pat_fallback = r'^(?:tolong\s+)?(?:sampaikan|kirimkan|teruskan|arahkan|instruksikan|infokan|beritahu)\s+(?:pesan|arahan|tugas|catatan)?\s*(?:ke|kepada)\s+([A-Za-z\s.]+?)\s+(besok|hari ini|nanti|segera|mohon|agar|tolong|jadwal|mengenai|terkait)\s*(.+)$'
                m_fb = re.match(pat_fallback, remaining_text, re.IGNORECASE | re.DOTALL)
                if m_fb:
                    target_name_or_id = m_fb.group(1).strip()
                    instruction_content = f"{m_fb.group(2)} {m_fb.group(3)}".strip()

    if not target_name_or_id:
        return None

    # Bersihkan prefix ke/kepada dan sapaan dari nama target (Pak, Bpk, Ibu, Mas, Mbak)
    cleaned_target_name = re.sub(r'^(?:ke|kepada)\s+', '', target_name_or_id, flags=re.IGNORECASE).strip()
    cleaned_target_name = re.sub(r'^(?:bpk\.?|bapak|pak|ibu|bu\.?|mas|mbak|sdr\.?|saudara)\s+', '', cleaned_target_name, flags=re.IGNORECASE).strip()

    # Bersihkan nomor telepon dari nama jika ada di dalam kurung, misal: "Wisnu (0812345678)"
    phone_in_paren = re.search(r'\(([\d\+\s\-]+)\)', cleaned_target_name)
    extracted_phone = ""
    if phone_in_paren:
        extracted_phone = phone_in_paren.group(1).strip()
        cleaned_target_name = re.sub(r'\s*\([\d\+\s\-]+\)', '', cleaned_target_name).strip()

    phone_to_use = ""
    if contact_card_info and contact_card_info.get("phone"):
        phone_to_use = contact_card_info["phone"]
    elif extracted_phone:
        phone_to_use = extracted_phone

    return {
        "raw_target": target_name_or_id,
        "target_name": cleaned_target_name,
        "phone": phone_to_use,
        "instruction": instruction_content,
        "is_contact_card": contact_card_info is not None
    }


def format_delegated_message_draft(
    sender_user: Dict[str, Any],
    recipient_data: Dict[str, Any],
    instruction_text: str
) -> str:
    """
    Menyusun draf pesan resmi bernada kedinasan khas Ditjen Bina Bangda Kemendagri.
    Secara dinamis menyesuaikan nama, jabatan, unit kerja, dan tim kerja pimpinan pengirim.
    """
    sender_name = sender_user.get("full_name") or "Pimpinan Ditjen Bangda"
    sender_jabatan = sender_user.get("jabatan") or "Pejabat Ditjen Bina Bangda"
    sender_unit = sender_user.get("unit_kerja") or "Ditjen Bina Pembangunan Daerah"
    sender_tim = sender_user.get("tim_kerja") or ""

    # Bersihkan format baris unit/tim pimpinan
    if sender_unit and sender_tim and sender_unit.lower() in sender_tim.lower():
        unit_tim_line = sender_tim
    elif sender_tim:
        unit_tim_line = f"{sender_unit} — {sender_tim}"
    else:
        unit_tim_line = sender_unit

    recipient_name = recipient_data.get("full_name") or "Bapak/Ibu"
    recipient_jabatan = recipient_data.get("jabatan") or "Staf/Pegawai"
    recipient_tim = recipient_data.get("tim_kerja") or recipient_data.get("unit_kerja") or "Ditjen Bina Bangda"

    # Deteksi sapaan gender pengirim (Ibu vs Bpk.)
    sender_lower = sender_name.lower()
    is_female = any(w in sender_lower for w in ["lady", "diana", "roza", "ibu", "dra", "siti", "tri", "ani", "nur", "dewi", "retno", "sri"])
    sender_honorific = "Ibu" if is_female else "Bpk."

    now_wib = datetime.now(timezone(timedelta(hours=7))).strftime("%d/%m/%Y, %H:%M WIB")

    draft = (
        f"🏛️ *ARAHAN KEDINASAN KEMENDAGRI — DITJEN BINA BANGDA*\n"
        f"_{unit_tim_line}_\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Kepada Yth.\n"
        f"*{recipient_name}*\n"
        f"_{recipient_jabatan} — {recipient_tim}_\n\n"
        f"Dengan hormat,\n"
        f"Menindaklanjuti arahan kedinasan dari *{sender_name}* ({sender_jabatan}), "
        f"melalui Asisten Operasional Eksekutif SATRIA disampaikan instruksi sebagai berikut:\n\n"
        f"📌 *POIN ARAHAN / INSTRUKSI DINAS:*\n"
        f"\"{instruction_text}\"\n\n"
        f"Mohon arahan di atas dapat dipedomani dan ditindaklanjuti dengan sebaik-baiknya. "
        f"Apabila ada hal teknis yang memerlukan koordinasi, silakan melaporkan langsung kepada beliau.\n\n"
        f"Terima kasih atas dedikasi dan kerja sama Saudara.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 *Waktu Disampaikan:* {now_wib}\n"
        f"🤖 _Pesan resmi ini diteruskan secara otomatis oleh SATRIA (Executive AI Co-Pilot Ditjen Bina Bangda) "
        f"atas mandat {sender_honorific} {sender_name.rstrip('.')}._"
    )
    return draft


def format_leader_preview(
    recipient_data: Dict[str, Any],
    draft_text: str,
    target_phone: str
) -> str:
    """
    Menampilkan pratinjau draf lengkap kepada pimpinan disertai opsi konfirmasi Human-in-the-Loop.
    """
    r_name = recipient_data.get("full_name") or "Penerima"
    r_jabatan = recipient_data.get("jabatan") or "Pegawai Ditjen Bangda"
    r_unit = recipient_data.get("unit_kerja") or "Dit. SUPD IV"
    r_tim = recipient_data.get("tim_kerja") or r_unit
    r_nip = recipient_data.get("nip") or "-"

    phone_disp = format_phone_display(target_phone) if target_phone else "⚠️ Belum terdaftar"

    preview = (
        f"📋 *PRATINJAU DRAF INSTRUKSI KEDINASAN*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Penerima Sasaran:* {r_name}\n"
        f"🆔 *NIP:* {r_nip}\n"
        f"💼 *Jabatan:* {r_jabatan}\n"
        f"🏢 *Tim Kerja / Unit:* {r_tim} ({r_unit})\n"
        f"📱 *Nomor Tujuan WA:* {phone_disp}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 *Naskah Arahan yang Akan Dikirim:*\n"
        f"```\n{draft_text}\n```\n\n"
        f"⚡ *PILIHAN TINDAKAN PIMPINAN:*\n"
        f"• Ketik *KIRIM* 👉 untuk menyetujui & langsung mengirimkan pesan ke WhatsApp beliau.\n"
        f"• Ketik *BATAL* 👉 untuk membatalkan pengiriman draf ini.\n\n"
        f"⏳ _Draf ini tersimpan aktif dan aman selama 30 menit._"
    )
    return preview


def store_pending_dispatch(sender_key: str, payload: Dict[str, Any]):
    """Menyimpan state draf pending ke memori dan disk."""
    clean_key = normalize_phone_number(sender_key)
    payload["created_at"] = time.time()
    payload["expires_at"] = time.time() + DEFAULT_TTL_SECONDS
    _PENDING_DISPATCHES[clean_key] = payload
    _save_pending_to_disk()
    logger.info(f"Stored pending dispatch for {clean_key} targeting {payload.get('recipient_name')}")


def get_pending_dispatch(sender_key: str) -> Optional[Dict[str, Any]]:
    """Mengambil state draf pending pimpinan jika belum kadaluarsa."""
    clean_key = normalize_phone_number(sender_key)
    item = _PENDING_DISPATCHES.get(clean_key)
    if not item:
        return None
    if time.time() > item.get("expires_at", 0):
        clear_pending_dispatch(clean_key)
        return None
    return item


def clear_pending_dispatch(sender_key: str):
    """Menghapus draf pending setelah dieksekusi atau dibatalkan."""
    clean_key = normalize_phone_number(sender_key)
    if clean_key in _PENDING_DISPATCHES:
        del _PENDING_DISPATCHES[clean_key]
        _save_pending_to_disk()
        logger.info(f"Cleared pending dispatch for {clean_key}")


def is_confirmation_trigger(text: str) -> Tuple[bool, str]:
    """
    Memeriksa apakah pesan teks merupakan kata kunci konfirmasi.
    Returns: (is_matched, action) where action is 'CONFIRM', 'CANCEL', or 'NONE'
    """
    if not text:
        return False, "NONE"
    t = text.strip().lower()
    t = re.sub(r'[^a-zA-Z0-9\s]', '', t).strip()

    confirm_keywords = {
        "kirim", "kirimkan", "ya kirim", "ya kirimkan", "ok kirim",
        "oke kirim", "send", "yes", "setuju", "lanjutkan", "teruskan"
    }
    cancel_keywords = {
        "batal", "batalkan", "cancel", "tidak jadi", "hapus draf", "jangan"
    }

    if t in confirm_keywords:
        return True, "CONFIRM"
    if t in cancel_keywords:
        return True, "CANCEL"

    return False, "NONE"


async def execute_dispatch(
    sender_user: Dict[str, Any],
    pending_payload: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Mengeksekusi pengiriman pesan arahan kedinasan secara otonom
    melalui Baileys WhatsApp Webhook (POST http://127.0.0.1:3001/webhook/whatsapp),
    dan mencatat audit trail ke PostgreSQL.
    """
    recipient_jid = pending_payload.get("recipient_jid")
    draft_text = pending_payload.get("draft_text")
    recipient_name = pending_payload.get("recipient_name")
    recipient_phone = pending_payload.get("recipient_phone")
    sender_phone = sender_user.get("phone_number") or sender_user.get("user_id")

    if not recipient_jid or not draft_text:
        return False, "Data sasaran pengiriman atau naskah draf tidak lengkap."

    webhook_url = os.getenv("WHATSAPP_WEBHOOK_URL", "http://127.0.0.1:3001/webhook/whatsapp")
    webhook_secret = os.getenv("WEBHOOK_SECRET") or os.getenv("MCP_WEBHOOK_SECRET") or "mcp_unified_webhook_2026"
    request_id = f"delegated-{int(time.time())}-{re.sub(r'[^0-9]', '', str(sender_phone))[-4:]}"

    post_payload = {
        "user_id": recipient_jid,
        "response": draft_text,
        "request_id": request_id,
        "sender_id": clean_phone_for_jid(sender_phone)
    }

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": webhook_secret
    }

    dispatch_success = False
    error_detail = ""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=post_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    dispatch_success = True
                    logger.info(f"Autonomous delegation dispatched to {recipient_jid} (req_id={request_id})")
                else:
                    err_txt = await resp.text()
                    error_detail = f"HTTP {resp.status}: {err_txt}"
                    logger.error(f"Failed to dispatch delegation to {recipient_jid}: {error_detail}")
    except Exception as e:
        error_detail = str(e)
        logger.error(f"Exception during autonomous dispatch: {e}")

    # Catat Audit Trail ke PostgreSQL unified_messages (non-blocking)
    try:
        import psycopg2
        conn = psycopg2.connect(_get_db_url(), connect_timeout=4)
        cur = conn.cursor()
        # Tentukan namespace audit berdasar unit kerja pimpinan pengirim
        u_unit_str = str(sender_user.get("unit_kerja") or "bangda").lower()
        if "supd_iv" in u_unit_str or "supd iv" in u_unit_str:
            audit_namespace = "supd_iv"
        elif "supd_ii" in u_unit_str or "supd ii" in u_unit_str:
            audit_namespace = "supd_ii"
        elif "supd_i" in u_unit_str or "supd i" in u_unit_str:
            audit_namespace = "supd_i"
        elif "supd_iii" in u_unit_str or "supd iii" in u_unit_str:
            audit_namespace = "supd_iii"
        elif "peipd" in u_unit_str:
            audit_namespace = "peipd"
        elif "kpm" in u_unit_str:
            audit_namespace = "kpm"
        elif "hukum" in u_unit_str or "sekretariat" in u_unit_str or "puu" in u_unit_str:
            audit_namespace = "hukum_puu"
        else:
            audit_namespace = "bangda_eksekutif"

        cur.execute("""
            INSERT INTO public.unified_messages 
            (platform, external_id, namespace, sender, recipient, content, metadata, timestamp, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW());
        """, (
            "whatsapp",
            request_id,
            audit_namespace,
            f"{sender_user.get('full_name')} ({sender_phone})",
            f"{recipient_name} ({recipient_phone})",
            draft_text,
            json.dumps({
                "action": "EXECUTIVE_DELEGATION",
                "status": "SUCCESS" if dispatch_success else "FAILED",
                "recipient_jid": recipient_jid,
                "recipient_jabatan": pending_payload.get("recipient_jabatan"),
                "recipient_tim": pending_payload.get("recipient_tim"),
                "instruction": pending_payload.get("instruction_text"),
                "request_id": request_id,
                "error": error_detail if not dispatch_success else None
            }, ensure_ascii=False)
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as db_err:
        logger.warning(f"Audit log write failed (non-fatal): {db_err}")

    now_wib = datetime.now(timezone(timedelta(hours=7))).strftime("%d/%m/%Y, %H:%M WIB")

    sender_name = sender_user.get("full_name") or "Pimpinan"
    sender_lower = sender_name.lower()
    is_female = any(w in sender_lower for w in ["lady", "diana", "roza", "ibu", "dra", "siti", "tri", "ani", "nur", "dewi", "retno", "sri"])
    sender_honorific = "Ibu" if is_female else "Bpk."

    if dispatch_success:
        report = (
            f"✅ *ARAHAN KEDINASAN BERHASIL DISAMPAIKAN*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Penerima:* {recipient_name}\n"
            f"📱 *Nomor Tujuan:* {format_phone_display(recipient_phone)}\n"
            f"🕒 *Waktu Pengiriman:* {now_wib}\n"
            f"📊 *Status:* Terkirim ke antrean WhatsApp (Dispatch OK)\n"
            f"🔖 *ID Transaksi:* `{request_id}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"SATRIA telah meneruskan mandat {sender_honorific} *{sender_name.rstrip('.')}* secara resmi. "
            f"Seluruh riwayat transmisi telah dicatat pada sistem audit operasional Ditjen Bina Bangda."
        )
        return True, report
    else:
        fail_report = (
            f"❌ *PENGIRIMAN GAGAL TEREKSEKUSI*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Terjadi kendala teknis saat menghubungi gerbang pesan WhatsApp: {error_detail}.\n"
            f"Draf instruksi tetap tersimpan. Bapak dapat mencoba mengetik *KIRIM* kembali sesaat lagi."
        )
        return False, fail_report
