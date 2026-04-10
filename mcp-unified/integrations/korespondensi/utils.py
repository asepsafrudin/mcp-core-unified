import os
import re
import json
import httpx
from typing import Dict, List, Any, Optional
from datetime import datetime

# Advanced logic for parsing POSISI as a story timeline
def parse_posisi_timeline(posisi_str: str, sender: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parses a complex POSISI string into a structured timeline of events.
    Supports units (SES, BU, etc.), dates (D/M), actions (KOREKSI, TTD),
    and personnel (names in brackets).
    
    Format yang didukung:
    1. Normal: "SES 9/3 PUU 11/3" → Sekretaris → PUU
    2. Multi-unit: "PRC, KEU, PUU, Umum 6/1" → Disposisi ke 4 unit sekaligus
    3. Multi-step: "SES 5/2 KOREKSI 5/2 SES 5/2 KOREKSI 6/2 SES 10/2 PUU 11/2"
    """
    import re
    if not posisi_str or str(posisi_str).upper() == "NULL":
        return []

    units = ["SES", "TU", "BU", "KEU", "PRC", "PUU", "PEIPD", "SUPD", "SD", "DIRJEN", "DITJEN", "BANGDA", "UMUM"]
    actions = ["KOREKSI", "REVISI", "TTD", "PARAFA", "PARAF", "ST", "SISTEM", "BAGI", "DITERIMA", "DONE", "SELESAI", "PROSES", "DJ"]
    systems = ["SRIKANDI", "SIMND", "POOLING"]

    # ── Pre-check: Multi-unit comma-separated format ──────────────────────
    # Pattern: "Unit1, Unit2, Unit3, ... DD/M" (e.g., "PRC, KEU, PUU, Umum 6/1")
    multi_unit_pattern = re.compile(
        r'^([A-Za-z]+(?:\s*,\s*[A-Za-z]+)+)\s+(\d{1,2}/\d{1,2})$'
    )
    multi_match = multi_unit_pattern.match(posisi_str.strip())
    
    if multi_match:
        units_part = multi_match.group(1)  # "PRC, KEU, PUU, Umum"
        shared_date = multi_match.group(2)  # "6/1"
        
        # Extract individual units
        unit_names = [u.strip().upper() for u in units_part.split(',')]
        
        timeline = []
        for unit_name in unit_names:
            # Map to canonical name if available
            canonical = next((u for u in units if u == unit_name), unit_name)
            timeline.append({
                "unit": canonical,
                "date": shared_date,
                "action": "DISPOSISI",
                "notes": f"Multi-unit batch: {units_part}"
            })
        
        return timeline

    # ── Standard parsing for non-multi-unit format ────────────────────────
    # Combined pattern for dates, times, brackets, and words
    pattern = re.compile(r'(\d{1,2}/\d{1,2})|(\d{1,2}\.?\d{2}\.?\d{0,2})|(\([^\)]+\))|([a-zA-Z\d\.\-]+)', re.IGNORECASE)
    matches = pattern.finditer(posisi_str)

    timeline = []
    current_unit = "UNKNOWN"
    current_date = None
    current_time = None
    
    tokens = [m.groups() for m in matches]
    
    for date_val, time_val, bracket_val, word_val in tokens:
        # A. Date Found (D/M)
        if date_val:
            current_date = date_val
            # Date Adoption: If last event missing date, update it
            if timeline and timeline[-1].get('date') is None:
                timeline[-1]['date'] = current_date
                # If we updated the last one, we don't need a new UPDATE step unless it's a gap
                continue
            elif not timeline or timeline[-1]['date'] != current_date:
                # New step for new date
                timeline.append({
                    "unit": current_unit, 
                    "date": current_date, 
                    "action": "UPDATE", 
                    "notes": ""
                })
            continue

        # B. Time Found
        if time_val:
            # Clean time format 14.30.00 -> 14.30
            clean_time = str(time_val).replace(".", ":")
            if clean_time.count(":") > 1:
                clean_time = ":".join(clean_time.split(":")[:2])
            current_time = clean_time
            if timeline:
                timeline[-1]["time"] = clean_time
            continue

        # C. Bracket Found
        if bracket_val:
            notes = bracket_val.strip("()")
            # Enhanced social context
            notes_upper = notes.upper()
            if "DIANTAR" in notes_upper or "PEMBAWA" in notes_upper:
                notes = f"Diantar oleh {notes}"
            elif "DIAMBIL" in notes_upper:
                notes = f"Diambil oleh {notes}"
            elif "OLEH" in notes_upper:
                 notes = f"Oleh {notes}"
            
            if timeline:
                timeline[-1]["notes"] = (timeline[-1].get("notes", "") + " " + notes).strip()
            continue

        # D. Word Found
        if word_val:
            word_upper = word_val.upper()
            
            # Unit Matching
            is_unit = any(u == word_upper for u in units)
            if is_unit:
                current_unit = word_upper
                # Add new position check
                timeline.append({
                    "unit": current_unit, 
                    "date": current_date, 
                    "action": "POSITION_CHECK", 
                    "notes": ""
                })
                continue
            
            # Action Matching
            is_action = any(a in word_upper for a in actions)
            if is_action:
                action = word_upper
                if "KOREKSI" in action and sender:
                    action = f"KOREKSI (oleh {sender})"
                
                if timeline:
                    # Merge action into current step if same date/unit
                    last = timeline[-1]
                    if last['unit'] == current_unit and last['date'] == current_date:
                        if last['action'] in ["UPDATE", "POSITION_CHECK"]:
                            last['action'] = action
                        else:
                            last['action'] += f"+{action}"
                    else:
                        timeline.append({"unit": current_unit, "date": current_date, "action": action, "notes": ""})
                else:
                    timeline.append({"unit": current_unit, "date": current_date, "action": action, "notes": ""})
                continue

            # System Matching
            if word_upper in systems:
                if timeline:
                    timeline[-1]["action"] += f" (via {word_val})"

    # Post-process merging redundant steps
    merged = []
    for ev in timeline:
        if not merged:
            merged.append(ev)
            continue
        last = merged[-1]
        # Merge identical consecutive steps
        if ev['unit'] == last['unit'] and ev['date'] == last['date']:
            # Keep action if it's not POSITION_CHECK/UPDATE
            if ev['action'] not in ["UPDATE", "POSITION_CHECK"]:
                last['action'] = ev['action']
            if ev.get('notes'):
                last['notes'] = (last.get('notes', '') + " " + ev['notes']).strip()
            if ev.get('time'):
                last['time'] = ev['time']
        else:
            merged.append(ev)
            
    return merged

def extract_puu_received_date(posisi_str: str) -> Optional[str]:
    """
    Ekstrak tanggal diterima PUU dari kolom POSISI.
    
    Semua data yang mengandung "PUU" diikuti DD/M dianggap sebagai 
    "Surat Masuk PUU" (korespondensi internal ditujukan ke Kelompok Substansi PUU).
    DD/M setelah "PUU" = tanggal diterima oleh PUU.
    
    Format yang didukung:
    1. Normal: "SES 9/3 PUU 11/3" → tanggal diterima PUU = 11/3
    2. Multi-unit: "PRC, KEU, PUU, Umum 6/1" → tanggal diterima PUU = 6/1
    3. Complex: "SES 5/2 KOREKSI 5/2 SES 10/2 PUU 11/2" → tanggal diterima PUU = 11/2
    
    Args:
        posisi_str: String dari kolom POSISI
        
    Returns:
        String tanggal dalam format "DD/M" atau None jika tidak ada PUU
    """
    if not posisi_str or str(posisi_str).upper() == "NULL":
        return None
    
    import re
    
    posisi_upper = posisi_str.upper().strip()
    
    # Cek apakah mengandung PUU
    if "PUU" not in posisi_upper:
        return None
    
    # Pattern 1: Standard format "...PUU DD/M..."
    # Cari PUU diikuti tanggal secara langsung
    puu_date_pattern = re.compile(r'PUU\s+(\d{1,2}/\d{1,2})', re.IGNORECASE)
    match = puu_date_pattern.search(posisi_str)
    if match:
        return match.group(1)

    # Pattern 2: Komma-separated multi-unit yang berakhir dengan tanggal bersama.
    # Menangani bentuk sederhana "PRC, KEU, PUU, Umum 6/1" maupun bentuk campuran
    # seperti "SES 16/3 KOREKSI 16/3 SES 6/4 PUU, BU 6/4".
    trailing_multi_unit_pattern = re.compile(
        r'PUU(?:\s*,\s*[A-Za-z]+)+\s+(\d{1,2}/\d{1,2})(?:\s|$)',
        re.IGNORECASE,
    )
    multi_match = trailing_multi_unit_pattern.search(posisi_str)
    if multi_match:
        return multi_match.group(1)

    # Pattern 3: Fallback ke parser timeline. Ini menangani format kompleks yang
    # tetap bisa dipetakan ke event unit PUU dengan tanggal adopsi dari token sebelumnya.
    for event in parse_posisi_timeline(posisi_str):
        if str(event.get("unit", "")).upper() == "PUU" and event.get("date"):
            return str(event["date"])
    
    return None


def parse_posisi(posisi_str: str) -> Dict[str, Any]:
    """
    Compatibility wrapper for simple status check.
    
    Juga mengekstrak tanggal diterima PUU untuk verifikasi dengan mail merge.
    """
    timeline = parse_posisi_timeline(posisi_str)
    if not timeline:
        return {"original": str(posisi_str), "status": "PENDING", "is_done": False}
        
    last_event = timeline[-1]
    is_done = any(ev['action'] in ['SELESAI', 'TTD', 'DJ'] for ev in timeline)
    
    # Ekstrak tanggal diterima PUU
    puu_received_date = extract_puu_received_date(posisi_str)
    
    return {
        "original": str(posisi_str),
        "status": last_event['action'],
        "owner": last_event['unit'],
        "last_date": last_event['date'],
        "is_done": is_done,
        "timeline_count": len(timeline),
        "puu_received_date": puu_received_date,  # Tanggal diterima oleh PUU
        "is_surat_masuk_puu": puu_received_date is not None  # Flag surat masuk PUU
    }

async def send_telegram_notification(text: str):
    """
    Send a notification to the Telegram Admin.
    Reuses the bot token from the environment.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Try to find the first admin user or allowed user or fallback to TELEGRAM_CHAT_ID
    admin_id = os.getenv("TELEGRAM_ADMIN_USERS", "").split(",")[0]
    if not admin_id:
        admin_id = os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",")[0]
    if not admin_id:
        admin_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not admin_id:
        print("Telegram configuration missing for notifications")
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": admin_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload)
            return res.status_code == 200
    except Exception as e:
        print(f"Failed to send telegram notification: {e}")
        return False

def translate_disposisi(dispo_str: str, sender: Optional[str] = None) -> Dict[str, Any]:
    """
    Translates disposisi text based on organizational rules.
    - XXX -> High Priority / Urgent
    - Code (e.g., 022/set/peipd/2026) -> Forwarding info
    - No Code -> Back to sender (Column 'DARI')
    - Multi units (e.g., 022/SET/BU/KEU) -> Forwarded to all
    """
    if not dispo_str or str(dispo_str).lower() == 'null':
        return {"original": "", "priority": "NORMAL", "info": "Tidak ada disposisi"}
        
    res = {
        "original": dispo_str,
        "priority": "SANGAT PENTING (PRIORITAS SEGERA)" if "XXX" in dispo_str.upper() else "NORMAL",
        "forwarded_from": None,
        "forwarded_to_list": [],
        "instructions": []
    }
    
    # Unit mapping dictionary
    unit_map = {
        "SET": "Sekretaris Ditjen",
        "SES": "Sekretaris Ditjen",
        "BANGDA": "Ditjen Bina Pembangunan Daerah",
        "PEIPD": "Direktorat PEIPD",
        "SUPD I": "Direktorat SUPD I",
        "SUPD.I": "Direktorat SUPD I",
        "SUPD II": "Direktorat SUPD II",
        "SUPD.II": "Direktorat SUPD II",
        "SUPD III": "Direktorat SUPD III",
        "SUPD.III": "Direktorat SUPD III",
        "SUPD IV": "Direktorat SUPD IV",
        "SUPD.IV": "Direktorat SUPD IV",
        "SUPDIV": "Direktorat SUPD IV (Typo)",
        "BU": "Bagian Umum",
        "KEU": "Bagian Keuangan",
        "PRC": "Bagian Perencanaan",
        "PUU": "Kelompok Substansi Perundang-Undangan (PUU)"
    }
    
    # 1. Extract instructions (verbs)
    instruction_keywords = [
        "PROSES LEBIH LANJUT", "KOORDINASIKAN", "TELAAH", "CERMATI", 
        "LAPORKAN", "IKUTI PERKEMBANGANNYA", "KONFIRMASIKAN", "DIMONITOR", "BICARAKAN"
    ]
    u_dispo = dispo_str.upper()
    for ik in instruction_keywords:
        if ik in u_dispo:
            res["instructions"].append(ik)
            
    # 2. Extract Reference Code and forwarding info
    # Find all units in the slash pattern
    slash_parts = re.findall(r'/([A-Z\s\.]+)', u_dispo)
    
    if slash_parts:
        # First part after the first slash is usually FROM
        # Subsequent parts are TO
        res["forwarded_from"] = unit_map.get(slash_parts[0].strip(), slash_parts[0].strip())
        
        # Collect all recipients
        for part in slash_parts[1:]:
            clean_part = part.strip()
            # Stop if we hit the year (usually 4 digits)
            if re.match(r'^\d{4}$', clean_part): break
            res["forwarded_to_list"].append(unit_map.get(clean_part, clean_part))
            
        res["ref_code"] = re.search(r'\d+/[A-Z\s\./]+', u_dispo).group(0) if re.search(r'\d+/[A-Z\s\./]+', u_dispo) else None
    else:
        # RULES: No code found, return to sender
        if sender:
            res["forwarded_from"] = "Sekretaris"
            res["forwarded_to_list"] = [unit_map.get(sender.upper(), sender)]
            res["priority_reason"] = "DIKEMBALIKAN KE PEMRAKARSA (Tanpa Kode Referensi)"

    return res

def format_new_letter_message(source: str, letters: List[Dict[str, Any]]) -> str:
    if not letters:
        return ""
        
    # Load bot username from env (fallback to actual bot)
    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "Asep_mcp_bot")
    dashboard_url = f"https://t.me/{bot_username}?start=dashboard"
    
    emoji = "📥" if "internal" in source.lower() else "📩"
    msg = f"{emoji} *SURAT MASUK BARU ({source.upper()})*\n\n"
    
    for i, letter in enumerate(letters[:5]): # Max 5 to prevent spam
        dari = letter.get('DARI') or letter.get('Surat Dari') or "N/A"
        hal = letter.get('HAL') or letter.get('Perihal') or "N/A"
        nomor = letter.get('NOMOR ND') or letter.get('Nomor Surat') or "-"
        
        msg += f"{i+1}. *{dari}*\n"
        msg += f"   📂 No: `{nomor}`\n"
        msg += f"   📝 Hal: _{hal[:100]}..._\n\n"
        
    if len(letters) > 5:
        msg += f"_...dan {len(letters)-5} surat lainnya._\n"
        
    msg += f"\n🔗 [Buka Dashboard]({dashboard_url})"
    return msg
