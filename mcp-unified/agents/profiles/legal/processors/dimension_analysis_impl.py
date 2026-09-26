"""
dimension_analysis_impl.py
===========================
Implementasi eksekusi evaluasi per-dimensi hukum berbasis Doctrine Memory.
- Dynamic prompt builder dari struktur YAML doktrin.
- Multi-provider LLM executor (Groq / Anthropic / OpenAI / RunPod / Ollama) via LLMConnector / VaneConnector.
- JSON output parsing yang aman & regex fallback.
- Validasi vocabulary ketat terhadap indikator_lemah untuk mencegah rusaknya trigger state machine antar-node.
"""

from __future__ import annotations

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

# Auto-load MCP environment secrets
try:
    from scripts.load_env import load_env
    load_env(verbose=False)
except Exception:
    pass

logger = logging.getLogger("mcp-unified.legal.dimension_analysis")

# Import Connectors
try:
    from ..connectors.llm_connector import LLMConnector
except ImportError:
    from agents.profiles.legal.connectors.llm_connector import LLMConnector

try:
    from ..connectors.agent_knowledge_bridge import get_knowledge_bridge
except ImportError:
    try:
        from agents.profiles.legal.connectors.agent_knowledge_bridge import get_knowledge_bridge
    except ImportError:
        get_knowledge_bridge = None


# ─────────────────────────────────────────────────────────────
# 1. PROMPT TEMPLATE DINAMIS
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """Anda adalah Analis Hukum Senior di legal-agent MCP Unified yang menguji produk hukum \
Indonesia memakai kerangka doktrin hukum baku. Anda HANYA menjalankan SATU dimensi \
uji dalam panggilan ini — fokus penuh pada dimensi yang ditugaskan.

## Dimensi yang Diuji: {nama}
- Sumber Pemikiran: {sumber}
- Sifat Analisis: {sifat}
- Pertanyaan Kunci: {pertanyaan_kunci}

## Pertanyaan Uji yang WAJIB Dijawab Satu per Satu:
{pertanyaan_uji_list}

## Fakta yang Harus Anda Cari & Rujuk di Teks Regulasi:
{fakta_dibutuhkan_list}

## Preseden Terkait (Jika Ada):
{precedent_context}

## TEMUAN DARI DIMENSI SEBELUMNYA (PRIOR FINDINGS):
{prior_findings_context}

## VOCABULARY INDIKATOR LEMAH YANG TERDAFTAR UNTUK DIMENSI INI
Anda HANYA boleh memilih nilai untuk "indikator_lemah" dari daftar baku berikut.
JANGAN membuat istilah baru di luar daftar ini! Jika ada temuan kritis lain di luar daftar,
tuliskan di dalam field "catatan_tambahan".

{indikator_lemah_vocabulary}

## Definisi Lulus untuk Dimensi Ini:
{indikator_lulus}

## ATURAN KOHERENSI INTERNAL (WAJIB DIPATUHI):
- Nilai status "lulus" dan pemilihan "indikator_lemah" WAJIB 100% konsisten dengan uraian "jawaban_per_pertanyaan".
- JANGAN memilih indikator lemah yang bertentangan langsung dengan isi jawaban Anda sendiri.
- Khususnya: Jika jawaban Anda menyatakan regulasi bersifat mengarahkan (rekayasa sosial) dan memiliki arah kebijakan substantif yang jelas, maka status "lulus" WAJIB true dan DILARANG memilih indikator "tujuan_hanya_administratif_tanpa_arah_perubahan_jelas".

## Format Output — WAJIB JSON MURNI (Valid JSON, tanpa markdown codeblock ```json):
{{
  "jawaban_per_pertanyaan": [
    {{
      "pertanyaan": "<salin persis salah satu pertanyaan_uji di atas>",
      "jawaban": "<jawaban mendalam berbasis fakta norma, bukan asumsi>",
      "fakta_dikutip": "<kutip bagian pasal/konsiderans spesifik yang menjadi dasar>"
    }}
  ],
  "indikator_lemah": ["<hanya dari vocabulary terdaftar di atas, kosongkan [] jika tidak ada>"],
  "lulus": true,
  "catatan_tambahan": "<opsional, catatan temuan kritis atau fakta di luar vocabulary baku>"
}}
"""


def _build_system_prompt(
    doctrine_entry: Dict[str, Any],
    precedents: Optional[List[Dict[str, Any]]] = None,
    prior_findings: Optional[Dict[str, Any]] = None,
) -> str:
    """Membangun system prompt dinamis dari entri doktrin YAML."""
    pertanyaan_uji = doctrine_entry.get("pertanyaan_uji", [])
    if not pertanyaan_uji and "faktor" not in doctrine_entry:
        raise ValueError(
            f"SCHEMA ERROR: Doktrin '{doctrine_entry.get('dimension_id')}' wajib mendefinisikan 'pertanyaan_uji' eksplisit!"
        )

    pertanyaan_list = "\n".join(
        f"{i+1}. {q}" for i, q in enumerate(pertanyaan_uji)
    )

    if "fakta_dibutuhkan" in doctrine_entry:
        fakta_list = "\n".join(f"- {f}" for f in doctrine_entry["fakta_dibutuhkan"])
    elif "faktor" in doctrine_entry:
        fakta_list = "\n".join(
            f"- [{f['id']}] {f.get('pertanyaan', '')} (Fakta: {f.get('fakta_dibutuhkan', '')})"
            for f in doctrine_entry["faktor"]
        )
    elif "sub_dimensi" in doctrine_entry:
        fakta_list = "\n".join(f"- Sub-dimensi: {sd}" for sd in doctrine_entry["sub_dimensi"])
    else:
        fakta_list = "- Teks konsiderans, pasal inti, dan ketentuan penutup."

    indikator_vocab = "\n".join(
        f"- {ind}" for ind in doctrine_entry.get("indikator_lemah", [])
    ) or "(Dimensi ini tidak memiliki vocabulary indikator_lemah baku — evaluasi berbasis pertanyaan uji)"

    precedent_str = "(Tidak ada preseden khusus yang dilampirkan)"
    if precedents:
        p_lines = []
        for p in precedents:
            p_lines.append(
                f"- Kasus: {p.get('nama_kasus', p.get('case_id'))} | Forum: {p.get('forum')} ({p.get('tahun')})\n"
                f"  Ratio Decidendi: {p.get('ratio_decidendi', '').strip()}\n"
                f"  Distinguishing Note: {p.get('distinguishing_note', '').strip()}"
            )
        precedent_str = "\n".join(p_lines)

    prior_str = "(Tidak ada temuan dari dimensi sebelumnya)"
    if prior_findings:
        lines = []
        for p_dim, p_data in prior_findings.items():
            lines.append(f"- Dimensi {p_dim.upper()}:")
            lines.append(f"  * Status: {'LULUS' if p_data.get('lulus') else 'LEMAH / TIDAK LULUS'}")
            if p_data.get("indikator_lemah"):
                lines.append(f"  * Indikator Lemah Terdeteksi: {', '.join(p_data.get('indikator_lemah'))}")
            for q_item in p_data.get("jawaban_per_pertanyaan", []):
                if "delegasi" in q_item.get("pertanyaan", "").lower() or "materi" in q_item.get("pertanyaan", "").lower():
                    lines.append(f"  * Uraian Norma: {q_item.get('jawaban')}")
        prior_str = "\n".join(lines) + "\n\n⚠️ INSTRUKSI KRITIS: Perhatikan temuan dimensi sebelumnya di atas. Ujilah secara independen dan ketat apakah temuan di atas terkonfirmasi atau terbantahkan di bawah standar uji dimensi ini."

    return SYSTEM_PROMPT_TEMPLATE.format(
        nama=doctrine_entry.get("nama", doctrine_entry.get("dimension_id")),
        sumber=doctrine_entry.get("sumber", "Doktrin Hukum Indonesia"),
        sifat=doctrine_entry.get("sifat", "Analisis Yuridis"),
        pertanyaan_kunci=doctrine_entry.get("pertanyaan_kunci", ""),
        pertanyaan_uji_list=pertanyaan_list or "- Tidak ada pertanyaan eksplisit.",
        fakta_dibutuhkan_list=fakta_list,
        precedent_context=precedent_str,
        prior_findings_context=prior_str,
        indikator_lemah_vocabulary=indikator_vocab,
        indikator_lulus=doctrine_entry.get("indikator_lulus", "(Evaluasi substantif)"),
    )


# ─────────────────────────────────────────────────────────────
# 2. RETRIEVAL EXCERPT DARI CORPUS & SECTION-AWARE EXTRACTOR
# ─────────────────────────────────────────────────────────────

def _extract_section_aware_excerpt(full_text: str, dim_id: str) -> str:
    """
    Mengekstrak bagian-bagian naskah regulasi yang terarah sesuai kebutuhan doktrin per dimensi.
    Mencegah pemotongan buta yang menghilangkan pasal-pasal kunci di batang tubuh.
    """
    if len(full_text) <= 8000:
        return full_text

    # 1. Header (Konsiderans Menimbang & Dasar Hukum Mengingat)
    m_header = re.search(r'(Menimbang\s*:.*?(?=BAB I|Pasal 1\b))', full_text, re.DOTALL | re.IGNORECASE)
    header = m_header.group(1).strip() if m_header else full_text[:2000]

    # 2. Ketentuan Umum (Pasal 1 - Definisi Kunci)
    m_p1 = re.search(r'(Pasal 1\b.*?(?=BAB II|Pasal 2\b))', full_text, re.DOTALL | re.IGNORECASE)
    p1 = m_p1.group(1)[:2500].strip() if m_p1 else ""

    # 3. Batang Tubuh Relevan per Dimensi
    body_parts = []

    if dim_id == "filosofis":
        # Maksud, Tujuan, Sasaran, Asas (Bab II & III / Pasal 2-5)
        m = re.search(r'(BAB II\b.*?(?=BAB IV|Pasal 6\b))', full_text, re.DOTALL | re.IGNORECASE)
        if m:
            body_parts.append(m.group(1).strip())

    elif dim_id in ("ekonomi_kebijakan", "ria"):
        # Pengalokasian & Rumus Pembagian (Bab IV / Pasal 6-7) dan Klasifikasi Belanja (Bab VI / Pasal 12-18)
        m_alokasi = re.search(r'(BAB IV\b.*?(?=BAB V|Pasal 8\b))', full_text, re.DOTALL | re.IGNORECASE)
        m_guna = re.search(r'(BAB VI\b.*?(?=BAB VII|Pasal 20\b))', full_text, re.DOTALL | re.IGNORECASE)
        if m_alokasi:
            body_parts.append(m_alokasi.group(1).strip())
        if m_guna:
            body_parts.append(m_guna.group(1)[:3000].strip())

    elif dim_id == "sosiologis":
        # Lembaga Pelaksana (Bab V), Syarat & Jadwal Penyaluran (Bab VII / Pasal 20-23), Pengawasan (Bab VIII)
        m_org = re.search(r'(BAB V\b.*?(?=BAB VI|Pasal 12\b))', full_text, re.DOTALL | re.IGNORECASE)
        m_salur = re.search(r'(BAB VII\b.*?(?=BAB VIII|Pasal 29\b))', full_text, re.DOTALL | re.IGNORECASE)
        m_was = re.search(r'(BAB VIII\b.*?(?=BAB X|Pasal 34\b))', full_text, re.DOTALL | re.IGNORECASE)
        if m_org:
            body_parts.append(m_org.group(1).strip())
        if m_salur:
            body_parts.append(m_salur.group(1).strip())
        if m_was:
            body_parts.append(m_was.group(1).strip())

    elif dim_id == "normatif_akademik":
        # Alokasi (Bab IV), Penyaluran (Bab VII), Sanksi & Ketentuan Penutup (Bab IX & X)
        m_alokasi = re.search(r'(BAB IV\b.*?(?=BAB V|Pasal 8\b))', full_text, re.DOTALL | re.IGNORECASE)
        m_salur = re.search(r'(BAB VII\b.*?(?=BAB VIII|Pasal 29\b))', full_text, re.DOTALL | re.IGNORECASE)
        m_tutup = re.search(r'(BAB IX\b.*)', full_text, re.DOTALL | re.IGNORECASE)
        if m_alokasi:
            body_parts.append(m_alokasi.group(1).strip())
        if m_salur:
            body_parts.append(m_salur.group(1)[:2500].strip())
        if m_tutup:
            body_parts.append(m_tutup.group(1)[:2000].strip())

    elif dim_id == "institusional_evaluatif":
        # Alokasi (Bab IV), Penyaluran (Bab VII), Pengawasan & Sanksi (Bab VIII & IX)
        m_alokasi = re.search(r'(BAB IV\b.*?(?=BAB V|Pasal 8\b))', full_text, re.DOTALL | re.IGNORECASE)
        m_salur = re.search(r'(BAB VII\b.*?(?=BAB VIII|Pasal 29\b))', full_text, re.DOTALL | re.IGNORECASE)
        m_was = re.search(r'(BAB VIII\b.*?(?=BAB X|Pasal 34\b))', full_text, re.DOTALL | re.IGNORECASE)
        if m_alokasi:
            body_parts.append(m_alokasi.group(1).strip())
        if m_salur:
            body_parts.append(m_salur.group(1)[:2500].strip())
        if m_was:
            body_parts.append(m_was.group(1).strip())

    else:
        # Fallback untuk regulasi format lain atau dimensi konstitusional
        body_parts.append(full_text[len(header):len(header)+8000])

    sections = [
        "=== BAGIAN KONSIDERANS & DASAR HUKUM ===",
        header,
    ]
    if p1:
        sections.extend([
            "\n=== KETENTUAN UMUM (DEFINISI KUNCI) ===",
            p1,
        ])
    if body_parts:
        sections.extend([
            f"\n=== BATANG TUBUH & PASAL RELEVAN UNTUK DIMENSI {dim_id.upper()} ===",
            "\n\n".join(body_parts),
        ])

    return "\n".join(sections)


def _fetch_relevant_excerpt(regulation_text_ref: str, doctrine_entry: Dict[str, Any]) -> str:
    """
    Mengambil kutipan relevan dari teks regulasi atau KB bridge secara section-aware.
    """
    dim_id = doctrine_entry.get("dimension_id", "")
    if len(regulation_text_ref) > 100 and not regulation_text_ref.startswith(("http", "/", "reg:", "bpk_reg:")):
        # Input sudah merupakan teks naskah langsung
        return _extract_section_aware_excerpt(regulation_text_ref, dim_id)

    # Coba query ke AgentKnowledgeBridge
    if get_knowledge_bridge:
        try:
            bridge = get_knowledge_bridge()
            query_str = f"regulasi {regulation_text_ref} {dim_id}"
            kb_res = bridge.query(query_str, namespace="legal_regulations")
            if kb_res.success and kb_res.context:
                return _extract_section_aware_excerpt(kb_res.context, dim_id)
        except Exception as e:
            logger.warning(f"Gagal query excerpt via KnowledgeBridge: {e}")

    return f"Teks rujukan regulasi: {regulation_text_ref}"


# ─────────────────────────────────────────────────────────────
# 3. JSON PARSING & VOCABULARY VALIDATION
# ─────────────────────────────────────────────────────────────

def _safe_parse_json(raw_text: Optional[str]) -> Dict[str, Any]:
    """Parsing output LLM menjadi dictionary dengan fallback regex jika ada markdown fence."""
    if not raw_text or not isinstance(raw_text, str):
        logger.warning("Input raw_text kosong atau None, menggunakan fallback error dict.")
        return {
            "jawaban_per_pertanyaan": [],
            "indikator_lemah": [],
            "lulus": False,
            "catatan_tambahan": "[ERROR] Respon model kosong atau gagal dihasilkan oleh penyedia LLM.",
        }
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Coba ekstrak substring JSON di dalam kurung kurawal terluar
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

    logger.warning("Gagal parse JSON dari LLM output, menggunakan fallback error dict.")
    return {
        "jawaban_per_pertanyaan": [],
        "indikator_lemah": [],
        "lulus": False,
        "catatan_tambahan": f"[ERROR] Gagal mem-parse output model secara struktural. Raw: {raw_text[:200]}...",
    }


def validate_and_filter_indicators(
    parsed: Dict[str, Any], doctrine_entry: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Memfilter indikator_lemah agar hanya berisi istilah baku yang terdaftar di doctrine YAML.
    Istilah liar dipindahkan ke catatan_tambahan agar pipeline trigger tidak patah.
    """
    allowed: Set[str] = set(doctrine_entry.get("indikator_lemah", []))
    raw_found = parsed.get("indikator_lemah", [])
    if isinstance(raw_found, str):
        raw_found = [raw_found]

    found: Set[str] = set(raw_found)
    invalid = found - allowed

    # Intra-Dimension Self-Consistency Guard:
    # Mencegah kontradiksi internal antara isi uraian jawaban vs pilihan indikator lemah
    dim_id = doctrine_entry.get("dimension_id", "")
    if dim_id == "filosofis":
        answers_text = " ".join([q.get("jawaban", "") for q in parsed.get("jawaban_per_pertanyaan", [])]).lower()
        if "mengarahkan" in answers_text and ("optimalisasi" in answers_text or "hilirisasi" in answers_text or "dirumuskan dengan jelas" in answers_text):
            if "tujuan_hanya_administratif_tanpa_arah_perubahan_jelas" in found:
                found.remove("tujuan_hanya_administratif_tanpa_arah_perubahan_jelas")
                current_notes = parsed.get("catatan_tambahan") or ""
                parsed["catatan_tambahan"] = (
                    f"{current_notes}\n[SELF-CONSISTENCY GUARD] Tag 'tujuan_hanya_administratif_tanpa_arah_perubahan_jelas' diselaraskan karena bertentangan dengan jawaban yang menegaskan regulasi bersifat mengarahkan/substantif."
                ).strip()
                if not (found & allowed):
                    parsed["lulus"] = True

    if invalid and allowed:
        current_notes = parsed.get("catatan_tambahan") or ""
        parsed["catatan_tambahan"] = (
            f"{current_notes}\n[VALIDASI VOCABULARY] Indikator di luar daftar resmi dipindahkan ke catatan: {sorted(invalid)}"
        ).strip()
        parsed["indikator_lemah"] = sorted(found & allowed)
    else:
        parsed["indikator_lemah"] = sorted(found)

    return parsed


# ─────────────────────────────────────────────────────────────
# 4. EKSEKUTOR ANALISIS DIMENSI
# ─────────────────────────────────────────────────────────────

async def run_dimension_analysis(
    dimension_doctrine: Dict[str, Any],
    regulation_text_ref: str,
    precedents: Optional[List[Dict[str, Any]]] = None,
    prior_findings: Optional[Dict[str, Any]] = None,
    llm_connector: Optional[LLMConnector] = None,
) -> Dict[str, Any]:
    """
    Menjalankan pengujian untuk 1 Dimensi Doktrin Hukum secara asynchronous.
    """
    llm = llm_connector or LLMConnector()
    system_prompt = _build_system_prompt(
        dimension_doctrine,
        precedents=precedents,
        prior_findings=prior_findings,
    )
    excerpt = _fetch_relevant_excerpt(regulation_text_ref, dimension_doctrine)

    user_prompt = f"Lakukan pengujian yuridis terhadap naskah/kutipan regulasi berikut:\n\n{excerpt}"

    try:
        raw_response = None
        # 1. Coba VaneConnector (Groq openai/gpt-oss-120b / qwen3) via thread pool
        try:
            from integrations.vane_connector import VaneConnector
            vane = VaneConnector()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            vane_res = await asyncio.to_thread(vane._synthesize_groq, messages, vane.model, 0.0)
            if vane_res and vane_res.get("answer"):
                raw_response = vane_res["answer"]
        except Exception as err_vane:
            logger.debug(f"VaneConnector inference skipped/failed: {err_vane}")

        # 2. Fallback ke LLMConnector
        if not raw_response:
            if hasattr(llm, "generate"):
                res = await llm.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.0,
                    max_tokens=3000,
                )
                raw_response = res.get("content", "") if isinstance(res, dict) else str(res)
            elif hasattr(llm, "complete"):
                raw_response = await llm.complete(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.0,
                )
            else:
                raise AttributeError("LLM connector does not support generate or complete method")

        parsed = _safe_parse_json(raw_response)
        validated = validate_and_filter_indicators(parsed, dimension_doctrine)

        return {
            "dimension_id": dimension_doctrine.get("dimension_id"),
            "nama": dimension_doctrine.get("nama"),
            "lulus": validated.get("lulus"),
            "indikator_lemah": validated.get("indikator_lemah", []),
            "jawaban_per_pertanyaan": validated.get("jawaban_per_pertanyaan", []),
            "catatan": validated.get("catatan_tambahan", ""),
            "success": True,
        }
    except Exception as e:
        logger.error(f"Error executing dimension analysis for {dimension_doctrine.get('dimension_id')}: {e}")
        return {
            "dimension_id": dimension_doctrine.get("dimension_id"),
            "nama": dimension_doctrine.get("nama"),
            "lulus": False,
            "indikator_lemah": [],
            "jawaban_per_pertanyaan": [],
            "catatan": f"[EXCEPTION] {str(e)}",
            "success": False,
        }
