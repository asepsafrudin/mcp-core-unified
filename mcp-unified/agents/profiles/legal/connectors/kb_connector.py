"""
Knowledge Base Connector - UU 23/2014 & SPM Integration
"""

import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path


class KBConnector:
    """Connector untuk Knowledge Base UU 23/2014."""
    
    def __init__(self):
        self.kb_path = Path('Bangda_PUU/lampiran UU 23/docs/knowledge/UU_23_2014_knowledge_base.json')
        self.spm_path = Path('Bangda_PUU/lampiran UU 23/processed/klasifikasi_bidang_urusan_spm.json')
        self._kb_cache = None
        self._spm_cache = None
    
    def _load_kb(self) -> Dict:
        """Load knowledge base ke cache."""
        if self._kb_cache is None:
            if self.kb_path.exists():
                with open(self.kb_path, 'r', encoding='utf-8') as f:
                    self._kb_cache = json.load(f)
            else:
                self._kb_cache = {"bab": [], "pasal": []}
        return self._kb_cache
    
    def _load_spm(self) -> Dict:
        """Load SPM classification ke cache."""
        if self._spm_cache is None:
            if self.spm_path.exists():
                with open(self.spm_path, 'r', encoding='utf-8') as f:
                    self._spm_cache = json.load(f)
            else:
                self._spm_cache = {"klasifikasi": []}
        return self._spm_cache
    
    def search_regulation(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search regulasi by keyword.
        
        Returns:
            List of matching pasal/bab
        """
        kb = self._load_kb()
        results = []
        query_lower = query.lower()
        
        # Search pasal
        for pasal in kb.get('pasal', []):
            text = f"{pasal.get('nomor', '')} {pasal.get('judul', '')} {pasal.get('isi', '')}"
            if query_lower in text.lower():
                results.append({
                    'type': 'pasal',
                    'nomor': pasal.get('nomor'),
                    'judul': pasal.get('judul'),
                    'isi': pasal.get('isi')[:500] + '...' if len(pasal.get('isi', '')) > 500 else pasal.get('isi'),
                    'bab': pasal.get('bab')
                })
        
        return results[:limit]
    
    def get_spm_by_bidang(self, bidang_urusan: str) -> List[Dict]:
        """
        Get SPM classification by bidang urusan.
        
        Args:
            bidang_urusan: Nama bidang urusan (e.g., "Pendidikan")
        
        Returns:
            List of SPM items
        """
        spm = self._load_spm()
        results = []
        bidang_lower = bidang_urusan.lower()
        
        for item in spm.get('klasifikasi', []):
            if bidang_lower in item.get('bidang_urusan', '').lower():
                results.append(item)
        
        return results
    
    def verify_spm_classification(self, spm_data: Dict) -> Dict[str, Any]:
        """
        Verifikasi klasifikasi SPM terhadap UU 23/2014.
        
        Returns:
            Verification result dengan status dan issues
        """
        issues = []
        verified = True
        
        # Check required fields
        required = ['bidang_urusan', 'sub_urusan', 'spm']
        for field in required:
            if field not in spm_data or not spm_data[field]:
                issues.append(f"Missing required field: {field}")
                verified = False
        
        # Check dasar hukum references
        dasar_hukum = spm_data.get('dasar_hukum', [])
        if not dasar_hukum:
            issues.append("No dasar hukum specified")
            verified = False
        
        # Cross-check dengan UU 23/2014
        kb = self._load_kb()
        uu_mentioned = False
        for dh in dasar_hukum:
            if '23/2014' in str(dh) or '23 tahun 2014' in str(dh).lower():
                uu_mentioned = True
                break
        
        if not uu_mentioned:
            issues.append("UU 23/2014 not referenced in dasar hukum")
        
        return {
            'verified': verified,
            'issues': issues,
            'spm_data': spm_data
        }
    
    def get_citation(self, pasal_nomor: str) -> Optional[Dict]:
        """Get citation data untuk pasal tertentu."""
        kb = self._load_kb()
        
        for pasal in kb.get('pasal', []):
            if str(pasal.get('nomor')) == pasal_nomor:
                return {
                    'nomor': pasal.get('nomor'),
                    'judul': pasal.get('judul'),
                    'isi': pasal.get('isi'),
                    'bab': pasal.get('bab'),
                    'citation': f"Pasal {pasal.get('nomor')} UU Nomor 23 Tahun 2014"
                }
        
        return None
