"""
Semantic Triple Extractor for Graph Memory (TASK-122).
Uses LLM to extract structured (Subject -> Predicate -> Object) knowledge triples from text.
"""

import json
import re
import urllib.request
from typing import List, Dict, Any, Optional
from pathlib import Path
from .schema import Triple

EXTRACTION_SYSTEM_PROMPT = """Anda adalah pakar Knowledge Graph Information Extraction.
Tugas Anda adalah mengekstrak entitas dan relasi faktual (Triples) dari teks yang diberikan.

Format output WAJIB berupa JSON Array murni yang berisi objek dengan format:
[
  {
    "source_id": "kategori:nama_ringkas_tanpa_spasi",
    "source_name": "Nama lengkap subjek",
    "source_type": "surat|pegawai|instansi|regulasi|lokasi|topik|jabatan",
    "relation": "relasi_snake_case (contoh: ditandatangani_oleh, merujuk_ke, menjabat_sebagai, bertugas_ke, diterbitkan_pada)",
    "target_id": "kategori:nama_ringkas_tanpa_spasi",
    "target_name": "Nama lengkap objek",
    "target_type": "surat|pegawai|instansi|regulasi|lokasi|topik|jabatan",
    "weight": 1.0,
    "metadata": {"konteks": "keterangan tambahan singkat"}
  }
]

HANYA kembalikan JSON array valid tanpa teks pengantar atau penutup markdown!
"""

class SemanticTripleExtractor:
    def __init__(self, ollama_url: Optional[str] = None, model: str = "qwen2.5-coder:7b"):
        self.model = model
        self.ollama_url = (ollama_url or self._resolve_ollama_url()).rstrip("/")

    def _resolve_ollama_url(self) -> str:
        env_ai_file = Path("/home/aseps/MCP/config/env/.env.ai")
        if env_ai_file.exists():
            try:
                with open(env_ai_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("OLLAMA_URL="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
                            if val:
                                return val
            except Exception:
                pass
        return "http://localhost:11434"

    def extract_triples_from_text(self, text: str, max_triples: int = 15) -> List[Triple]:
        """
        Extract triples using LLM via Ollama endpoint.
        """
        if not text or len(text.strip()) < 10:
            return []

        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nTEKS DOKUMEN:\n{text[:3000]}\n\nJSON Output:"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }
        
        endpoint = f"{self.ollama_url}/api/generate"
        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_resp = data.get("response", "").strip()
                return self._parse_json_triples(raw_resp)
        except Exception as e:
            # Fallback heuristic extractor jika LLM offline
            return self._heuristic_extractor(text)

    def _parse_json_triples(self, raw_text: str) -> List[Triple]:
        """Extract and sanitize JSON array from LLM output."""
        triples = []
        # Find JSON array using regex
        match = re.search(r'\[\s*\{.*\}\s*\]', raw_text, re.DOTALL)
        json_str = match.group(0) if match else raw_text
        
        try:
            items = json.loads(json_str)
            if isinstance(items, list):
                for it in items:
                    if "source_id" in it and "relation" in it and "target_id" in it:
                        triples.append(Triple(
                            source_id=str(it["source_id"]).lower(),
                            source_name=str(it.get("source_name", it["source_id"])),
                            source_type=str(it.get("source_type", "concept")),
                            relation=str(it["relation"]).lower().replace(" ", "_"),
                            target_id=str(it["target_id"]).lower(),
                            target_name=str(it.get("target_name", it["target_id"])),
                            target_type=str(it.get("target_type", "concept")),
                            weight=float(it.get("weight", 1.0)),
                            metadata=it.get("metadata", {})
                        ))
        except Exception:
            pass
        return triples

    def _heuristic_extractor(self, text: str) -> List[Triple]:
        """Rule-based regex fallback extractor for key document entities."""
        triples = []
        # 1. Nomor Surat
        no_surat_match = re.search(r'(?:Nomor|No\.?)\s*:\s*([0-9A-Za-z\.\/\-]+)', text, re.IGNORECASE)
        if no_surat_match:
            no_surat = no_surat_match.group(1).strip()
            surat_id = f"surat:{no_surat.replace('/', '_')}"
            
            # Tanggal
            tgl_match = re.search(r'(\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4})', text, re.IGNORECASE)
            if tgl_match:
                tgl = tgl_match.group(1).strip()
                triples.append(Triple(
                    source_id=surat_id,
                    source_name=f"Surat {no_surat}",
                    source_type="surat",
                    relation="diterbitkan_pada",
                    target_id=f"tanggal:{tgl.replace(' ', '_').lower()}",
                    target_name=tgl,
                    target_type="tanggal"
                ))
                
            # Penandatangan / Nama
            nama_match = re.search(r'(?:Analis|Kepala|Sekretaris|Direktur)[^\n]*\n+([A-Z][a-zA-Z\s\.,]+(?:SH|MH|M\.Si|M\.H|S\.H|MM)?)', text)
            if nama_match:
                nama = nama_match.group(1).strip()
                if len(nama) > 4:
                    triples.append(Triple(
                        source_id=surat_id,
                        source_name=f"Surat {no_surat}",
                        source_type="surat",
                        relation="ditandatangani_oleh",
                        target_id=f"pegawai:{nama.replace(' ', '_').lower()}",
                        target_name=nama,
                        target_type="pegawai"
                    ))
        return triples
