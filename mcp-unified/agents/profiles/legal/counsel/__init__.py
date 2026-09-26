"""
counsel/__init__.py - Track B (JF Analis Hukum - BPHN / Kemenkumham)
=====================================================================
Modul implementasi siklus hilir evaluasi regulasi, legal counsel, dan advokasi:
1. opinion_agent: Legal Opinion IRAC, AUPB Shield, Evaluasi Diskresi, & Deteksi Tipikor.
2. contract_agent: Audit & Vetting Klausul Kontrak PBJ Pemerintah & PKS Daerah.
3. litigation_agent: Kronologi Fakta, 5 Alat Bukti PTUN, Eksepsi Formal, & Judicial Review MK/MA.
"""

from .opinion_agent import (
    LegalOpinionAgent,
    LegalIssue,
    RuleReference,
    AUPBComplianceCheck,
    DiskresiAssessment,
    LegalOpinionResult,
)
from .contract_agent import (
    ContractVettingAgent,
    ContractRiskItem,
    ContractVettingResult,
)
from .litigation_agent import (
    LitigationAdvocacyAgent,
    KronologiEvent,
    AlatBuktiPTUN,
    EksepsiItem,
    JudicialReviewDefense,
    LitigationCaseFile,
)

__all__ = [
    "LegalOpinionAgent",
    "LegalIssue",
    "RuleReference",
    "AUPBComplianceCheck",
    "DiskresiAssessment",
    "LegalOpinionResult",
    "ContractVettingAgent",
    "ContractRiskItem",
    "ContractVettingResult",
    "LitigationAdvocacyAgent",
    "KronologiEvent",
    "AlatBuktiPTUN",
    "EksepsiItem",
    "JudicialReviewDefense",
    "LitigationCaseFile",
]
