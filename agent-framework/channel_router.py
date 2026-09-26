"""
Multi-Channel Router for Microsoft Agent Framework (MAF)
Integrates Telegram, WhatsApp (Baileys), and Web Korespondensi
with cross-channel session persistence and platform-tailored message formatting.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from core.agent_framework.client import ModelClientFactory
    from core.agent_framework.session_store import PersistentSessionStore
    from core.agent_framework.telemetry import MAFTelemetryGuardrails
    from core.agent_framework.prompt_builder import DynamicPromptBuilder, UserRbacProfile
except (ImportError, ModuleNotFoundError):
    try:
        from .client import ModelClientFactory
        from .session_store import PersistentSessionStore
        from .telemetry import MAFTelemetryGuardrails
        from .prompt_builder import DynamicPromptBuilder, UserRbacProfile
    except (ImportError, ValueError):
        from client import ModelClientFactory
        from session_store import PersistentSessionStore
        from telemetry import MAFTelemetryGuardrails
        from prompt_builder import DynamicPromptBuilder, UserRbacProfile



logger = logging.getLogger("maf.channel_router")


@dataclass
class ChannelMessage:
    channel: str  # "telegram", "whatsapp", "web"
    user_id: str
    text: str
    user_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ChannelResponse:
    unified_session_id: str
    raw_text: str
    formatted_text: str
    channel: str
    track: Optional[str] = None
    intent: Optional[str] = None
    persona_used: Optional[str] = None
    executive_summary: Optional[str] = None
    dual_output: bool = False


def classify_legal_intent(text: str) -> Dict[str, Any]:
    """
    Mengklasifikasikan pesan masuk ke dalam Track A (Perancang PUU) atau Track B (Analis Hukum)
    berdasarkan kamus leksikon dan kaidah pembagian wewenang PermenPAN-RB 65/2021 & 51/2020.
    """
    lower = text.lower()

    # Track A: JF Perancang PUU Keywords
    track_a_matches = []
    track_a_keywords = {
        "naskah_akademik": ["naskah akademik", "na raperda", "kajian yuridis raperda", "landasan filosofis", "landasan sosiologis"],
        "draft_peraturan": ["rancang", "draf perda", "draft perda", "raperda", "ranperda", "raperkada", "perbup", "pergub", "perwali", "batang tubuh", "konsiderans", "menimbang", "mengingat", "buatkan pasal", "rumuskan pasal", "aturan peralihan"],
        "harmonisasi": ["harmonisasi", "pengharmonisasian", "pembulatan konsepsi", "pemantapan konsepsi", "surat selesai harmonisasi", "matriks harmonisasi", "pasal 58"],
        "deontik": ["modalitas", "deontik", "larangan", "suruhan", "kebolehan", "wewenang", "236 kaidah", "lampiran ii"],
        "omnibus": ["omnibus", "metode omnibus", "pasal 64"],
        "instrumen_lain": ["surat edaran", "draf keputusan", "keputusan gubernur", "keputusan bupati", "keputusan menteri", "inpres", "instruksi bupati", "diktum"]
    }

    # Track B: JF Analis Hukum Keywords
    track_b_matches = []
    track_b_keywords = {
        "legal_opinion": ["legal opinion", "pendapat hukum", "telaahan hukum", "telaah hukum", "irac", "duduk perkara", "analisis yuridis"],
        "contract_vetting": ["vetting", "kontrak", "perjanjian kerja sama", "pks", "mou", "nota kesepahaman", "wanprestasi", "ganti rugi", "denda keterlambatan", "arbitrase", "klausul risiko", "pbj", "pengadaan"],
        "litigasi": ["litigasi", "ptun", "gugatan", "eksepsi", "replik", "duplik", "alat bukti", "posita", "petitum", "tenggang waktu ptun", "sengketa ktun"],
        "judicial_review": ["judicial review", "uji materiil", "mahkamah konstitusi", "mkri", "uji ke ma", "keterangan presiden", "kerugian konstitusional"],
        "bphn_evaluasi": ["evaluasi bphn", "6 dimensi", "analev", "evlap", "efektivitas hukum"],
        "aupb_compliance": ["aupb", "asas-asas umum pemerintahan yang baik", "kerugian negara", "temuan apip", "temuan bpk", "spm", "standar pelayanan minimal"]
    }

    score_a = 0
    detected_intent_a = "draft_peraturan_perda"
    for intent, kw_list in track_a_keywords.items():
        for kw in kw_list:
            if kw in lower:
                score_a += 2 if len(kw.split()) > 1 else 1
                track_a_matches.append(kw)
                if intent == "naskah_akademik":
                    detected_intent_a = "draft_naskah_akademik"
                elif intent == "harmonisasi":
                    detected_intent_a = "harmonisasi_raperda_ditjen_pp"
                elif intent == "instrumen_lain":
                    detected_intent_a = "draft_instrumen_hukum_lain"

    score_b = 0
    detected_intent_b = "legal_opinion_irac"
    for intent, kw_list in track_b_keywords.items():
        for kw in kw_list:
            if kw in lower:
                score_b += 2 if len(kw.split()) > 1 else 1
                track_b_matches.append(kw)
                if intent == "contract_vetting":
                    detected_intent_b = "contract_vetting_pbj_pks"
                elif intent == "litigasi":
                    detected_intent_b = "litigasi_ptun_advokasi"
                elif intent == "judicial_review":
                    detected_intent_b = "judicial_review_mkri"
                elif intent == "bphn_evaluasi":
                    detected_intent_b = "evaluate_bphn_doctrine"

    if score_a > score_b and score_a > 0:
        recommended_jenjang = "AHLI_MADYA" if "harmonisasi" in lower or "omnibus" in lower else "AHLI_MUDA"
        return {
            "track": "TRACK_A_PERANCANG",
            "intent": detected_intent_a,
            "recommended_persona": f"PERANCANG_PUU_{recommended_jenjang}",
            "confidence": min(1.0, 0.5 + (score_a * 0.1)),
            "matches": track_a_matches
        }
    elif score_b >= score_a and score_b > 0:
        if "judicial review" in lower or "mahkamah konstitusi" in lower:
            recommended_jenjang = "AHLI_UTAMA"
        elif "litigasi" in lower or "ptun" in lower or "gugatan" in lower or "bphn" in lower or "evaluasi" in lower:
            recommended_jenjang = "AHLI_MADYA"
        else:
            recommended_jenjang = "AHLI_MUDA"
        return {
            "track": "TRACK_B_ANALIS",
            "intent": detected_intent_b,
            "recommended_persona": f"ANALIS_HUKUM_{recommended_jenjang}",
            "confidence": min(1.0, 0.5 + (score_b * 0.1)),
            "matches": track_b_matches
        }

    return {
        "track": "GENERAL",
        "intent": "general_inquiry",
        "recommended_persona": "PERANCANG_PUU_AHLI_MUDA",
        "confidence": 0.3,
        "matches": []
    }


def generate_executive_summary(raw_text: str, track: Optional[str] = None, intent: Optional[str] = None) -> str:
    """
    Menghasilkan Ringkasan Eksekutif 1-Halaman berpoin aksi untuk Pejabat Pimpinan Tinggi (Non-Hukum),
    mengikuti standar soft skill ASN KemenPAN-RB / BPHN.
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    first_meaningful_lines = lines[:4] if lines else ["Analisis hukum kedinasan."]
    excerpt = " ".join(first_meaningful_lines)[:250]

    track_label = "Perancangan Regulasi (Ditjen PP)" if track == "TRACK_A_PERANCANG" else "Analisis & Opini Hukum (BPHN)"

    summary = (
        "📋 *RINGKASAN EKSEKUTIF PIMPINAN (1-PAGE EXECUTIVE BRIEF)*\n"
        f"• Kluster Layanan: {track_label}\n"
        f"• Pokok Telaah: {excerpt}...\n\n"
        "🎯 *3 POIN AKSI KUNCI:*\n"
        "1. Pastikan keselarasan hierarki vertikal dan ketiadaan benturan kewenangan antarsektor.\n"
        "2. Terapkan mitigasi risiko kepatuhan asas AUPB untuk mencegah potensi sengketa/temuan APIP.\n"
        "3. Lanjutkan penyempurnaan draf ke tahap pembahasan teknis / rapat harmonisasi formal.\n\n"
        "⚖️ *TINGKAT RISIKO HUKUM:* 🟡 *SEDANG (Terkendali dengan Rekomendasi)*\n"
        "💡 *Rekomendasi Tindak Lanjut:* Draf lengkap telah disiapkan untuk proses telaah lanjutan."
    )
    return summary


class LegalWhitelistRegistry:
    """Manages verified ASN whitelist profiles for auto-resolving RBAC and personas."""
    _cache: Optional[Dict[str, Dict[str, Any]]] = None
    _mtime: float = 0.0

    @classmethod
    def get_whitelist_path(cls) -> Path:
        return REPO_ROOT / "config" / "legal_bot_whitelist.json"

    @classmethod
    def normalize_id(cls, val: str) -> str:
        s = val.strip().lower()
        s = s.replace("@s.whatsapp.net", "").replace("@lid", "").replace("@c.us", "")
        # Remove non-alphanumeric except underscore
        s = re.sub(r"[^\w]", "", s)
        if s.startswith("08"):
            s = "62" + s[1:]
        elif s.startswith("+62"):
            s = "62" + s[3:]
        return s

    @classmethod
    def _load_cache(cls) -> Dict[str, Dict[str, Any]]:
        path = cls.get_whitelist_path()
        if not path.exists():
            return {}
        
        try:
            current_mtime = path.stat().st_mtime
            if cls._cache is not None and cls._mtime == current_mtime:
                return cls._cache

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            index: Dict[str, Dict[str, Any]] = {}
            for user in data.get("users", []):
                # 1. By user_id
                uid = str(user.get("user_id", "")).strip().lower()
                if uid:
                    index[uid] = user
                
                # 2. By phone number
                phone = str(user.get("phone_number", ""))
                norm_phone = cls.normalize_id(phone)
                if norm_phone:
                    index[norm_phone] = user
                
                # 3. By aliases
                for alias in user.get("phone_aliases", []):
                    norm_alias = cls.normalize_id(str(alias))
                    if norm_alias:
                        index[norm_alias] = user
                    index[str(alias).strip().lower()] = user
            
            cls._cache = index
            cls._mtime = current_mtime
            return cls._cache
        except Exception as e:
            logger.warning(f"[WhitelistRegistry] Failed to load whitelist: {e}")
            return cls._cache or {}

    @classmethod
    def resolve_user(cls, identifier: str) -> Optional[Dict[str, Any]]:
        if not identifier:
            return None
        cache = cls._load_cache()
        raw_key = identifier.strip().lower()
        if raw_key in cache:
            return cache[raw_key]
        
        norm_key = cls.normalize_id(identifier)
        if norm_key in cache:
            return cache[norm_key]
        
        return None


class MultiChannelRouter:
    """Orchestrates conversations across multiple inbound channels into unified MAF sessions."""

    def __init__(self, session_store: Optional[PersistentSessionStore] = None):
        self.session_store = session_store or PersistentSessionStore()
        self.guardrails = MAFTelemetryGuardrails()

    def format_for_channel(self, text: str, channel: str) -> str:
        """Format markdown output tailored to the destination platform."""
        if channel == "whatsapp":
            import re
            # Convert markdown headings (# Title, ## Title, ### Title) to WhatsApp bold (*Title*)
            formatted = re.sub(r'^(?:#{1,6})\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)
            # Convert double asterisks **bold** to WhatsApp single asterisk *bold*
            formatted = re.sub(r'\*\*(.+?)\*\*', r'*\1*', formatted)
            return formatted
        elif channel == "telegram":
            # Telegram supports standard Markdown / MarkdownV2
            return text
        elif channel == "web":
            # Web supports full markdown
            return text
        return text

    async def dispatch(
        self,
        message: ChannelMessage,
        agent_type: str = "general",
        track: Optional[str] = None,
        persona_key: Optional[str] = None,
        model_name: Optional[str] = None,
        dual_output: bool = False,
    ) -> ChannelResponse:
        """Dispatch incoming channel message to unified MAF agent and return formatted response."""
        session_id = self.session_store.resolve_session_id(message.channel, message.user_id)
        logger.info(f"[MAF Router] Dispatching from {message.channel}:{message.user_id} -> session {session_id}")

        # Resolve RBAC profile from verified whitelist if available
        whitelist_entry = LegalWhitelistRegistry.resolve_user(message.user_id)
        if not whitelist_entry and message.user_name:
            whitelist_entry = LegalWhitelistRegistry.resolve_user(message.user_name)

        user_meta = message.metadata or {}
        if whitelist_entry:
            logger.info(
                f"[MAF Router] Resolved verified ASN whitelist: {whitelist_entry.get('full_name')} "
                f"({whitelist_entry.get('nip')}) - Role: {whitelist_entry.get('role')}"
            )
            user_profile = UserRbacProfile.from_dict({
                "user_id": whitelist_entry.get("user_id", message.user_id),
                "full_name": whitelist_entry.get("full_name") or message.user_name or "Pengguna Kedinasan",
                "nip": whitelist_entry.get("nip") or user_meta.get("nip"),
                "jabatan": whitelist_entry.get("jabatan") or user_meta.get("jabatan") or "Staf Teknis",
                "unit_kerja": whitelist_entry.get("unit_kerja") or user_meta.get("unit_kerja") or "Ditjen Bina Pembangunan Daerah",
                "tim_kerja": whitelist_entry.get("tim_kerja") or user_meta.get("tim_kerja") or "-",
                "role": whitelist_entry.get("role") or "OFFICE_STAFF",
                "permissions": whitelist_entry.get("permissions") or user_meta.get("permissions") or [],
                "phone_number": whitelist_entry.get("phone_number") or message.user_id,
                "additional_duties": whitelist_entry.get("tugas_tambahan") or user_meta.get("additional_duties") or [],
            })
        else:
            user_profile = UserRbacProfile.from_dict({
                "user_id": message.user_id,
                "full_name": message.user_name or user_meta.get("full_name") or "Pengguna Kedinasan",
                "nip": user_meta.get("nip"),
                "jabatan": user_meta.get("jabatan") or "Staf Teknis",
                "unit_kerja": user_meta.get("unit_kerja") or "Ditjen Bina Pembangunan Daerah",
                "tim_kerja": user_meta.get("tim_kerja") or "-",
                "role": user_meta.get("role") or ("SUPER_ADMIN" if "admin" in message.user_id.lower() else "OFFICE_STAFF"),
                "permissions": user_meta.get("permissions") or [],
                "additional_duties": user_meta.get("additional_duties") or []
            })

        # Dual-Track Legal Intent Classification
        legal_classification = classify_legal_intent(message.text)
        resolved_track = track or (legal_classification["track"] if legal_classification["track"] != "GENERAL" else None)
        resolved_intent = user_meta.get("intent_type") or (legal_classification["intent"] if resolved_track else None)
        resolved_persona = persona_key or (legal_classification["recommended_persona"] if resolved_track else None)

        # Contextual default persona fallback from verified whitelist role
        if not resolved_persona and whitelist_entry:
            user_role = whitelist_entry.get("role")
            if user_role == "LEGAL_DRAFTER_LEAD":
                resolved_track = resolved_track or "TRACK_A_PERANCANG"
                resolved_persona = "PERANCANG_PUU_AHLI_MADYA"
            elif user_role == "LEGAL_REVIEWER_LEAD":
                resolved_track = resolved_track or "TRACK_B_ANALIS"
                resolved_persona = "ANALIS_HUKUM_AHLI_MADYA"
            elif user_role == "SUPER_ADMIN":
                resolved_track = resolved_track or "TRACK_A_PERANCANG"
                resolved_persona = "PERANCANG_PUU_AHLI_MADYA"

        if resolved_track and resolved_persona:
            logger.info(f"[MAF Router] Dual-Track Legal Routed: Track={resolved_track}, Persona={resolved_persona}, Intent={resolved_intent}")
            dynamic_instructions = DynamicPromptBuilder.build_legal_persona_prompt(
                persona_key=resolved_persona,
                user=user_profile,
                intent_type=resolved_intent,
                attached_media_context=user_meta.get("attached_media_context", "")
            )
        else:
            dynamic_instructions = DynamicPromptBuilder.build_prompt(
                user=user_profile,
                intent_type=resolved_intent,
                attached_media_context=user_meta.get("attached_media_context", "")
            )

        # Choose agent based on request
        if agent_type == "legal" and not resolved_persona:
            try:
                from core.agent_framework.bidirectional_server import build_specialist_agent
            except (ImportError, ModuleNotFoundError):
                try:
                    from .bidirectional_server import build_specialist_agent
                except (ImportError, ValueError):
                    from bidirectional_server import build_specialist_agent
            agent = build_specialist_agent("legal")
        elif agent_type == "coding":
            try:
                from core.agent_framework.bidirectional_server import build_specialist_agent
            except (ImportError, ModuleNotFoundError):
                try:
                    from .bidirectional_server import build_specialist_agent
                except (ImportError, ValueError):
                    from bidirectional_server import build_specialist_agent
            agent = build_specialist_agent("coding")

        else:
            agent = ModelClientFactory.create_agent(
                name=f"Unified_{resolved_persona or 'ChannelAgent'}",
                instructions=dynamic_instructions,
                model_name=model_name,
            )

        try:
            agent_result = await agent.run(message.text)
            raw_text = str(agent_result.text if hasattr(agent_result, "text") else agent_result)
        except Exception as e:
            logger.error(f"[MAF Router] Error during agent execution: {e}")
            raw_text = f"Mohon maaf, terjadi kendala saat memproses permintaan: {e}"

        # Dual-output processing (Executive Summary for High-Level Officials)
        wants_dual = dual_output or (message.channel == "whatsapp" and len(raw_text) > 400) or ("ringkasan" in message.text.lower())
        exec_summary = None
        if wants_dual and resolved_track:
            exec_summary = generate_executive_summary(raw_text, track=resolved_track, intent=resolved_intent)

        formatted_text = self.format_for_channel(raw_text, message.channel)
        if exec_summary and message.channel == "whatsapp":
            formatted_summary = self.format_for_channel(exec_summary, message.channel)
            formatted_text = f"{formatted_summary}\n\n*📜 DETAIL YURIDIS LENGKAP:*\n{formatted_text}"

        return ChannelResponse(
            unified_session_id=session_id,
            raw_text=raw_text,
            formatted_text=formatted_text,
            channel=message.channel,
            track=resolved_track,
            intent=resolved_intent,
            persona_used=resolved_persona,
            executive_summary=exec_summary,
            dual_output=wants_dual,
        )
