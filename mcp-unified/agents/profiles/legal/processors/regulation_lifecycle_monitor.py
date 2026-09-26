"""
regulation_lifecycle_monitor.py — Regulation Lifecycle & Transitional Deadline Monitor.
Mendeteksi batas masa transisi/kedaluwarsa regulasi dan menjadwalkan audit berkala via MCP Scheduler.
"""

import re
import datetime
from typing import Dict, Any, List, Optional


def extract_transitional_deadlines(
    regulation_text: str,
    regulation_title: Optional[str] = None,
    base_date_str: Optional[str] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Mem-parsing tanggal-tanggal batas transisi, batas penyaluran, dan masa berlaku dari naskah regulasi.
    """

    deadlines = []

    # 1. Pola tanggal transisi spesifik (mis. 31 Desember 2026)
    m_transisi = re.search(
        r'(?:masa transisi|berlaku sampai|paling lambat|tenggat waktu)[^\n\.\;]*?(\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4})',
        regulation_text,
        re.IGNORECASE,
    )
    if m_transisi:
        deadlines.append({
            "tipe": "TRANSISI_REGULASI",
            "tanggal_target": m_transisi.group(1),
            "konteks": m_transisi.group(0).strip(),
            "saran_tindakan": "Evaluasi kepatuhan transisi dan kesiapan pelaku usaha 30 hari sebelum tenggat.",
        })

    # 2. Pola batas verifikasi bulanan (mis. tanggal 15, 20, atau 25 setiap bulan)
    m_rutin = re.findall(
        r'(?:paling lambat tanggal|sebelum tanggal)\s+(\d{1,2})\s+(?:setiap bulan|bulan berjalan)',
        regulation_text,
        re.IGNORECASE,
    )
    for tgl in set(m_rutin):
        deadlines.append({
            "tipe": "SIKLUS_RUTIN_BULANAN",
            "tanggal_target": f"Tanggal {tgl} setiap bulan",
            "konteks": f"Batas waktu penyampaian dokumen / verifikasi bulanan (tgl {tgl})",
            "saran_tindakan": f"Pemicu rekonsiliasi otomatis SIP-DADES setiap tanggal {tgl}.",
        })

    # 3. Pola Tahun Anggaran (TA 2026)
    m_ta = re.search(r'Tahun Anggaran\s+(\d{4})', regulation_text, re.IGNORECASE)
    if m_ta:
        tahun = m_ta.group(1)
        deadlines.append({
            "tipe": "AKHIR_TAHUN_ANGGARAN",
            "tanggal_target": f"31 Desember {tahun}",
            "konteks": f"Masa laku keuangan Tahun Anggaran {tahun}",
            "saran_tindakan": f"Audit akhir tahun realisasi penggunaan anggaran dan sisa pagu TA {tahun}.",
        })

    return deadlines


def schedule_lifecycle_alerts(deadlines: List[Dict[str, Any]], regulation_title: str) -> Dict[str, Any]:
    """
    Menghasilkan spesifikasi jadwal monitoring untuk didaftarkan ke MCP Scheduler / Cron Registry.
    """
    scheduled_jobs = []
    for d in deadlines:
        job = {
            "nama_job": f"Lifecycle_Monitor_{d['tipe']}_{regulation_title[:25]}".replace(" ", "_"),
            "target_deadline": d["tanggal_target"],
            "keterangan": d["konteks"],
            "rekomendasi_cron": "0 8 1 * *" if d["tipe"] == "SIKLUS_RUTIN_BULANAN" else "0 8 1 11 *",
            "status": "READY_TO_SCHEDULE",
        }
        scheduled_jobs.append(job)

    return {
        "regulation_title": regulation_title,
        "total_monitored_events": len(deadlines),
        "scheduled_jobs": scheduled_jobs,
    }
