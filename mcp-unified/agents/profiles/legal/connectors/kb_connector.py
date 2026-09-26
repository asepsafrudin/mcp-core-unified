"""
Knowledge Base Connector - UU 23/2014, NSPK, & SPM Integration
Reads from:
- /home/aseps/MCP/docs/uu23_mapping/ (Comprehensive markdown mapping)
- /home/aseps/MCP/storage/datasets/uu23_regulasi_json/ (Structured PP & Permendagri datasets)
- /home/aseps/MCP/storage/pedoman_analisis_evaluasi_extracted.md (BPHN Evaluation Guidelines)
"""

import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path


class KBConnector:
    """Connector untuk Knowledge Base UU 23/2014 & Regulasi Turunannya."""
    
    def __init__(self):
        self.repo_root = Path("/home/aseps/MCP")
        self.uu23_docs_dir = self.repo_root / "docs/uu23_mapping"
        self.regulasi_datasets_dir = self.repo_root / "storage/datasets/uu23_regulasi_json"
        self.spm_json_path = self.regulasi_datasets_dir / "PP_2_2018_SPM.json"
        
        self._docs_cache: Optional[Dict[str, str]] = None
        self._json_cache: Optional[Dict[str, Any]] = None

    def _load_uu23_docs(self) -> Dict[str, str]:
        """Load semua dokumen mapping UU 23/2014 ke memory cache."""
        if self._docs_cache is None:
            self._docs_cache = {}
            if self.uu23_docs_dir.exists():
                for file in self.uu23_docs_dir.glob("*.md"):
                    try:
                        with open(file, "r", encoding="utf-8") as f:
                            self._docs_cache[file.stem] = f.read()
                    except Exception:
                        pass
        return self._docs_cache

    def _load_json_datasets(self) -> Dict[str, Any]:
        """Load dataset regulasi turunan UU 23/2014."""
        if self._json_cache is None:
            self._json_cache = {}
            if self.regulasi_datasets_dir.exists():
                for file in self.regulasi_datasets_dir.glob("*.json"):
                    try:
                        with open(file, "r", encoding="utf-8") as f:
                            self._json_cache[file.stem] = json.load(f)
                    except Exception:
                        pass
        return self._json_cache

    def search_regulation(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Pencarian kata kunci pada seluruh basis pengetahuan UU 23/2014 dan regulasi turunannya.
        
        Returns:
            List of matching sections / documents.
        """
        results = []
        query_lower = query.lower()
        
        # 1. Search in UU 23/2014 Markdown Mappings
        docs = self._load_uu23_docs()
        for doc_name, content in docs.items():
            if query_lower in content.lower():
                # Extract relevant snippet
                idx = content.lower().find(query_lower)
                start = max(0, idx - 150)
                end = min(len(content), idx + 350)
                snippet = content[start:end].replace("\n", " ").strip()
                
                results.append({
                    "source_type": "uu23_mapping_doc",
                    "doc_name": doc_name,
                    "title": doc_name.replace("_", " ").title(),
                    "snippet": f"...{snippet}...",
                    "reference": f"docs/uu23_mapping/{doc_name}.md"
                })

        # 2. Search in Structured JSON Regulations (PP SPM, PP Keuangan, PP Perangkat Daerah, dll.)
        json_data = self._load_json_datasets()
        for reg_name, data in json_data.items():
            data_str = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
            if query_lower in data_str.lower():
                results.append({
                    "source_type": "derived_regulation_json",
                    "doc_name": reg_name,
                    "title": reg_name.replace("_", " "),
                    "reference": f"storage/datasets/uu23_regulasi_json/{reg_name}.json"
                })

        return results[:limit]

    def get_spm_by_bidang(self, bidang_urusan: str) -> List[Dict[str, Any]]:
        """Mengambil data SPM berdasarkan bidang urusan (PP 2/2018)."""
        json_data = self._load_json_datasets()
        spm_data = json_data.get("PP_2_2018_SPM", {})
        results = []
        bidang_lower = bidang_urusan.lower()
        
        # Cari di struktur JSON SPM
        if isinstance(spm_data, dict):
            for k, v in spm_data.items():
                if bidang_lower in str(k).lower() or bidang_lower in str(v).lower():
                    results.append({"bidang": k, "detail": v})
        return results

    def verify_spm_classification(self, spm_data: Dict) -> Dict[str, Any]:
        """Verifikasi data SPM terhadap ketentuan UU 23/2014 & PP 2/2018."""
        issues = []
        verified = True
        
        required = ['bidang_urusan', 'sub_urusan', 'spm']
        for field in required:
            if field not in spm_data or not spm_data[field]:
                issues.append(f"Missing required field: {field}")
                verified = False
        
        dasar_hukum = spm_data.get('dasar_hukum', [])
        if not dasar_hukum:
            issues.append("No dasar hukum specified")
            verified = False
        
        uu_mentioned = any(
            '23/2014' in str(dh) or '23 tahun 2014' in str(dh).lower() or 'pp 2/2018' in str(dh).lower()
            for dh in dasar_hukum
        )
        if not uu_mentioned:
            issues.append("UU 23/2014 atau PP 2/2018 tidak dicantumkan sebagai dasar hukum")
        
        return {
            'verified': verified,
            'issues': issues,
            'spm_data': spm_data
        }
