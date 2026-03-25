"""
SPM Processor - Standar Pelayanan Minimal Processing
"""

from typing import Dict, Any, List
from ..connectors.llm_connector import LLMConnector
from ..connectors.kb_connector import KBConnector


class SPMProcessor:
    """Processor untuk klasifikasi dan verifikasi SPM."""
    
    def __init__(self):
        self.llm = LLMConnector()
        self.kb = KBConnector()
    
    async def classify_spm(self, deskripsi: str, bidang_hint: str = None) -> Dict[str, Any]:
        """
        Klasifikasi SPM dari deskripsi.
        
        Args:
            deskripsi: Deskripsi layanan/urusan
            bidang_hint: Optional hint untuk bidang urusan
        
        Returns:
            Classification result dengan bidang, sub_urusan, dan SPM
        """
        system_prompt = """Anda adalah ahli klasifikasi SPM (Standar Pelayanan Minimal) sesuai UU 23/2014.
        Analisis deskripsi dan tentukan:
        1. Bidang urusan pemerintahan
        2. Sub-urusan
        3. Jenis SPM yang sesuai
        4. Dasar hukum (referensi ke UU 23/2014)
        
        Response dalam format JSON."""
        
        prompt = f"""Klasifikasikan SPM untuk deskripsi berikut:
        
        Deskripsi: {deskripsi}
        {f"Bidang hint: {bidang_hint}" if bidang_hint else ""}
        
        Berikan response dalam format JSON:
        {{
            "bidang_urusan": "...",
            "sub_urusan": "...",
            "spm": "...",
            "indikator": ["..."],
            "dasar_hukum": ["UU 23/2014 Pasal ..."],
            "confidence": 0.85
        }}
        """
        
        result = await self.llm.generate(prompt, system_prompt)
        
        if result['success']:
            try:
                import json
                classification = json.loads(result['content'])
                return {
                    'success': True,
                    'classification': classification,
                    'model_used': result['model_used']
                }
            except json.JSONDecodeError:
                return {
                    'success': False,
                    'error': 'Failed to parse LLM response',
                    'raw_response': result['content']
                }
        
        return {
            'success': False,
            'error': result.get('error', 'LLM failed')
        }
    
    async def verify_spm(self, spm_data: Dict) -> Dict[str, Any]:
        """
        Verifikasi data SPM dengan KB dan LLM.
        
        Returns:
            Verification result
        """
        # Step 1: Basic KB verification
        kb_result = self.kb.verify_spm_classification(spm_data)
        
        # Step 2: LLM deep verification
        system_prompt = """Anda adalah ahli verifikator SPM. Verifikasi data SPM berikut
        terhadap UU 23/2014 dan regulasi terkait. Identifikasi:
        1. Kelengkapan data
        2. Konsistensi dasar hukum
        3. Relevansi indikator
        4. Rekomendasi perbaikan"""
        
        prompt = f"""Verifikasi data SPM berikut:
        
        {spm_data}
        
        Berikan analisis dalam format JSON:
        {{
            "is_valid": true/false,
            "completeness_score": 0.0-1.0,
            "issues": ["..."],
            "recommendations": ["..."],
            "missing_references": ["..."]
        }}
        """
        
        llm_result = await self.llm.generate(prompt, system_prompt)
        
        if llm_result['success']:
            try:
                import json
                llm_analysis = json.loads(llm_result['content'])
                
                return {
                    'success': True,
                    'kb_verification': kb_result,
                    'llm_analysis': llm_analysis,
                    'overall_valid': kb_result['verified'] and llm_analysis.get('is_valid', False),
                    'model_used': llm_result['model_used']
                }
            except json.JSONDecodeError:
                pass
        
        return {
            'success': True,
            'kb_verification': kb_result,
            'llm_analysis': None,
            'overall_valid': kb_result['verified']
        }
