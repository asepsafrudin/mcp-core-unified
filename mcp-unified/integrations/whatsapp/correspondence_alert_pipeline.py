"""
correspondence_alert_pipeline.py — Pipeline Notifikasi WhatsApp Surat Masuk PUU.

Mengambil data surat masuk internal & eksternal dari database master korespondensi
(periode September 2026 ke atas) yang berstatus:
1. Belum terverifikasi (is_verified_puu = false / tgl_diterima_puu IS NULL / status = 'Belum Diproses')
2. Belum memiliki data PIC (pic_name IS NULL atau kosong)

Menyusun ringkasan eksekutif dan mengirimkannya ke WhatsApp staf berwenang
(Bpk. Ahmad Subarjo / +6285885241434) via Baileys Webhook.
Mendukung deduplikasi / idempotency via tabel correspondence_notification_dispatches.
"""

import os
import sys
import json
import time
import logging
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Setup path & load environment
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
CORE_DIR = BASE_DIR / "core" / "mcp-unified"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

try:
    from scripts.load_env import load_env
    load_env()
except ImportError:
    pass

logger = logging.getLogger("correspondence_alert_pipeline")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

DEFAULT_RECIPIENT_PHONE = "+6285885241434"
DEFAULT_RECIPIENT_JID = "6285885241434@s.whatsapp.net"
BAILEYS_WEBHOOK_URL = os.getenv("WHATSAPP_WEBHOOK_URL", "http://127.0.0.1:3001/webhook/whatsapp")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "mcp_unified_webhook_2026")


def get_db_connection():
    """Membuka koneksi ke database PostgreSQL mcp_knowledge."""
    import psycopg2
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pg_user = os.getenv("POSTGRES_USER", "mcp_user")
        pg_pass = os.getenv("POSTGRES_PASSWORD", "")
        pg_host = os.getenv("POSTGRES_HOST", "127.0.0.1")
        pg_port = os.getenv("POSTGRES_PORT", "5433")
        pg_db   = os.getenv("POSTGRES_DB", "mcp_knowledge")
        db_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    clean_url = db_url.replace("@localhost:", "@127.0.0.1:")
    return psycopg2.connect(clean_url, connect_timeout=5)


def ensure_tracking_table():
    """Memastikan tabel pelacakan notifikasi sudah dibuat di PostgreSQL."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.correspondence_notification_dispatches (
                id SERIAL PRIMARY KEY,
                unique_id TEXT NOT NULL,
                nomor_nd TEXT,
                origin TEXT,
                recipient_phone TEXT NOT NULL,
                recipient_jid TEXT NOT NULL,
                status_surat TEXT,
                pic_status TEXT,
                dispatch_status TEXT DEFAULT 'SENT',
                dispatched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                metadata JSONB DEFAULT '{}'::jsonb
            );
            CREATE INDEX IF NOT EXISTS idx_corr_notif_unique_id ON public.correspondence_notification_dispatches(unique_id);
            CREATE INDEX IF NOT EXISTS idx_corr_notif_dispatched_at ON public.correspondence_notification_dispatches(dispatched_at);
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed ensuring tracking table: {e}")


def fetch_pending_september_correspondence(conn, filter_already_dispatched: bool = True, recipient_phone: str = DEFAULT_RECIPIENT_PHONE) -> List[Dict[str, Any]]:
    """
    Mengambil seluruh surat masuk (internal & eksternal) mulai September 2026
    yang belum terverifikasi atau belum ber-PIC.
    """
    cur = conn.cursor()
    
    # Kueri internal dan eksternal
    sql = """
    WITH raw_letters AS (
        SELECT 
            'INTERNAL'::text as origin,
            id,
            unique_id,
            nomor_nd,
            dari,
            dari_full,
            hal,
            tanggal_surat,
            tanggal_diterima_puu,
            posisi,
            status_pengiriman,
            pic_name,
            NULL::boolean as is_verified_puu,
            agenda_puu,
            drive_file_url
        FROM public.surat_masuk_puu_internal
        WHERE (tanggal_surat >= '2026-09-01' OR tanggal_diterima_puu >= '2026-09-01')
          AND (
              (pic_name IS NULL OR TRIM(pic_name) = '' OR pic_name = '-')
              OR (tanggal_diterima_puu IS NULL OR status_pengiriman = 'Belum Diproses' OR status_pengiriman ILIKE '%belum%')
          )

        UNION ALL

        SELECT 
            'EKSTERNAL'::text as origin,
            id,
            unique_id,
            nomor_nd,
            dari,
            dari_full,
            hal,
            tanggal_surat,
            tanggal_diterima_puu,
            posisi,
            status_pengiriman,
            pic_name,
            is_verified_puu,
            agenda_puu,
            drive_file_url
        FROM public.surat_masuk_puu_eksternal
        WHERE (tanggal_surat >= '2026-09-01' OR tanggal_diterima_puu >= '2026-09-01' OR tanggal_disposisi_ses >= '2026-09-01' OR tanggal_diterima_ula >= '2026-09-01')
          AND (
              (pic_name IS NULL OR TRIM(pic_name) = '' OR pic_name = '-')
              OR (is_verified_puu = FALSE OR tanggal_diterima_puu IS NULL OR status_pengiriman = 'Belum Diproses')
          )
    )
    SELECT 
        origin,
        id,
        unique_id,
        nomor_nd,
        dari,
        dari_full,
        hal,
        tanggal_surat,
        tanggal_diterima_puu,
        posisi,
        status_pengiriman,
        pic_name,
        is_verified_puu,
        agenda_puu,
        drive_file_url
    FROM raw_letters
    ORDER BY origin ASC, COALESCE(tanggal_diterima_puu, tanggal_surat) DESC NULLS LAST, id DESC;
    """
    
    cur.execute(sql)
    col_names = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    
    results = []
    for r in rows:
        item = dict(zip(col_names, r))
        
        # Konversi tipe date ke string
        if item.get("tanggal_surat"):
            item["tanggal_surat_str"] = item["tanggal_surat"].strftime("%d/%m/%Y")
        else:
            item["tanggal_surat_str"] = "-"
            
        if item.get("tanggal_diterima_puu"):
            item["tanggal_diterima_puu_str"] = item["tanggal_diterima_puu"].strftime("%d/%m/%Y")
        else:
            item["tanggal_diterima_puu_str"] = "Belum Terverifikasi"
            
        # Klasifikasi isu
        has_pic = bool(item.get("pic_name") and item.get("pic_name").strip() and item.get("pic_name").strip() != "-")
        is_verified = (item.get("origin") == "EKSTERNAL" and item.get("is_verified_puu") is True and item.get("tanggal_diterima_puu") is not None) or \
                      (item.get("origin") == "INTERNAL" and item.get("tanggal_diterima_puu") is not None and item.get("status_pengiriman") != "Belum Diproses")
        
        item["has_pic"] = has_pic
        item["is_verified"] = is_verified
        
        if not is_verified and not has_pic:
            item["category"] = "UNVERIFIED_AND_NO_PIC"
            item["urgency_label"] = "🔴 Belum Diverifikasi & Belum Ada PIC"
        elif not has_pic:
            item["category"] = "NO_PIC"
            item["urgency_label"] = "🟡 Belum Memiliki Data PIC"
        else:
            item["category"] = "UNVERIFIED"
            item["urgency_label"] = "🟠 Belum Diverifikasi / Diproses"

        results.append(item)
        
    cur.close()

    if filter_already_dispatched:
        # Cek apakah sudah pernah dikirim ke recipient
        cur_disp = conn.cursor()
        cur_disp.execute("""
            SELECT unique_id, dispatched_at 
            FROM public.correspondence_notification_dispatches 
            WHERE recipient_phone = %s
        """, (recipient_phone,))
        dispatched_map = {row[0]: row[1] for row in cur_disp.fetchall()}
        cur_disp.close()
        
        filtered = [item for item in results if item["unique_id"] not in dispatched_map]
        return filtered

    return results


def format_executive_alert_message(letters: List[Dict[str, Any]], recipient_name: str = "Bpk. Ahmad Subarjo") -> str:
    """
    Membuat naskah notifikasi WhatsApp yang elegan, terstruktur, dan mudah dibaca pimpinan/staf.
    """
    total_letters = len(letters)
    now_str = datetime.now().strftime("%d %B %Y %H:%M WIB")
    
    # Kelompokkan surat
    cat_both = [l for l in letters if l.get("category") == "UNVERIFIED_AND_NO_PIC"]
    cat_no_pic = [l for l in letters if l.get("category") == "NO_PIC"]
    cat_unver = [l for l in letters if l.get("category") == "UNVERIFIED"]
    
    lines = [
        "📢 *NOTIFIKASI SURAT MASUK PUU — PERIODE SEPTEMBER 2026*",
        f"_Sistem Otomasi Korespondensi SATRIA Ditjen Bina Bangda_",
        f"📅 Waktu Audit: {now_str}",
        f"👤 Penerima Atensi: *{recipient_name}* (Pengadministrasi Perkantoran PUU)",
        "",
        f"Ditemukan *{total_letters} Surat Masuk* yang membutuhkan tindak lanjut administrasi:",
        f"• 🔴 Belum Diverifikasi & Tanpa PIC: *{len(cat_both)} surat*",
        f"• 🟡 Belum Memiliki PIC: *{len(cat_no_pic)} surat*",
        f"• 🟠 Belum Diproses: *{len(cat_unver)} surat*",
        "──────────────────────────────"
    ]
    
    idx = 1
    # 1. Kategori Kritis: Belum Diverifikasi & Tanpa PIC
    if cat_both:
        lines.append("\n🚨 *KATEGORI A: BELUM DIVERIFIKASI & BELUM ADA PIC*")
        for l in cat_both:
            origin_badge = "🏛️ [EKSTERNAL]" if l["origin"] == "EKSTERNAL" else "🏢 [INTERNAL]"
            lines.append(f"\n*{idx}. {origin_badge} {l.get('nomor_nd')}*")
            lines.append(f"   ▫️ *Pengirim:* {l.get('dari_full') or l.get('dari')}")
            lines.append(f"   ▫️ *Perihal:* {l.get('hal')}")
            lines.append(f"   ▫️ *Tgl Surat:* {l.get('tanggal_surat_str')}")
            lines.append(f"   ▫️ *Tgl Terima PUU:* {l.get('tanggal_diterima_puu_str')}")
            lines.append(f"   ▫️ *Posisi:* {l.get('posisi') or '-'}")
            lines.append(f"   ▫️ *Status:* {l.get('urgency_label')}")
            idx += 1

    # 2. Kategori Belum Memiliki PIC
    if cat_no_pic:
        lines.append("\n⚠️ *KATEGORI B: MENUNGGU PENUNJUKAN PIC ANALIS/PERANCANG*")
        for l in cat_no_pic:
            origin_badge = "🏛️ [EKSTERNAL]" if l["origin"] == "EKSTERNAL" else "🏢 [INTERNAL]"
            lines.append(f"\n*{idx}. {origin_badge} {l.get('nomor_nd')}*")
            lines.append(f"   ▫️ *Pengirim:* {l.get('dari_full') or l.get('dari')}")
            lines.append(f"   ▫️ *Perihal:* {l.get('hal')}")
            lines.append(f"   ▫️ *Tgl Surat:* {l.get('tanggal_surat_str')}")
            lines.append(f"   ▫️ *Tgl Diterima PUU:* {l.get('tanggal_diterima_puu_str')}")
            lines.append(f"   ▫️ *Agenda PUU:* {l.get('agenda_puu') or '-'}")
            lines.append(f"   ▫️ *Status:* {l.get('urgency_label')}")
            idx += 1

    # 3. Kategori Belum Diproses
    if cat_unver:
        lines.append("\n📋 *KATEGORI C: STATUS BELUM DIPROSES*")
        for l in cat_unver:
            origin_badge = "🏛️ [EKSTERNAL]" if l["origin"] == "EKSTERNAL" else "🏢 [INTERNAL]"
            lines.append(f"\n*{idx}. {origin_badge} {l.get('nomor_nd')}*")
            lines.append(f"   ▫️ *Pengirim:* {l.get('dari_full') or l.get('dari')}")
            lines.append(f"   ▫️ *Perihal:* {l.get('hal')}")
            lines.append(f"   ▫️ *Tgl Surat:* {l.get('tanggal_surat_str')}")
            lines.append(f"   ▫️ *PIC Terdata:* {l.get('pic_name') or '-'}")
            lines.append(f"   ▫️ *Status:* {l.get('status_pengiriman') or 'Belum Diproses'}")
            idx += 1

    lines.extend([
        "\n──────────────────────────────",
        "💡 *Rekomendasi Tindak Lanjut:*",
        "1. Lakukan verifikasi fisik berkas surat masuk pada loket administrasi PUU.",
        "2. Input tanggal diterima PUU dan no. agenda disposisi untuk surat yang belum terverifikasi.",
        "3. Koordinasikan bersama Ketua Tim Kerja (Bpk. Faisal Baharuddin / Ibu Lady Diana) terkait penunjukan PIC Analis.",
        "\n_Pesan otomatis dikirimkan oleh Sub-Sistem Notifikasi SATRIA Ditjen Bangda._"
    ])
    
    return "\n".join(lines)


def send_whatsapp_message(recipient_jid: str, message_text: str, request_id: Optional[str] = None) -> Tuple[bool, str]:
    """
    Mengirimkan pesan ke Baileys Webhook port 3001.
    """
    req_id = request_id or f"notif-corr-{int(time.time())}"
    payload = {
        "user_id": recipient_jid,
        "response": message_text,
        "request_id": req_id
    }
    
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BAILEYS_WEBHOOK_URL,
        data=req_data,
        headers={
            "Content-Type": "application/json",
            "x-webhook-secret": WEBHOOK_SECRET,
            "User-Agent": "SATRIA-Correspondence-Alert-Pipeline/1.0"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            resp_body = response.read().decode("utf-8")
            res_json = json.loads(resp_body)
            logger.info(f"Notification successfully enqueued to Baileys for {recipient_jid}: {res_json}")
            return True, "Enqueued to Baileys successfully"
    except urllib.error.HTTPError as e:
        err_msg = f"HTTP Error {e.code}: {e.read().decode('utf-8')}"
        logger.error(f"Failed sending alert: {err_msg}")
        return False, err_msg
    except Exception as e:
        logger.error(f"Network / connection error: {e}")
        return False, str(e)


def record_dispatches(conn, letters: List[Dict[str, Any]], recipient_phone: str, recipient_jid: str):
    """
    Mencatat pengiriman surat ke tabel correspondence_notification_dispatches agar tidak terjadi spam.
    """
    cur = conn.cursor()
    for l in letters:
        cur.execute("""
            INSERT INTO public.correspondence_notification_dispatches 
                (unique_id, nomor_nd, origin, recipient_phone, recipient_jid, status_surat, pic_status, dispatch_status, dispatched_at, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'SENT', NOW(), %s)
        """, (
            l.get("unique_id"),
            l.get("nomor_nd"),
            l.get("origin"),
            recipient_phone,
            recipient_jid,
            l.get("status_pengiriman"),
            l.get("pic_name") or "NO_PIC",
            json.dumps({
                "category": l.get("category"),
                "tanggal_surat": l.get("tanggal_surat_str"),
                "tanggal_diterima_puu": l.get("tanggal_diterima_puu_str")
            })
        ))
    conn.commit()
    cur.close()


def run_pipeline(
    recipient_phone: str = DEFAULT_RECIPIENT_PHONE,
    force: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Menjalankan siklus eksekusi penuh pipeline notifikasi surat masuk September 2026.
    """
    ensure_tracking_table()
    conn = get_db_connection()
    
    clean_digits = "".join(c for c in recipient_phone if c.isdigit())
    recipient_jid = f"{clean_digits}@s.whatsapp.net"
    
    # Ambil data surat
    letters = fetch_pending_september_correspondence(conn, filter_already_dispatched=(not force), recipient_phone=recipient_phone)
    
    if not letters:
        logger.info(f"Tidak ada surat baru bulan September yang perlu dinotifikasikan ke {recipient_phone} (force={force}).")
        conn.close()
        return {
            "status": "skipped",
            "message": "Tidak ada surat pending baru yang perlu dikirim (semua sudah pernah dinotifikasikan atau sudah memiliki PIC/terverifikasi).",
            "count": 0,
            "letters": []
        }
        
    logger.info(f"Ditemukan {len(letters)} surat masuk September yang perlu atensi!")
    
    # Dapatkan nama penerima dari whitelist
    from integrations.whatsapp.whitelist_guard import get_whitelist_user
    user = get_whitelist_user(recipient_phone)
    recipient_name = user.get("full_name", "Bpk. Ahmad Subarjo") if user else "Bpk. Ahmad Subarjo"
    
    message_text = format_executive_alert_message(letters, recipient_name=recipient_name)
    
    if dry_run:
        logger.info("[DRY RUN] Pesan notifikasi tidak dikirimkan secara fisik. Pratinjau:")
        print(message_text)
        conn.close()
        return {
            "status": "dry_run",
            "recipient": recipient_phone,
            "recipient_name": recipient_name,
            "count": len(letters),
            "message_preview": message_text,
            "letters": letters
        }
        
    # Kirimkan pesan melalui Baileys Webhook
    success, reason = send_whatsapp_message(recipient_jid, message_text)
    
    if success:
        # Catat riwayat dispatch
        record_dispatches(conn, letters, recipient_phone, recipient_jid)
        logger.info(f"Sukses mengirim notifikasi dan mencatat dispatch untuk {len(letters)} surat.")
        
    conn.close()
    
    return {
        "status": "success" if success else "failed",
        "recipient": recipient_phone,
        "recipient_jid": recipient_jid,
        "recipient_name": recipient_name,
        "count": len(letters),
        "dispatched": success,
        "reason": reason,
        "message": message_text
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline Notifikasi WhatsApp Surat Masuk PUU")
    parser.add_argument("--phone", default=DEFAULT_RECIPIENT_PHONE, help="Nomor penerima WhatsApp")
    parser.add_argument("--force", action="store_true", help="Paksa kirim meskipun sudah pernah dikirim sebelumnya")
    parser.add_argument("--dry-run", action="store_true", help="Pratinjau pesan tanpa mengirim WhatsApp fisik")
    
    args = parser.parse_args()
    result = run_pipeline(recipient_phone=args.phone, force=args.force, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, default=str))
