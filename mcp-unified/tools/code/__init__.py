"""
Code Tools Module - Phase 6 Direct Registration

Code analysis and quality tools.
"""

# Import modules (triggers @register_tool registration)
from . import self_review
from . import analyzer

# Export for backward compatibility
from .self_review import (
    Issue,
    CHECKS,
    self_review,
    self_review_batch,
)
from .analyzer import (
    RiskLevel,
    CodeMetrics,
    RiskAssessment,
    CodeQualityAnalyzer,
    get_analyzer,
    analyze_file,
    analyze_code,
    analyze_project,
)

__all__ = [
    # Self-review exports
    "Issue",
    "CHECKS",
    "self_review",
    "self_review_batch",
    # Analyzer exports
    "RiskLevel",
    "CodeMetrics",
    "RiskAssessment",
    "CodeQualityAnalyzer",
    "get_analyzer",
    "analyze_file",
    "analyze_code",
    "analyze_project",
]
