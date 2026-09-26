"""
dimension_router_node.py
=========================
Reasoning Graph & Multi-Pass Dimension Router untuk Legal Agent.
- Membaca Doctrine Memory & Precedent Memory (YAML).
- Two-Pass Routing: Pass 1 (Dimensi Primer), Pass 2 (Uji Konstitusional jika terpicu dependensi).
- Precedent Matching via faktor_kunci & distinguishing_note (Analogical Reasoning).
- Cross-Dimension Consistency Evaluation & Narrative Synthesis.
- Async Orchestrator (Bisa dijalankan standalone ataupun via LangGraph).
"""

from __future__ import annotations

import os
import re
import yaml
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

from .dimension_analysis_impl import run_dimension_analysis

logger = logging.getLogger("mcp-unified.legal.dimension_router")

CONFIG_DIR = Path(__file__).parent.parent / "config"
DOCTRINE_PATH = CONFIG_DIR / "doctrine_memory.yaml"
PRECEDENT_PATH = CONFIG_DIR / "precedent_memory.yaml"


# ─────────────────────────────────────────────────────────────
# 1. LOAD CONFIG DOCTRINE & PRECEDENT
# ─────────────────────────────────────────────────────────────

def load_doctrine_memory(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    p = path or DOCTRINE_PATH
    if not p.exists():
        logger.warning(f"File doctrine {p} tidak ditemukan, menggunakan fallback kosong.")
        return []
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data.get("doctrine_memory", [])


def load_precedent_memory(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    p = path or PRECEDENT_PATH
    if not p.exists():
        logger.warning(f"File precedent {p} tidak ditemukan, menggunakan fallback kosong.")
        return []
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data.get("precedent_memory", [])


# ─────────────────────────────────────────────────────────────
# 2. KLASIFIKASI REGULASI (METADATA & FLAG EKSTRAKSI)
# ─────────────────────────────────────────────────────────────

def classify_regulation_metadata(text_or_title: str, explicit_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Menganalisis teks/judul regulasi untuk menghasilkan flag klasifikasi
    yang diperlukan oleh trigger_conditions doktrin.
    """
    meta = explicit_meta.copy() if explicit_meta else {}
    sample = text_or_title.lower()

    # 1. Cek Hierarki PUU (di bawah UU atau setingkat UU)
    is_uu = bool(re.search(r"\bundang[- ]undang\b|\buu\b|\buud\b", sample) and not re.search(r"\bperaturan pemerintah\b|\bpp\b|\bperpres\b|\bpermen\b|\bperda\b", sample))
    meta.setdefault("regulasi_di_bawah_UU", not is_uu)

    # 2. Status Keberlakuan
    meta.setdefault("regulasi_sudah_berlaku", True)
    meta.setdefault("regulasi_sudah_berlaku_minimal_beberapa_bulan", True)

    # 3. Masa Transisi Pendek
    has_transition = bool(re.search(r"transisi|tenggat|penyesuaian|bulan|desember|januari", sample))
    meta.setdefault("masa_transisi_pendek", has_transition)
    meta.setdefault("ATAU_ada_masa_transisi_pendek_yang_perlu_dinilai_risikonya", has_transition)

    # 4. Dampak Ekonomi & Restrukturisasi Pasar
    has_economic = bool(re.search(r"ekspor|impor|bumn|pasar|komoditas|tambang|sawit|minerba|tarif|retribusi|pajak|anggaran", sample))
    meta.setdefault("regulasi_berdampak_ekonomi_signifikan", has_economic)
    meta.setdefault("dampak_ekonomi_signifikan", has_economic)
    meta.setdefault("ada_isu_deregulasi_atau_restrukturisasi_pasar", has_economic)
    meta.setdefault("ATAU_ada_isu_deregulasi_atau_restrukturisasi_pasar", has_economic)

    return meta


# ─────────────────────────────────────────────────────────────
# 3. TRIGGER CONDITIONS EVALUATOR
# ─────────────────────────────────────────────────────────────

def evaluate_trigger(trigger_conditions: List[Dict[str, Any]] | Dict[str, Any], meta: Dict[str, Any], findings: Dict[str, Any]) -> bool:
    """Evaluasi kondisi trigger doktrin terhadap metadata dan findings saat ini."""
    if isinstance(trigger_conditions, list):
        # Gabungkan list dict menjadi satu dict
        merged = {}
        for item in trigger_conditions:
            if isinstance(item, dict):
                merged.update(item)
        trigger_conditions = merged

    if not isinstance(trigger_conditions, dict):
        return True

    if trigger_conditions.get("selalu_relevan"):
        return True

    # Cek dependensi khusus dimensi konstitusional
    if "indikator_lemah_normatif_mengandung_materi_melampaui_delegasi" in trigger_conditions:
        normatif = findings.get("normatif_akademik", {})
        lemah = normatif.get("indikator_lemah", [])
        if "materi_muatan_tampak_melampaui_cakupan_delegasi_UU_induk" not in lemah:
            return False

    # AND conditions
    and_conditions = {k: v for k, v in trigger_conditions.items() if not k.startswith("ATAU_") and k not in ["selalu_relevan", "indikator_lemah_normatif_mengandung_materi_melampaui_delegasi"]}
    and_pass = all(meta.get(k, False) == v for k, v in and_conditions.items())

    # OR conditions
    or_conditions = {k: v for k, v in trigger_conditions.items() if k.startswith("ATAU_")}
    or_pass = True
    if or_conditions:
        or_pass = any(meta.get(k, False) == v or meta.get(k.replace("ATAU_", ""), False) == v for k, v in or_conditions.items())

    return and_pass and or_pass


# ─────────────────────────────────────────────────────────────
# 4. PRECEDENT RETRIEVAL & OVERLAP SCORING
# ─────────────────────────────────────────────────────────────

def _faktor_overlap_score(faktor_kunci: Dict[str, Any], indikator_lemah: List[str]) -> int:
    score = 0
    for factor_name, is_true in faktor_kunci.items():
        if is_true and any(factor_name.lower() in ind.lower() for ind in indikator_lemah):
            score += 2
        elif not is_true and any("tanpa" in ind.lower() or "tidak" in ind.lower() for ind in indikator_lemah):
            score += 1
    return score


def retrieve_precedent(relevan_untuk_dimension: str, indikator_lemah: List[str]) -> List[Dict[str, Any]]:
    precedents = load_precedent_memory()
    candidates = [p for p in precedents if p.get("relevan_untuk_dimension") == relevan_untuk_dimension]
    if not candidates:
        return []

    ranked = sorted(
        candidates,
        key=lambda p: _faktor_overlap_score(p.get("faktor_kunci", {}), indikator_lemah),
        reverse=True,
    )
    return ranked[:2]


# ─────────────────────────────────────────────────────────────
# 5. CROSS-DIMENSION CONSISTENCY & SYNTHESIS
# ─────────────────────────────────────────────────────────────

def evaluate_cross_dimension_consistency(findings: Dict[str, Any]) -> List[str]:
    """Mendeteksi pola korelasi temuan antar dimensi."""
    notes = []
    filosofis = findings.get("filosofis", {})
    sosiologis = findings.get("sosiologis", {})
    ekonomi = findings.get("ekonomi_kebijakan", {})
    normatif = findings.get("normatif_akademik", {})
    konstitusional = findings.get("konstitusional", {})

    # Pola 1: Filosofi Kuat tapi Implementasi / Kesiapan Lapangan Lemah
    if filosofis.get("lulus") and (not sosiologis.get("lulus", True) or not ekonomi.get("lulus", True)):
        notes.append(
            "⚠️ **Pola Filosofi Kuat vs Implementasi Rentan:** "
            "Tujuan pembaharuan sosial/ekonomi dirumuskan sangat jelas, tetapi kesiapan pelaksana, "
            "waktu transisi, atau dukungan data ekonomi (RIA) sangat minim/rapuh."
        )

    # Pola 2: Indikasi Ultra Vires pada Dimensi Normatif & Konstitusional
    normatif_lemah = normatif.get("indikator_lemah", [])
    if "materi_muatan_tampak_melampaui_cakupan_delegasi_UU_induk" in normatif_lemah:
        notes.append(
            "🔴 **Pola Cacat Delegasi (Potensi Ultra Vires):** "
            "Materi muatan peraturan turunan menciptakan mekanisme baru di luar mandat eksplisit UU induk. "
            "Berpotensi kuat diajukan Hak Uji Materiil (HUM) ke Mahkamah Agung."
        )

        # Cek Kontradiksi Antar-Dimensi: Normatif mendeteksi cacat delegasi tapi Konstitusional menyatakan lulus/sah
        konst_lemah = konstitusional.get("indikator_lemah", [])
        konst_lulus = konstitusional.get("lulus", False)
        if konstitusional and (konst_lulus or "delegasi_bersifat_umum_tanpa_perintah_substantif_spesifik" not in konst_lemah):
            notes.append(
                "⚠️ **KONTRADIKSI TEMUAN ANTAR-DIMENSI (DISCREPANCY DETECTED):** "
                "Dimensi Normatif-Akademik mendeteksi indikator 'materi_muatan_tampak_melampaui_cakupan_delegasi_UU_induk', "
                "namun Dimensi Konstitusional menyimpulkan delegasi masih dalam batas wewenang. "
                "Inkonsistensi ini menunjukkan zona sengketa yudisial tinggi (*contentious gray area*) "
                "antara doktrin kepatuhan delegasi ketat (ultra vires) vs doktrin diskresi regulasi ekonomi."
            )

    # Pola 3: Kekosongan Definisi / Regulasi Turunan Menggantung
    if "istilah_kunci_tidak_didefinisikan_di_ketentuan_umum" in normatif_lemah or "banyak_ketentuan_lebih_lanjut_didelegasikan_ke_peraturan_turunan_yang_belum_terbit" in normatif_lemah:
        notes.append(
            "⚠️ **Pola Ketidakpastian Regulasi Menggantung:** "
            "Terdapat istilah kunci multitafsir atau ketergantungan masif pada regulasi pelaksana yang belum terbit."
        )

    return notes


def build_narrative_synthesis(
    regulation_title: str,
    findings: Dict[str, Any],
    cross_notes: List[str],
    precedent_matches: Dict[str, List[Dict[str, Any]]],
) -> str:
    """Menyusun sintesis naratif yuridis komprehensif berdasarkan 6 Dimensi."""
    lines = [
        f"# ⚖️ Laporan Hasil Uji Doktrin Multi-Dimensi: {regulation_title}",
        "",
        "## 📊 Rekapitulasi Penilaian Dimensi",
        "| Dimensi Doktrin | Status | Temuan Kunci / Indikator Lemah |",
        "|---|---|---|",
    ]

    for dim_id, res in findings.items():
        nama = res.get("nama", dim_id)
        is_lulus = res.get("lulus", False)
        ind_list = res.get("indikator_lemah", [])
        
        # Nuansa status untuk dimensi threshold-based vs zero-tolerance
        if is_lulus and ind_list:
            status = f"✅ LULUS (Catatan: {len(ind_list)} catatan minor)"
        elif is_lulus:
            status = "✅ LULUS"
        else:
            status = "⚠️ PERHATIAN / LEMAH"

        indikator = ", ".join(ind_list) or "Tidak ada indikator lemah signifikan"
        lines.append(f"| **{nama}** | {status} | {indikator} |")

    lines.append("")

    if cross_notes:
        lines.append("## 🔍 Analisis Konsistensi Lintas Dimensi (Cross-Dimension Findings)")
        for note in cross_notes:
            lines.append(f"- {note}")
        lines.append("")

    # Preseden Terkait
    has_precedent = False
    precedent_lines = ["## 📚 Preseden & Komparasi Putusan Hukum (Analogical Precedents)"]
    for dim_id, precs in precedent_matches.items():
        for p in precs:
            has_precedent = True
            core_reasoning = p.get("ratio_decidendi") or p.get("temuan_inti") or ""
            forum_str = f"{p.get('forum')}" + (f", {p.get('tahun')}" if p.get("tahun") else "")
            precedent_lines.append(
                f"- **{p.get('nama_kasus')} ({forum_str}):**\n"
                f"  - *Temuan / Ratio Decidendi:* {core_reasoning.strip()}\n"
                f"  - *Distinguishing Note:* {p.get('distinguishing_note', '').strip()}"
            )
    if has_precedent:
        lines.extend(precedent_lines)
        lines.append("")

    # Kesimpulan & Rekomendasi
    lines.append("## 🎯 Kesimpulan & Rekomendasi Yuridis")
    has_fatal_ultra_vires = any("Ultra Vires" in note for note in cross_notes)
    if has_fatal_ultra_vires:
        rekomendasi = "**REVISI MATERIIL / PEMANTAUAN KETAT RISIKO GUGATAN:**\nPeraturan ini memiliki risiko yudisial tinggi karena melampaui bunyi delegasi UU induk. Disarankan segera menyempurnakan pasal delegasi atau menyiapkan landasan UU yang lebih eksplisit."
    elif any("Implementasi Rentan" in note for note in cross_notes):
        rekomendasi = "**PERPANJANGAN MASA TRANSISI & PERCEPATAN REGULASI PELAKSANA:**\nFilosofi regulasi sangat baik, tetapi perlu mitigasi kesiapan pelaku usaha dan penerbitan segera petunjuk teknis/SOP pelaksana."
    else:
        rekomendasi = "**DIPERTAHANKAN:**\nRegulasi memiliki koherensi doktrinal, formil, materiil, dan kesiapan operasional yang memadai."

    lines.append(rekomendasi)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# 6. ASYNC ORCHESTRATOR UTAMA
# ─────────────────────────────────────────────────────────────

async def run_multidimensional_analysis(
    regulation_text_or_ref: str,
    regulation_title: str = "Regulasi Teruji",
    metadata_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Eksekutor Utama Two-Pass Reasoning Graph dengan Auto-Ingestion Dokumen (PDF/OCR/Teks).
    """
    from agents.profiles.legal.processors.document_ingestion import load_regulation_text
    resolved_text = load_regulation_text(regulation_text_or_ref)

    meta = classify_regulation_metadata(resolved_text, metadata_override)
    doctrine_list = load_doctrine_memory()

    findings: Dict[str, Any] = {}
    precedent_matches: Dict[str, List[Dict[str, Any]]] = {}

    # ── PASS 1: Dimensi Primer (Semua dimensi non-konstitusional yang lolos trigger) ──
    pass_1_tasks = []
    pass_1_dims = []

    for dim in doctrine_list:
        dim_id = dim["dimension_id"]
        if dim_id == "konstitusional":
            continue  # Konstitusional ditahan hingga Pass 2

        if evaluate_trigger(dim.get("trigger_conditions", {}), meta, findings):
            pass_1_dims.append(dim)
            pass_1_tasks.append(run_dimension_analysis(dim, resolved_text))

    # Eksekusi paralel Pass 1
    if pass_1_tasks:
        results_pass_1 = await asyncio.gather(*pass_1_tasks)
        for dim_res in results_pass_1:
            dim_id = dim_res["dimension_id"]
            findings[dim_id] = dim_res
            # Re-rank preseden berdasarkan indikator lemah aktual yang ditemukan
            dim_lemah = dim_res.get("indikator_lemah", [])
            if dim_lemah:
                precs = retrieve_precedent(dim_id, dim_lemah)
                if precs:
                    precedent_matches[dim_id] = precs

    # ── PASS 2: Evaluasi Dependensi & Dimensi Konstitusional ──
    cross_notes = evaluate_cross_dimension_consistency(findings)

    # Cek apakah Dimensi Konstitusional perlu dijalankan
    konstitusional_dim = next((d for d in doctrine_list if d["dimension_id"] == "konstitusional"), None)
    if konstitusional_dim and evaluate_trigger(konstitusional_dim.get("trigger_conditions", {}), meta, findings):
        normatif_data = findings.get("normatif_akademik", {})
        normatif_lemah = normatif_data.get("indikator_lemah", [])
        precs = retrieve_precedent("konstitusional", normatif_lemah)
        precedent_matches["konstitusional"] = precs

        # Teruskan hasil temuan normatif sebagai konteks uji ke dimensi konstitusional
        prior_findings_ctx = {"normatif_akademik": normatif_data}
        res_konst = await run_dimension_analysis(
            konstitusional_dim,
            resolved_text,
            precedents=precs,
            prior_findings=prior_findings_ctx,
        )
        findings["konstitusional"] = res_konst

        # Re-evaluasi cross notes dengan adanya data konstitusional lengkap
        cross_notes = evaluate_cross_dimension_consistency(findings)

    # ── SINTESIS AKHIR & INTEGRASI EKOSISTEM TOOLS (TASK-128) ──
    final_synthesis = build_narrative_synthesis(regulation_title, findings, cross_notes, precedent_matches)

    # 1. Visualisasi Radar Chart & Policy Brief Canvas (Subtask 128-B)
    from .doctrine_visualizer import calculate_dimension_scores, generate_svg_radar_chart, generate_policy_brief_canvas
    scores = calculate_dimension_scores(findings)
    svg_chart = generate_svg_radar_chart(scores, title=f"Profil Doktrin: {regulation_title[:40]}")
    
    slug = re.sub(r'[^a-zA-Z0-9_]+', '_', regulation_title[:30]).lower()
    report_html_path = Path("/home/aseps/MCP/storage/reports") / f"policy_brief_{slug}.html"
    generate_policy_brief_canvas({"dimension_findings": findings, "cross_dimension_notes": cross_notes, "final_synthesis": final_synthesis}, regulation_title, output_html_path=report_html_path)

    # 2. Historical Correspondence Alignment (Subtask 128-D)
    from .correspondence_verifier import find_related_correspondence
    topic_keys = [regulation_title, meta.get("jurisdiction", "")]
    related_correspondence = find_related_correspondence(topic_keys)

    # 3. Regulation Lifecycle & Transitional Deadline Monitor (Subtask 128-E)
    from .regulation_lifecycle_monitor import extract_transitional_deadlines, schedule_lifecycle_alerts
    deadlines = extract_transitional_deadlines(resolved_text)
    lifecycle_schedule = schedule_lifecycle_alerts(deadlines, regulation_title)

    # 4. WhatsApp High-Risk Legal Alert (Subtask 128-F)
    from .legal_alert_dispatcher import should_trigger_red_alert, format_whatsapp_red_alert
    is_red_alert = should_trigger_red_alert({"dimension_findings": findings})
    red_alert_msg = format_whatsapp_red_alert(regulation_title, {"dimension_findings": findings, "cross_dimension_notes": cross_notes}) if is_red_alert else ""

    # 5. Policy-as-Code Alignment (Subtask 128-G)
    from .policy_as_code_verifier import extract_regulatory_formulas, verify_code_alignment
    reg_formulas = extract_regulatory_formulas(resolved_text)
    policy_code_alignment = verify_code_alignment(reg_formulas)

    return {
        "success": True,
        "regulation_title": regulation_title,
        "metadata": meta,
        "dimension_findings": findings,
        "dimension_scores": scores,
        "cross_dimension_notes": cross_notes,
        "precedent_matches": precedent_matches,
        "final_synthesis": final_synthesis,
        "visual_radar_svg": svg_chart,
        "policy_brief_html_path": str(report_html_path),
        "related_correspondence": related_correspondence,
        "lifecycle_deadlines": deadlines,
        "lifecycle_schedule": lifecycle_schedule,
        "is_red_alert_triggered": is_red_alert,
        "red_alert_preview": red_alert_msg[:400] if is_red_alert else "Aman (Risiko Normal)",
        "policy_as_code_alignment": policy_code_alignment,
    }

