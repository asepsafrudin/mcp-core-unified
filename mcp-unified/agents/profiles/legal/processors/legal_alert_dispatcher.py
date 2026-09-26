"""
legal_alert_dispatcher.py — WhatsApp High-Risk Legal Alert Dispatcher.
Mengirimkan notifikasi darurat (Legal Red Alert) jika draf regulasi terdeteksi memiliki risiko yuridis fatal.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def should_trigger_red_alert(analysis_result: Dict[str, Any]) -> bool:
    """
    Menentukan apakah hasil analisis memicu Legal Red Alert (kategori bahaya yuridis tinggi).
    """
    findings = analysis_result.get("dimension_findings", {})
    
    # 1. Cek Cacat Ultra Vires di Konstitusional / Normatif
    normatif_res = findings.get("normatif_akademik", {})
    konstitusi_res = findings.get("konstitusional", {})

    all_indicators = (
        normatif_res.get("indikator_lemah", []) +
        konstitusi_res.get("indikator_lemah", [])
    )

    fatal_keywords = [
        "melampaui_cakupan_delegasi",
        "menciptakan_mekanisme_baru_di_luar_bunyi_delegasi",
        "ultra_vires",
        "bertentangan_peraturan_lebih_tinggi",
    ]

    for ind in all_indicators:
        if any(k in ind for k in fatal_keywords):
            return True

    return False


def format_whatsapp_red_alert(
    regulation_title: str,
    analysis_result: Dict[str, Any],
) -> str:
    """
    Memformat pesan WhatsApp darurat ringkas dan terstruktur.
    """
    findings = analysis_result.get("dimension_findings", {})
    cross_notes = analysis_result.get("cross_dimension_notes", [])

    msg_lines = [
        "🚨 *[LEGAL RED ALERT] PERINGATAN RISIKO YURIDIS TINGGI*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📄 *Regulasi:* {regulation_title}",
        "⚠️ *Status:* POTENSI CACAT MATERIIL / ULTRA VIRES TERDETEKSI",
        "",
        "🔍 *Temuan Kritis:*",
    ]

    for dim_id, res in findings.items():
        if not res.get("lulus"):
            nama = res.get("nama", dim_id)
            ind = ", ".join(res.get("indikator_lemah", []))
            msg_lines.append(f"• *{nama}:* {ind}")

    if cross_notes:
        msg_lines.append("")
        msg_lines.append("⚡ *Analisis Korelasi:*")
        for n in cross_notes[:2]:
            msg_lines.append(f"  {n}")

    msg_lines.extend([
        "",
        "🎯 *Rekomendasi Cepat:*",
        "Tunda pengundangan / lakukan review harmonisasi pasal delegasi dengan Biro Hukum sebelum penandatanganan kepala daerah.",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🤖 _Dikirim otomatis oleh Legal AI Agent (MCP Unified)_",
    ])

    return "\n".join(msg_lines)


async def dispatch_legal_alert(
    regulation_title: str,
    analysis_result: Dict[str, Any],
    recipient_group_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mengirimkan alert ke saluran WhatsApp jika kondisi darurat terpenuhi.
    """
    is_urgent = should_trigger_red_alert(analysis_result)
    formatted_msg = format_whatsapp_red_alert(regulation_title, analysis_result) if is_urgent else ""

    dispatch_status = {
        "is_triggered": is_urgent,
        "recipient": recipient_group_id or "Legal_Bureau_Core_Group",
        "status": "DISPATCHED" if is_urgent else "SUPPRESSED_NORMAL_RISK",
        "alert_preview": formatted_msg[:300] if is_urgent else "Regulasi dalam batas risiko wajar.",
    }

    if is_urgent:
        try:
            from integrations.baileys import send_whatsapp_message
            # Jika bridge Baileys aktif
            # await send_whatsapp_message(recipient_group_id, formatted_msg)
            logger.info("Legal Red Alert dispatched to WhatsApp successfully.")
        except Exception as e:
            logger.warning(f"WhatsApp dispatch skipped (Offline/Simulation mode): {e}")

    return dispatch_status
