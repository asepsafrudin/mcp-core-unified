"""
MCP Tools for WhatsApp Integration using WAHA.
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import Context

from .client import get_whatsapp_client


async def whatsapp_get_status(ctx: Context) -> str:
    """
    Get the status of the WhatsApp integration and sessions.
    """
    try:
        client = get_whatsapp_client()
        status = await client.get_status()
        sessions = await client.list_sessions()
        
        return json.dumps({
            "success": True,
            "status": status,
            "sessions": sessions
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def whatsapp_send_message(
    ctx: Context,
    to: str,
    text: str,
    session: str = "default"
) -> str:
    """
    Send a WhatsApp message to a specific number or chat.
    
    Args:
        to: Recipient phone number with country code (e.g. '62812345678')
            Note: Do not include +, just the numbers.
        text: The message content to send.
        session: WhatsApp session name (default: 'default')
    """
    try:
        # Normalize chat_id
        chat_id = to
        if not chat_id.endswith("@c.us") and not chat_id.endswith("@g.us"):
            chat_id = f"{chat_id}@c.us"
            
        client = get_whatsapp_client()
        result = await client.send_message(chat_id=chat_id, text=text, session_name=session)
        
        return json.dumps({
            "success": True,
            "result": result
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def whatsapp_get_qr(
    ctx: Context,
    session: str = "default"
) -> str:
    """
    Get the QR code for authenticating a WhatsApp session.
    Visit the returned URL or use the base64 data to link your device.
    """
    try:
        client = get_whatsapp_client()
        
        # Ensure session is started
        try:
            await client.start_session(session)
        except:
            pass # Might already be started
            
        qr_data = await client.get_qr_code(session_name=session)
        
        return json.dumps({
            "success": True,
            "session": session,
            "qr": qr_data,
            "instructions": "Scan this QR code in your WhatsApp mobile app (Linked Devices > Link a Device)"
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def whatsapp_list_chats(
    ctx: Context,
    session: str = "default"
) -> str:
    """
    List active chats and groups in a WhatsApp session.
    """
    try:
        client = get_whatsapp_client()
        chats = await client.get_chats(session_name=session)
        
        return json.dumps({
            "success": True,
            "session": session,
            "chats": chats
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def whatsapp_get_messages(
    ctx: Context,
    chat_id: str,
    limit: int = 20,
    session: str = "default"
) -> str:
    """
    Get recent messages from a specific WhatsApp chat or group.
    
    Args:
        chat_id: The ID of the chat (e.g. '62812345678@c.us' or 'group_id@g.us')
        limit: Number of messages to retrieve (default: 20)
        session: WhatsApp session name (default: 'default')
    """
    try:
        client = get_whatsapp_client()
        messages = await client.get_messages(chat_id=chat_id, limit=limit, session_name=session)
        
        return json.dumps({
            "success": True,
            "session": session,
            "chat_id": chat_id,
            "messages": messages
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def whatsapp_send_formal_report(
    ctx: Context,
    recipient_name: str,
    recipient_phone: str,
    title: str,
    summary: str,
    details: Optional[Dict[str, Any]] = None,
    impact: str = "",
    recommendation: str = "",
    report_type: str = "anomaly"
) -> str:
    """
    Send a formal/professional report via WhatsApp.
    Useful for reporting data anomalies, audit findings, or critical alerts.
    
    Args:
        recipient_name: Name of the person receiving the report (e.g. 'Pak Asep')
        recipient_phone: Phone number (e.g. '62812345678')
        title: Short title of the finding/issue
        summary: Clear summary of the discovery
        details: Optional key-value pairs with technical details
        impact: Describe the impact of this finding
        recommendation: Provide a call to action or fix
        report_type: Category of the report (default: 'anomaly')
    """
    try:
        from core.reporting.service import UniversalReport, get_reporting_service
        
        report = UniversalReport(
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            title=title,
            summary=summary,
            details=details or {},
            impact=impact,
            recommendation=recommendation,
            report_type=report_type
        )
        
        service = get_reporting_service()
        result = await service.send_report(report, channel="whatsapp")
        
        return json.dumps({
            "success": True,
            "message": "Formal report sent successfully",
            "report_id": report.report_id,
            "wa_result": result.get("wa_result")
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# ===== TASK-157: read_activity_log =====

# Retensi default 90 hari (UU 27/2022 PDP: simpan seperlunya, hapus selebihnya).
ACTIVITY_LOG_RETENTION_DAYS = int(os.getenv("SATRIA_LOG_RETENTION_DAYS", "90"))


def _mask_phone_number(phone: Any) -> str:
    """TASK-157: masking nomor WA — tampilkan 4 digit awal + '***'."""
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) < 4:
        return "***"
    return f"{digits[:4]}***"


def _parse_entry_timestamp(entry: Dict[str, Any]) -> Optional[datetime]:
    """TASK-157: ambil timestamp entri dari berbagai kunci yang dipakai logger."""
    for key in ("logged_at", "timestamp"):
        raw = entry.get(key)
        if isinstance(raw, str) and raw:
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                continue
    return None


def _entry_intent(entry: Dict[str, Any]) -> str:
    """TASK-157: normalisasi intent dari berbagai bentuk entri log."""
    for key in ("intent", "non_service_category"):
        val = entry.get(key)
        if isinstance(val, str) and val:
            return val
    if entry.get("is_non_service"):
        return "non_service"
    tool_name = entry.get("tool_name")
    if isinstance(tool_name, str) and tool_name:
        return f"tool:{tool_name}"
    return "unknown"


def _aggregate_activity_logs(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """TASK-157: agregasi statistik analitik dari entri log (tanpa PII)."""
    by_intent: Dict[str, int] = {}
    by_day: Dict[str, int] = {}
    by_hour: Dict[str, int] = {}
    tool_usage: Dict[str, int] = {}
    response_times: List[float] = []
    unique_users = set()
    fallback_count = 0

    for e in entries:
        intent = _entry_intent(e)
        by_intent[intent] = by_intent.get(intent, 0) + 1

        ts = _parse_entry_timestamp(e)
        if ts:
            by_day[ts.strftime("%Y-%m-%d")] = by_day.get(ts.strftime("%Y-%m-%d"), 0) + 1
            by_hour[ts.strftime("%H")] = by_hour.get(ts.strftime("%H"), 0) + 1

        for phone_key in ("user_phone", "phone_number", "phone"):
            if e.get(phone_key):
                unique_users.add(_mask_phone_number(e[phone_key]))
                break

        rt_found = False
        for rt_key in ("response_time_ms", "duration_ms", "total_response_ms"):
            rt = e.get(rt_key)
            if isinstance(rt, (int, float)) and rt >= 0:
                response_times.append(float(rt))
                rt_found = True
                break
        if not rt_found:
            latency = e.get("latency_breakdown")
            if isinstance(latency, dict):
                total = latency.get("total_response_ms")
                if isinstance(total, (int, float)):
                    response_times.append(float(total))

        tool_calls = e.get("tool_calls")
        if isinstance(tool_calls, list):
            for tc in tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else str(tc)
                if name:
                    tool_usage[name] = tool_usage.get(name, 0) + 1
        elif isinstance(e.get("tool_name"), str):
            tool_usage[e["tool_name"]] = tool_usage.get(e["tool_name"], 0) + 1

        if e.get("fallback_used"):
            fallback_count += 1

    response_times.sort()
    stats: Dict[str, Any] = {
        "total_interactions": len(entries),
        "unique_users_masked": len(unique_users),
        "by_intent": dict(sorted(by_intent.items(), key=lambda kv: kv[1], reverse=True)),
        "by_day": dict(sorted(by_day.items())),
        "by_hour": dict(sorted(by_hour.items())),
        "tool_usage": dict(sorted(tool_usage.items(), key=lambda kv: kv[1], reverse=True)),
        "fallback_count": fallback_count,
    }
    if response_times:
        stats["response_time_ms"] = {
            "avg": round(sum(response_times) / len(response_times), 1),
            "p50": round(response_times[len(response_times) // 2], 1),
            "p95": round(response_times[min(len(response_times) - 1, int(len(response_times) * 0.95))], 1),
            "samples": len(response_times),
        }
    return stats


def cleanup_old_activity_logs(
    retention_days: Optional[int] = None,
    log_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """TASK-157 (157-D): hapus file JSONL interaksi lebih tua dari retensi.

    Mengembalikan {deleted_files, kept_files, retention_days}.
    """
    from .interaction_logger import INTERACTIONS_DIR

    keep = retention_days if retention_days is not None else ACTIVITY_LOG_RETENTION_DAYS
    target_dir = Path(log_dir) if log_dir else INTERACTIONS_DIR
    if not target_dir.exists():
        return {"deleted_files": [], "kept_files": [], "retention_days": keep}
    cutoff = datetime.now() - timedelta(days=keep)
    deleted, kept = [], []
    for f in sorted(target_dir.glob("interactions_*.jsonl")):
        try:
            file_date = datetime.strptime(f.stem.replace("interactions_", ""), "%Y%m%d")
        except ValueError:
            kept.append(f.name)
            continue
        if file_date < cutoff:
            f.unlink()
            deleted.append(f.name)
        else:
            kept.append(f.name)
    return {"deleted_files": deleted, "kept_files": kept, "retention_days": keep}


async def read_activity_log(
    ctx: Context,
    caller_phone: str,
    days: int = 7,
    intent: Optional[str] = None,
    limit: int = 50,
    include_content: bool = False,
) -> str:
    """Read SATRIA WhatsApp interaction analytics (admin only).

    Aggregates interaction logs written by the async InteractionLogger into
    intent distribution, daily/hourly volume, tool usage, and latency stats.
    Phone numbers are masked; message content is excluded unless include_content
    is true AND the caller is a verified admin.

    Args:
        caller_phone: Phone number of the tool caller (must be admin/whitelisted).
        days: How many days back to analyze (default: 7, max: 90).
        intent: Optional intent filter (e.g. 'ADMIN_WHITELIST', 'non_service').
        limit: Max sample entries returned (default: 50, max: 200).
        include_content: Include sanitized message samples (admin only, default: False).
    """
    from .interaction_logger import InteractionLogger
    from .whitelist_guard import is_admin_user

    try:
        if not caller_phone or not is_admin_user(caller_phone):
            return json.dumps({"success": False, "error": "unauthorized: admin only"}, indent=2)

        days = max(1, min(int(days or 7), 90))
        limit = max(1, min(int(limit or 50), 200))

        activity_logger = InteractionLogger()
        entries = activity_logger.load_recent_interactions(days=days)

        if intent:
            intent_lower = intent.lower()
            entries = [e for e in entries if _entry_intent(e).lower() == intent_lower]

        stats = _aggregate_activity_logs(entries)
        result: Dict[str, Any] = {
            "success": True,
            "window_days": days,
            "intent_filter": intent,
            "stats": stats,
        }

        if include_content:
            samples = []
            for e in entries[-limit:]:
                samples.append({
                    "timestamp": e.get("logged_at") or e.get("timestamp"),
                    "user_phone_masked": _mask_phone_number(
                        e.get("user_phone") or e.get("phone_number") or e.get("phone")
                    ),
                    "intent": _entry_intent(e),
                    "input_text": e.get("input_text", ""),
                })
            result["samples"] = samples
            result["samples_count"] = len(samples)

        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def generate_draft_naskah(
    ctx: Context,
    jenis_naskah: str,
    data: str,
    output_filename: str = ""
) -> str:
    """
    Menghasilkan draft dokumen naskah dinas resmi (Nota Dinas Laporan, Nota Dinas Pengantar, Surat Keluar).
    
    Args:
        jenis_naskah: Jenis naskah ('laporan', 'pengantar_sesditjen', 'sesditjen_dirjen', 'surat_eksternal').
        data: JSON string berisi payload data naskah (hal, yth, dari, tanggal_nd, dll).
        output_filename: Nama file output opsional (contoh: 'ND_Laporan.docx').
    """
    import json
    from .naskah_dinas_generator import satria_naskah_generator
    
    try:
        payload = json.loads(data)
        out = ""
        if jenis_naskah == "laporan":
            out = satria_naskah_generator.generate_nd_laporan(payload, output_filename)
        elif jenis_naskah == "pengantar_sesditjen":
            out = satria_naskah_generator.generate_nd_pengantar(payload, output_filename)
        elif jenis_naskah == "sesditjen_dirjen":
            out = satria_naskah_generator.generate_nd_sesditjen_ke_dirjen(payload, output_filename)
        elif jenis_naskah == "surat_eksternal":
            out = satria_naskah_generator.generate_surat_dinas_eksternal(payload, output_filename)
        else:
            return f"Jenis naskah '{jenis_naskah}' tidak didukung."
        return f"Sukses! Draft naskah dinas berhasil di-generate di: {out}"
    except Exception as e:
        return f"Gagal generate naskah dinas: {e}"

async def search_web_realtime(
    ctx: Context,
    query: str,
    max_results: int = 3
) -> str:
    """
    Melakukan pencarian internet dan portal web resmi pemerintah secara live menggunakan Tri-Engine Hybrid Search.
    
    Args:
        query: Kata kunci pencarian internet atau nomor regulasi.
        max_results: Jumlah maksimum hasil (default: 3).
    """
    try:
        from core.browser.hybrid_search import hybrid_search_engine
        res = await hybrid_search_engine.search(query=query, max_results=max_results)
        if not res.get("success") or not res.get("results"):
            return f"Tidak ditemukan hasil pencarian web resmi untuk '{query}'."

        engine = res.get("engine_used", "hybrid").upper()
        res_text = f"HASIL PENELUSURAN DOKUMEN & WEB RESMI (ENGINE: {engine}):\n"
        for r in res.get("results", []):
            res_text += f"- Judul: {r.get('title')}\n  Ringkasan: {r.get('snippet')}\n  Tautan: {r.get('url')}\n\n"
        return res_text.strip()
    except Exception as e:
        return f"Pencarian web mengalami gangguan sementara: {e}"
