"""
pydantic_adapter.py — Pydantic Schema Validator & JSON-RPC 2.0 Sanitizer for SATRIA Co-Pilot.
Enforces strict type casting, fallback defaults, and malformed payload recovery
aligned with TASK-125 Redis Symbol Index and MCP Proxy standards.
"""

import json
import re
import uuid
import logging
from typing import Dict, Any, Optional, Tuple, Union
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger("satria_pydantic_adapter")


class MCPToolCallRequest(BaseModel):
    """Standar resmi pembungkus JSON-RPC 2.0 MCP."""
    jsonrpc: str = "2.0"
    method: str = "tools/call"
    params: Dict[str, Any]
    id: Optional[Union[str, int]] = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")


# Parameter Schemas per Tool
class LookupStaffArgs(BaseModel):
    query: str = Field(..., min_length=2, description="Nama pejabat, jabatan, atau tim kerja Ditjen Bangda")


class SearchRegulationArgs(BaseModel):
    query: str = Field(..., min_length=2, description="Nomor atau topik regulasi")
    namespace: Optional[str] = Field(default="legal_agent", description="Namespace RAG")


class SearchWebArgs(BaseModel):
    query: str = Field(..., min_length=2, description="Kata kunci pencarian live web")


class EvaluateDoctrineArgs(BaseModel):
    norm_text: str = Field(..., min_length=5, description="Naskah pasal draf regulasi")


class BrowsePortalArgs(BaseModel):
    url: str = Field(..., min_length=4, description="URL portal web target")
    task: str = Field(..., min_length=5, description="Instruksi eksplorasi portal")
    max_steps: Optional[int] = Field(default=5, ge=1, le=10, description="Maksimal langkah aksi sub-agent")


class SendMessageArgs(BaseModel):
    phone_number: str = Field(..., min_length=6, description="Nomor WhatsApp penerima")
    text: str = Field(..., min_length=1, description="Isi pesan")


class SearchCorrespondenceArgs(BaseModel):
    query: str = Field(..., min_length=2, description="Nomor surat, perihal, atau pengirim")


class PatchClauseArgs(BaseModel):
    problematic_clause: str = Field(..., min_length=3, description="Teks pasal atau klausul yang bermasalah")
    reason_or_defect: Optional[str] = Field(default="Pencegahan potensi ultra vires dan penyesuaian hierarki norma", description="Alasan perbaikan")


class VerifySPMArgs(BaseModel):
    indicator_query: str = Field(..., min_length=2, description="Sektor SPM atau indikator teknis pemenuhan pelayanan dasar")


class GenerateNotaDinasArgs(BaseModel):
    hal: str = Field(..., min_length=3, description="Perihal atau topik kegiatan/rapat dinas")
    poin_pembahasan: Optional[str] = Field(default="", description="Pokok pembahasan dan rekomendasi rapat")


class SystemHealthArgs(BaseModel):
    service_target: Optional[str] = Field(default="all", description="Target pemeriksaan: all, database, runpod, services")


class PolicyInventoryArgs(BaseModel):
    kategori: Optional[str] = Field(default=None, description="Kategori dokumen (KEPMENDAGRI, PERMENDAGRI, INMENDAGRI, SE, MOU)")
    tahun: Optional[int] = Field(default=2026, description="Tahun penerbitan")
    keyword: Optional[str] = Field(default=None, description="Kata kunci pencarian judul atau nomor")
    sub_kategori: Optional[str] = Field(default=None, description="Sub-kategori dokumen")
    limit: Optional[int] = Field(default=15, ge=1, le=50, description="Jumlah limit hasil")


class SatriaPydanticAdapter:
    """
    Adapter sanitasi dan validasi argumen JSON-RPC berbasis Pydantic v2.
    Mencegah error runtime -32602 (Invalid params) ke MCP Server.
    """

    TOOL_MODEL_MAP = {
        "lookup_bangda_staff": LookupStaffArgs,
        "search_regulation_knowledge": SearchRegulationArgs,
        "search_web_realtime": SearchWebArgs,
        "evaluate_bphn_doctrine": EvaluateDoctrineArgs,
        "browse_portal_autonomous": BrowsePortalArgs,
        "send_whatsapp_message": SendMessageArgs,
        "cari_surat_korespondensi": SearchCorrespondenceArgs,
        "legal_patch_clause": PatchClauseArgs,
        "legal_verify_spm": VerifySPMArgs,
        "nd_generate_laporan": GenerateNotaDinasArgs,
        "system_health_check": SystemHealthArgs,
        "policy_inventory_aggregator": PolicyInventoryArgs
    }

    @classmethod
    def sanitize_and_validate(
        cls,
        tool_name: str,
        raw_args: Union[Dict[str, Any], str]
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Memvalidasi argumen yang dihasilkan oleh model LLM.
        
        Returns:
            (is_valid, validated_args_dict, error_message)
        """
        # 1. Konversi raw string JSON jika model mengembalikan string
        parsed_dict: Dict[str, Any] = {}
        if isinstance(raw_args, str):
            clean_str = raw_args.strip()
            # Coba cari blok JSON {...}
            match = re.search(r'\{.*\}', clean_str, re.DOTALL)
            if match:
                clean_str = match.group(0)
            try:
                parsed_dict = json.loads(clean_str)
            except Exception as e:
                logger.warning(f"Failed to parse JSON string arguments for {tool_name}: {e}")
                # Fallback heuristik: jika string polos, jadikan sebagai 'query'
                parsed_dict = {"query": raw_args.strip()}
        elif isinstance(raw_args, dict):
            parsed_dict = raw_args
        else:
            parsed_dict = {}

        # 2. Dapatkan model Pydantic yang sesuai
        model_cls = cls.TOOL_MODEL_MAP.get(tool_name)
        if not model_cls:
            # Tool tanpa skema ketat, loloskan apa adanya
            return True, parsed_dict, None

        # 3. Validasi skema
        try:
            validated_obj = model_cls.model_validate(parsed_dict)
            return True, validated_obj.model_dump(), None
        except ValidationError as val_err:
            logger.warning(f"Validation error for tool '{tool_name}': {val_err}")
            # Coba auto-repair untuk parameter query umum
            if "query" in model_cls.model_fields and not parsed_dict.get("query"):
                first_val = next(iter(parsed_dict.values()), "") if parsed_dict else ""
                if first_val and isinstance(first_val, str):
                    repaired = {"query": first_val}
                    try:
                        validated_obj = model_cls.model_validate(repaired)
                        return True, validated_obj.model_dump(), None
                    except Exception:
                        pass
            return False, parsed_dict, str(val_err)

    @classmethod
    def wrap_to_jsonrpc(cls, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Membungkus argumen tervalidasi ke dalam payload JSON-RPC 2.0 MCP resmi."""
        req = MCPToolCallRequest(
            params={
                "name": tool_name,
                "arguments": arguments
            }
        )
        return req.model_dump()


# Singleton instance global
satria_pydantic_adapter = SatriaPydanticAdapter()
