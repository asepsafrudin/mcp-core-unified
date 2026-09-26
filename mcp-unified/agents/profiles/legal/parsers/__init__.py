"""
__init__.py — parsers package (7 Pilar DIM v2.0)
"""
from .legal_ast_parser import (
    parse_regulation_text,
    extract_articles_flat,
    get_article_by_id,
    get_glossary_definitions,
    serialize_to_markdown,
)
from .norm_transformation_engine import (
    build_cross_reference_graph,
    get_blast_radius_report,
    amendment_mapping,
    delete_article,
    split_article,
    merge_articles,
    renumber_all_articles,
)
from .editorial_linter import (
    run_full_editorial_audit,
    check_puebi_compliance,
    harmonize_glossary,
    validate_cross_references,
)
from .dim_disposition_engine import (
    set_article_disposition,
    batch_set_dispositions,
    get_dim_summary,
    format_dim_table_markdown,
)
from .hierarchy_validator import (
    classify_instrument_type,
    validate_hierarchy_compliance,
    detect_vertical_norm_conflict,
    run_full_hierarchy_audit,
)
from .jurisdiction_analyzer import (
    detect_portfolio_overlap,
    generate_skb_framework,
    validate_vertical_sop_alignment,
)
from .instrument_mandate_mapper import (
    check_spbe_alignment,
    analyze_fiscal_statutory_linkage,
    map_facility_capacity_standards,
    extract_lifecycle_mandates,
    detect_sunset_trigger,
    generate_closed_loop_revision,
    run_full_governance_audit,
)

__all__ = [
    # Pilar 1 & 2 — AST + Transformasi
    "parse_regulation_text", "extract_articles_flat", "get_article_by_id",
    "get_glossary_definitions", "serialize_to_markdown",
    "build_cross_reference_graph", "get_blast_radius_report",
    "amendment_mapping", "delete_article", "split_article", "merge_articles", "renumber_all_articles",
    # Pilar 2 — Linter
    "run_full_editorial_audit", "check_puebi_compliance", "harmonize_glossary", "validate_cross_references",
    # Pilar 6 — DIM
    "set_article_disposition", "batch_set_dispositions", "get_dim_summary", "format_dim_table_markdown",
    # Pilar 3 — Hierarki
    "classify_instrument_type", "validate_hierarchy_compliance", "detect_vertical_norm_conflict", "run_full_hierarchy_audit",
    # Pilar 4 — Jurisdiksi
    "detect_portfolio_overlap", "generate_skb_framework", "validate_vertical_sop_alignment",
    # Pilar 5 & 7 — Mandat & Governance
    "check_spbe_alignment", "analyze_fiscal_statutory_linkage", "map_facility_capacity_standards",
    "extract_lifecycle_mandates", "detect_sunset_trigger", "generate_closed_loop_revision", "run_full_governance_audit",
]
