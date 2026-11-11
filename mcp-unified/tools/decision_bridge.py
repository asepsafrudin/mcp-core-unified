"""
Decision Bridge Tool for MCP Unified Hub.
Bridges the JEV / SemIf Decision Engine into the MCP Unified tools registry.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base import register_tool

logger = logging.getLogger(__name__)

SERVER_HUMAN_DESCRIPTIONS: Dict[str, str] = {
    "core": "Operasi Berkas, Shell, Sistem, dan Perintah Dasar",
    "memory": "Simpan / Ambil Fakta ke Memori Jangka Panjang (LTM)",
    "knowledge": "Pencarian Semantik & Pengindeksan Dokumen RAG",
    "skills": "Pencarian atau Pendaftaran Prosedur / Skill Agen",
    "document": "Ekstraksi PDF, OCR Scan, dan Pengolahan Naskah",
    "bridge": "Integrasi Eksternal (Email, Telegram, WhatsApp, Jaringan)",
}


@register_tool
def decision_triage(task: str) -> Dict[str, Any]:
    """
    Triage, klasifikasi maksud, dan routing tugas menggunakan engine JEV/SemIf Decision Server.

    Mengembalikan:
      - target_server: Server tujuan modular (core, memory, knowledge, document, skills, bridge)
      - confidence: Skor keyakinan ML (0.0 - 1.0)
      - explanation_terms: Istilah bukti berbobot (TF-IDF coefficients) yang mendasari keputusan
      - risk_level: Tingkat risiko deterministik (low, medium, high, critical)
      - priority_score: Skor prioritas (0 - 100) dan band (P0-P4)
      - fallback_chain: Rantai server cadangan jika server utama tidak aktif
      - requires_human_review: Eskalasi otomatis jika berisiko kritis atau berkeyakinan rendah
    """
    if not task or not task.strip():
        return {"success": False, "error": "Task description cannot be empty"}

    try:
        from servers.decision.ml import classifier
        return classifier.classify(task)
    except Exception as exc:
        logger.warning("decision_triage in-process failed: %s; trying HTTP :8009", exc)
        try:
            import json
            import urllib.request
            req = urllib.request.Request(
                "http://127.0.0.1:8009/tools/call",
                data=json.dumps({"tool": "decision_classify", "payload": {"task": task}}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("data") or data
        except Exception as http_exc:
            return {
                "success": False,
                "error": f"Failed to triage task: in-process error ({exc}), http error ({http_exc})",
            }


@register_tool
def decision_status() -> Dict[str, Any]:
    """
    Memeriksa kesehatan dan metadata model JEV/SemIf Decision Engine.
    Menampilkan identitas model, versi, cross-validated accuracy, dan waktu inferensi.
    """
    try:
        from servers.decision.ml import classifier
        return {"success": True, **classifier.model_status()}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@register_tool
def decision_hitl_choice(task: str) -> Dict[str, Any]:
    """
    Mengonversi analisis JEV menjadi format Decision Choice siap pakai untuk Human-in-the-Loop (HITL).

    Cocok langsung dimasukkan ke parameter UI `ask_question` (options pilihan berganda)
    atau disajikan ke Web Dashboard sebagai decision matrix terstruktur.
    """
    if not task or not task.strip():
        return {"success": False, "error": "Task description cannot be empty"}

    triage = decision_triage(task)
    if not triage.get("success"):
        return triage

    routing = triage.get("routing", {})
    target = routing.get("target_server", "core")
    confidence_pct = routing.get("confidence_percent", 0.0)
    low_confidence = routing.get("low_confidence", False)
    risk = triage.get("risk_level", "low")
    risk_reasons = triage.get("risk_reasons", [])
    requires_review = triage.get("requires_human_review", False)
    top_candidates = routing.get("top_candidates", [])

    task_snippet = task.strip()
    if len(task_snippet) > 60:
        task_snippet = task_snippet[:57] + "..."

    if risk == "critical":
        reasons_text = ", ".join(risk_reasons) if risk_reasons else "risiko destruktif"
        question = (
            f"Tindakan '{task_snippet}' terdeteksi berisiko KRITIS ({reasons_text}). "
            "Pilih opsi konfirmasi:"
        )
    elif low_confidence:
        question = (
            f"Maksud tugas '{task_snippet}' memiliki ambiguitas (confidence {confidence_pct}%). "
            "Pilih tujuan pemrosesan yang dimaksud:"
        )
    else:
        question = (
            f"Konfirmasi pemrosesan tugas '{task_snippet}' ke server {target.upper()} "
            f"(confidence {confidence_pct}%):"
        )

    options: List[str] = []
    decision_matrix: List[Dict[str, Any]] = []

    for idx, cand in enumerate(top_candidates):
        srv = cand.get("server", "")
        prob = round(cand.get("probability", 0.0) * 100, 1)
        desc = SERVER_HUMAN_DESCRIPTIONS.get(srv, f"Layanan {srv}")
        prefix = "(Recommended) " if idx == 0 else ""
        opt_text = f"{prefix}{desc} [{srv.upper()} - {prob}%]"
        options.append(opt_text)

        decision_matrix.append({
            "choice_id": f"choice_{srv}",
            "server": srv,
            "label": desc,
            "probability_percent": prob,
            "is_recommended": (idx == 0),
        })

    options.append("Ketik klarifikasi atau instruksi yang lebih spesifik secara manual")

    return {
        "success": True,
        "hitl_required": requires_review,
        "task": task,
        "question": question,
        "options": options,
        "is_multi_select": False,
        "top_candidates": top_candidates,
        "decision_matrix": decision_matrix,
        "risk_level": risk,
        "priority_band": triage.get("priority_band", "P3-low"),
        "review_reasons": triage.get("review_reasons", []),
    }


