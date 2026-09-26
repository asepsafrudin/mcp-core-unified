"""
whitelist_guard.py — Strict RBAC Whitelist Guard for Legal Agent WhatsApp Bot.
Enforces user isolation, administrative CRUD operations, and personalized structural greetings
based on config/legal_bot_whitelist.json and PostgreSQL member_profiles sync.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger("whitelist_guard")

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "config" / "legal_bot_whitelist.json"
AUTH_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "services" / "whatsapp-bot-ai" / "auth_info"

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

_WHITELIST_CACHE: Optional[Dict[str, Any]] = None
_WHITELIST_CACHE_MTIME: float = 0.0

KNOWN_LIDS: Dict[str, str] = {
    "191022999048285": "+6285717223889", # Asep Safrudin (Super Admin)
    "117278511214666": "+6281284631983", # Lady Diana Handayani
    "153309008658561": "+6281343733332", # Faisal Baharuddin
    "233191055032324": "+6281584354128", # Sukma Adi Nugroho
    "243082817712167": "+6281574191868", # Romi Nugraha
    "66477688373373": "+6281318605121",  # Yonatan Sisco
    "68050166489298": "+6282138039791",  # Dennis Rahmat Himawan, S.H.
    "210578085830727": "+6287871393744"  # Ahmad Haidir Al-Fadlil, S.E.Sy (ULA Bangda)
}

DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "SUPER_ADMIN": [
        "admin_manage",
        "full_audit",
        "safe_patch",
        "doctrine_evaluation",
        "policy_as_code",
        "view_precedents",
        "dispatch_alerts",
        "correspondence_tracking",
        "disposisi_check",
        "spm_verification",
        "nd_laporan_generate",
        "system_health",
        "general_consultation"
    ],
    "LEGAL_REVIEWER_LEAD": [
        "full_audit",
        "safe_patch",
        "doctrine_evaluation",
        "view_precedents",
        "receive_alerts",
        "dispatch_alerts",
        "nd_laporan_generate",
        "correspondence_tracking",
        "general_consultation"
    ],
    "LEGAL_DRAFTER_LEAD": [
        "full_audit",
        "safe_patch",
        "statutory_verification",
        "doctrine_evaluation",
        "view_precedents",
        "receive_alerts",
        "nd_laporan_generate",
        "correspondence_tracking",
        "general_consultation"
    ],
    "LEGAL_ANALYST": [
        "full_audit",
        "statutory_verification",
        "doctrine_evaluation",
        "view_precedents",
        "receive_alerts",
        "nd_laporan_generate",
        "correspondence_tracking",
        "general_consultation"
    ],
    "REGIONAL_SUPPORT": [
        "full_audit",
        "view_precedents",
        "spm_verification",
        "regional_compliance",
        "correspondence_tracking",
        "disposisi_check",
        "general_consultation"
    ],
    "PLANNING_SUPPORT": [
        "full_audit",
        "view_precedents",
        "planning_verification",
        "system_health",
        "correspondence_tracking",
        "disposisi_check",
        "general_consultation"
    ],
    "OFFICE_STAFF": [
        "correspondence_tracking",
        "disposisi_check",
        "nd_laporan_generate",
        "general_consultation"
    ]
}


def _load_whitelist() -> Dict[str, Any]:
    global _WHITELIST_CACHE, _WHITELIST_CACHE_MTIME
    if CONFIG_PATH.exists():
        try:
            mtime = CONFIG_PATH.stat().st_mtime
            if _WHITELIST_CACHE is not None and mtime <= _WHITELIST_CACHE_MTIME:
                return _WHITELIST_CACHE
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                _WHITELIST_CACHE = json.load(f)
                _WHITELIST_CACHE_MTIME = mtime
                return _WHITELIST_CACHE
        except Exception as e:
            logger.error(f"Failed to load whitelist config: {e}")
            if _WHITELIST_CACHE is not None:
                return _WHITELIST_CACHE
    return {"users": [], "security_mode": "STRICT_WHITELIST_ONLY"}


def reload_whitelist_cache() -> Dict[str, Any]:
    """Force reload whitelist JSON dari disk ke memori cache."""
    global _WHITELIST_CACHE, _WHITELIST_CACHE_MTIME
    _WHITELIST_CACHE = None
    _WHITELIST_CACHE_MTIME = 0.0
    return _load_whitelist()


def list_whitelist_users() -> List[Dict[str, Any]]:
    """Mengembalikan daftar semua profil pengguna terdaftar."""
    data = _load_whitelist()
    return data.get("users", [])


def _resolve_lid_to_phone(lid_str: str) -> Optional[str]:
    """Menerjemahkan WhatsApp LID (Linked Device ID) ke nomor telepon resmi."""
    clean_lid = lid_str.split("@")[0].strip()
    
    # 1. Cek KNOWN_LIDS registry
    if clean_lid in KNOWN_LIDS:
        return KNOWN_LIDS[clean_lid]

    # 2. Cek user aliases di legal_bot_whitelist.json
    wl = _load_whitelist()
    for user in wl.get("users", []):
        aliases = [str(a).split("@")[0].strip() for a in user.get("phone_aliases", [])]
        if clean_lid in aliases:
            phone = user.get("phone_number")
            if phone:
                KNOWN_LIDS[clean_lid] = phone
                return phone

    # 3. Cek file mapping di auth_info
    if AUTH_DIR.exists():
        for f in AUTH_DIR.glob("lid-mapping-*.json"):
            if "_reverse" in f.name:
                continue
            try:
                content = f.read_text(encoding="utf-8")
                if clean_lid in content:
                    phone_part = f.stem.replace("lid-mapping-", "")
                    if phone_part.isdigit():
                        res_phone = "+" + phone_part if not phone_part.startswith("+") else phone_part
                        KNOWN_LIDS[clean_lid] = res_phone
                        return res_phone
            except Exception:
                continue

    return None


def normalize_phone_number(phone: str) -> str:
    """Normalisasi nomor HP ke format E.164 (+628...)."""
    if not phone:
        return ""
    clean_input = str(phone).strip()
    if "@lid" in clean_input or (clean_input.isdigit() and len(clean_input) >= 14 and not clean_input.startswith(("62", "08"))):
        resolved = _resolve_lid_to_phone(clean_input)
        if resolved:
            return resolved
        return clean_input.split("@")[0].strip()

    digits = "".join(c for c in clean_input if c.isdigit() or c == "+")
    if digits.startswith("08"):
        return "+62" + digits[1:]
    elif digits.startswith("628"):
        return "+" + digits
    elif digits.startswith("+628"):
        return digits
    elif digits.endswith("@c.us") or digits.endswith("@s.whatsapp.net"):
        clean = digits.split("@")[0]
        if clean.startswith("628"):
            return "+" + clean
        return clean
    return digits


def get_whitelist_user(phone: str) -> Optional[Dict[str, Any]]:
    """Mencari data pengguna terdaftar berdasarkan nomor telepon, LID, alias, atau user_id."""
    if not phone:
        return None
    raw_query = str(phone).strip()
    clean_phone = normalize_phone_number(raw_query)
    clean_id = raw_query.split("@")[0].strip()

    whitelist = _load_whitelist()
    for user in whitelist.get("users", []):
        u_phone = normalize_phone_number(user.get("phone_number", ""))
        if u_phone and (u_phone == clean_phone or u_phone == raw_query):
            return user
        
        # Cek user_id
        if user.get("user_id", "").lower() == raw_query.lower():
            return user
            
        # Cek phone aliases & LID
        aliases = user.get("phone_aliases", [])
        for a in aliases:
            norm_a = normalize_phone_number(str(a))
            raw_a = str(a).split("@")[0].strip()
            if clean_phone == norm_a or clean_id == raw_a or raw_query == str(a):
                return user
                
    return None


def is_authorized(phone: str, required_permission: Optional[str] = None) -> bool:
    """Memeriksa apakah nomor memiliki izin akses."""
    user = get_whitelist_user(phone)
    if not user:
        clean = normalize_phone_number(phone)
        if clean in ["+6285717223889", "191022999048285"]:
            return True
        return False
    if not required_permission:
        return True
    if user.get("role") == "SUPER_ADMIN":
        return True
    return required_permission in user.get("permissions", [])


def is_admin_user(phone: str) -> bool:
    """Memeriksa apakah pengguna memiliki privilege Administrator."""
    clean = normalize_phone_number(phone)
    if clean in ["+6285717223889", "191022999048285"]:
        return True
    user = get_whitelist_user(phone)
    if not user:
        return False
    if user.get("role") == "SUPER_ADMIN":
        return True
    return "admin_manage" in user.get("permissions", [])


def _sync_to_postgres(user_profile: Dict[str, Any]) -> bool:
    """Menyinkronkan profil ke tabel public.member_profiles di PostgreSQL."""
    try:
        import psycopg2
        clean_url = _get_db_url()
        conn = psycopg2.connect(clean_url, connect_timeout=4)
        cur = conn.cursor()
        
        name = user_profile.get("full_name") or user_profile.get("user_id")
        role = user_profile.get("role", "OFFICE_STAFF")
        phone = user_profile.get("phone_number", "")
        clean_phone_digits = "".join(c for c in phone if c.isdigit())
        
        wa_ids = []
        if clean_phone_digits:
            wa_ids.append(f"{clean_phone_digits}@s.whatsapp.net")
            
        for alias in user_profile.get("phone_aliases", []):
            al_str = str(alias).strip()
            if "@lid" in al_str:
                wa_ids.append(al_str)
            elif al_str.isdigit() and len(al_str) >= 14:
                wa_ids.append(f"{al_str}@lid")
            elif al_str.isdigit() and len(al_str) >= 10:
                wa_ids.append(f"{al_str}@s.whatsapp.net")

        # Catatan: source check constraint mengizinkan: 'google', 'whatsapp', 'manual', 'merged'
        for wid in set(wa_ids):
            cur.execute("""
                INSERT INTO member_profiles (whatsapp_id, name, role, segment, source, phone, updated_at)
                VALUES (%s, %s, %s, 'kantor', 'manual', %s, NOW())
                ON CONFLICT (whatsapp_id) DO UPDATE 
                SET name = EXCLUDED.name,
                    role = EXCLUDED.role,
                    segment = 'kantor',
                    source = 'manual',
                    phone = EXCLUDED.phone,
                    updated_at = NOW();
            """, (wid, name, role, phone))
            
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"Gagal menyinkronkan profil {user_profile.get('user_id')} ke Postgres: {e}")
        return False


def save_whitelist_user(
    identifier: str,
    full_name: str,
    jabatan: str = "Staf Teknis",
    unit_kerja: str = "Ditjen Bina Pembangunan Daerah",
    role: str = "OFFICE_STAFF",
    permissions: Optional[List[str]] = None,
    nip: Optional[str] = None,
    pangkat_golongan: Optional[str] = None,
    tim_kerja: Optional[str] = None,
    linked_phone: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Menyimpan atau memperbarui pengguna di config/legal_bot_whitelist.json
    serta melakukan auto-reload cache dan sinkronisasi ke PostgreSQL.
    """
    if not identifier or not full_name:
        return False, "Nomor WhatsApp / LID dan Nama Lengkap wajib diisi.", {}

    raw_id = str(identifier).strip()
    is_lid = "@lid" in raw_id or (raw_id.isdigit() and len(raw_id) >= 14 and not raw_id.startswith(("62", "08")))
    clean_lid = raw_id.split("@")[0].strip() if is_lid else None

    # Tentukan phone_number utama dan phone_aliases
    if is_lid:
        primary_phone = normalize_phone_number(linked_phone) if linked_phone else f"+{clean_lid}"
        aliases = [clean_lid, f"{clean_lid}@lid"]
        if linked_phone:
            clean_p = normalize_phone_number(linked_phone)
            aliases.append(clean_p)
            digits = "".join(c for c in clean_p if c.isdigit())
            if digits:
                aliases.append(f"{digits}@s.whatsapp.net")
            KNOWN_LIDS[clean_lid] = clean_p
    else:
        primary_phone = normalize_phone_number(raw_id)
        digits = "".join(c for c in primary_phone if c.isdigit())
        aliases = [primary_phone]
        if digits:
            aliases.append(f"{digits}@s.whatsapp.net")
        if linked_phone and ("@lid" in linked_phone or (linked_phone.isdigit() and len(linked_phone) >= 14)):
            l_id = linked_phone.split("@")[0].strip()
            aliases.extend([l_id, f"{l_id}@lid"])
            KNOWN_LIDS[l_id] = primary_phone

    # Tentukan user_id unik berbasis nama
    name_clean = re.sub(r'[^a-zA-Z0-9\s]', '', full_name.lower())
    words = [w for w in name_clean.split() if w not in ["sh", "mh", "se", "sy", "kom", "st", "ma", "cpsp", "pi"]]
    user_id = "_".join(words[:3]) if words else f"user_{digits[:8] if not is_lid else clean_lid[:8]}"

    # Default permissions sesuai role jika tidak dispesifikasikan
    role_upper = role.upper().strip()
    if role_upper not in DEFAULT_ROLE_PERMISSIONS:
        role_upper = "OFFICE_STAFF"
    
    assigned_permissions = permissions if permissions else DEFAULT_ROLE_PERMISSIONS.get(role_upper, ["general_consultation"])

    whitelist = _load_whitelist()
    users_list = whitelist.get("users", [])

    target_idx = -1
    for idx, u in enumerate(users_list):
        if u.get("user_id") == user_id:
            target_idx = idx
            break
        if normalize_phone_number(u.get("phone_number", "")) == primary_phone:
            target_idx = idx
            break
        existing_aliases = [str(a).split("@")[0].strip() for a in u.get("phone_aliases", [])]
        if clean_lid and clean_lid in existing_aliases:
            target_idx = idx
            break

    user_data = {
        "user_id": user_id,
        "phone_number": primary_phone,
        "phone_aliases": list(set(aliases)),
        "full_name": full_name.strip(),
        "jabatan": jabatan.strip(),
        "unit_kerja": unit_kerja.strip(),
        "role": role_upper,
        "permissions": assigned_permissions
    }
    if nip:
        user_data["nip"] = str(nip).strip()
    if pangkat_golongan:
        user_data["pangkat_golongan"] = str(pangkat_golongan).strip()
    if tim_kerja:
        user_data["tim_kerja"] = str(tim_kerja).strip()
    else:
        user_data["tim_kerja"] = unit_kerja.strip()

    if target_idx >= 0:
        old_user = users_list[target_idx]
        merged_aliases = list(set(old_user.get("phone_aliases", []) + aliases))
        user_data["phone_aliases"] = merged_aliases
        user_data["user_id"] = old_user.get("user_id", user_id)
        users_list[target_idx] = user_data
        action_desc = f"Pembaruan data pengguna *{full_name}* berhasil."
    else:
        users_list.append(user_data)
        action_desc = f"Pendaftaran pengguna baru *{full_name}* berhasil."

    whitelist["users"] = users_list

    # Atomic write ke CONFIG_PATH
    try:
        temp_file = CONFIG_PATH.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(whitelist, f, indent=2, ensure_ascii=False)
        temp_file.replace(CONFIG_PATH)
        
        # Reload memori cache
        reload_whitelist_cache()

        # Sinkronkan ke Postgres
        pg_synced = _sync_to_postgres(user_data)
        if pg_synced:
            action_desc += "\n✅ Sinkronisasi profil PostgreSQL: *OK*"
        else:
            action_desc += "\n⚠️ Sinkronisasi PostgreSQL: *Dilewati/Offline*"

        return True, action_desc, user_data
    except Exception as e:
        logger.error(f"Error saving whitelist user: {e}")
        return False, f"Gagal menyimpan whitelist: {str(e)}", {}


def remove_whitelist_user(identifier: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Menghapus pengguna dari whitelist config."""
    if not identifier:
        return False, "ID / Nomor pengguna wajib diisi.", None

    raw_id = str(identifier).strip()
    norm_id = normalize_phone_number(raw_id)
    clean_id = raw_id.split("@")[0].strip()

    whitelist = _load_whitelist()
    users_list = whitelist.get("users", [])
    target_idx = -1
    removed_user = None

    for idx, u in enumerate(users_list):
        if u.get("user_id", "").lower() == raw_id.lower():
            target_idx = idx
            removed_user = u
            break
        if normalize_phone_number(u.get("phone_number", "")) == norm_id:
            target_idx = idx
            removed_user = u
            break
        aliases = [str(a).split("@")[0].strip() for a in u.get("phone_aliases", [])]
        if clean_id in aliases:
            target_idx = idx
            removed_user = u
            break

    if target_idx < 0:
        return False, f"Pengguna dengan identifier '{identifier}' tidak ditemukan di whitelist.", None

    users_list.pop(target_idx)
    whitelist["users"] = users_list

    try:
        temp_file = CONFIG_PATH.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(whitelist, f, indent=2, ensure_ascii=False)
        temp_file.replace(CONFIG_PATH)
        reload_whitelist_cache()

        # Update member_profiles di PostgreSQL (turunkan ke segment default / role GENERAL_USER)
        try:
            import psycopg2
            clean_url = _get_db_url()
            conn = psycopg2.connect(clean_url, connect_timeout=4)
            cur = conn.cursor()
            for wid in removed_user.get("phone_aliases", []):
                cur.execute("UPDATE member_profiles SET segment = 'default', role = 'GENERAL_USER', updated_at = NOW() WHERE whatsapp_id = %s;", (str(wid),))
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass

        return True, f"Pengguna *{removed_user.get('full_name')}* ({removed_user.get('role')}) berhasil dihapus dari whitelist.", removed_user
    except Exception as e:
        return False, f"Gagal menghapus pengguna: {e}", None


def get_user_greeting(phone: str) -> str:
    """Menghasilkan salam pembuka formal berdasar jabatan struktural."""
    user = get_whitelist_user(phone)
    if not user:
        whitelist = _load_whitelist()
        return whitelist.get(
            "default_reject_message",
            "Mohon maaf, nomor Anda belum terdaftar dalam whitelist Legal Co-Pilot."
        )
    return (
        f"Selamat bertugas, *{user.get('full_name')}* ({user.get('jabatan')}).\n"
        f"Saya siap membantu telaah hukum, evaluasi 6-dimensi draf regulasi, "
        f"dan pencarian preseden yudisial Ditjen Bina Pembangunan Daerah."
    )


def update_user_additional_duties(
    identifier: str,
    duty_text: str
) -> Tuple[bool, str, List[str]]:
    """
    Menambahkan tugas dan fungsi tambahan ke profil pengguna whitelist,
    menyimpan ke config JSON, memperbarui PostgreSQL member_profiles, dan me-reload cache.
    """
    if not identifier or not duty_text:
        return False, "Identifier dan uraian tugas tambahan wajib diisi.", []

    user = get_whitelist_user(identifier)
    if not user:
        return False, f"Pengguna dengan identifier '{identifier}' tidak ditemukan di whitelist.", []

    duty_clean = duty_text.strip()
    prefixes_to_strip = [
        "saya juga mengampu", "saya juga ditugaskan", "tugas tambahan saya adalah",
        "tugas tambahan saya", "saya juga anggota", "saya ditunjuk sebagai",
        "selain itu saya", "tugas saya juga", "saya mengawal", "saya juga"
    ]
    for p in prefixes_to_strip:
        if duty_clean.lower().startswith(p):
            duty_clean = duty_clean[len(p):].strip(": ,-")
            break

    duty_clean = duty_clean.capitalize()
    if not duty_clean:
        duty_clean = duty_text.strip()

    whitelist = _load_whitelist()
    users_list = whitelist.get("users", [])
    target_idx = -1
    for idx, u in enumerate(users_list):
        if (
            u.get("user_id", "").lower() == user.get("user_id", "").lower()
            or (user.get("nip") and u.get("nip") == user.get("nip"))
            or (u.get("phone_number") and normalize_phone_number(u.get("phone_number", "")) == normalize_phone_number(user.get("phone_number", "")))
        ):
            target_idx = idx
            break

    if target_idx < 0:
        return False, "Gagal mencocokkan record pengguna di whitelist JSON.", []

    target_user = users_list[target_idx]
    current_duties = target_user.get("tugas_tambahan", [])
    if not isinstance(current_duties, list):
        current_duties = [str(current_duties)] if current_duties else []

    if any(duty_clean.lower() in d.lower() or d.lower() in duty_clean.lower() for d in current_duties):
        return True, "Tugas tambahan serupa sudah tercatat dalam profil.", current_duties

    current_duties.append(duty_clean)
    target_user["tugas_tambahan"] = current_duties
    users_list[target_idx] = target_user
    whitelist["users"] = users_list

    try:
        temp_file = CONFIG_PATH.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(whitelist, f, indent=2, ensure_ascii=False)
        temp_file.replace(CONFIG_PATH)
        reload_whitelist_cache()

        # Update member_profiles di PostgreSQL
        try:
            import psycopg2
            clean_url = _get_db_url()
            conn = psycopg2.connect(clean_url, connect_timeout=4)
            cur = conn.cursor()
            
            user_phone = target_user.get("phone_number", "")
            cur.execute("SELECT metadata FROM member_profiles WHERE phone LIKE %s OR whatsapp_id LIKE %s LIMIT 1;", (f"%{user_phone[-9:]}%", f"%{user_phone[-9:]}%"))
            row = cur.fetchone()
            meta = row[0] if row and row[0] else {}
            meta["tugas_tambahan"] = current_duties
            
            cur.execute("""
                UPDATE member_profiles 
                SET metadata = %s, updated_at = NOW() 
                WHERE phone LIKE %s OR whatsapp_id LIKE %s;
            """, (json.dumps(meta), f"%{user_phone[-9:]}%", f"%{user_phone[-9:]}%"))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as pg_err:
            logger.warning(f"Failed to update metadata in member_profiles: {pg_err}")

        # Update LTM memories
        try:
            import psycopg2
            clean_url = _get_db_url()
            conn = psycopg2.connect(clean_url, connect_timeout=4)
            cur = conn.cursor()
            ltm_key = f"tugas_tambahan_{target_user.get('nip') or target_user.get('user_id')}"
            ltm_content = f"Tugas dan fungsi tambahan {target_user.get('full_name')} ({target_user.get('jabatan')}): " + "; ".join(current_duties)
            ns = str(target_user.get("unit_kerja", "shared_legal")).lower()
            cur.execute("""
                INSERT INTO memories (key, content, namespace, metadata, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (key, namespace) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW();
            """, (ltm_key, ltm_content, ns, json.dumps({"nip": target_user.get("nip"), "nama": target_user.get("full_name")})))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as ltm_err:
            logger.warning(f"Failed to update LTM memories: {ltm_err}")

        return True, f"Tugas tambahan berhasil ditambahkan ke profil {target_user.get('full_name')}.", current_duties
    except Exception as e:
        logger.error(f"Error updating additional duties: {e}")
        return False, str(e), current_duties

