"""
MCP Tools for Legal Agent Suite.
Mengekspos seluruh kapabilitas penalaran yuridis multi-dimensi, multi-tier ingestion,
statutory RAG verifier, correspondence alignment, policy-as-code, radar visualizer,
transitional lifecycle monitor, dan alert dispatcher sebagai MCP tools.

Update v4.0 (TASK-131 — 7 Pilar DIM v2.0):
- legal_ast_parse()        : Parse dokumen hukum menjadi LegalDocument AST terstruktur
- legal_lint_editorial()   : Audit PUEBI, Glosarium, dan Style Guide UU 12/2011 (Pilar 2)
- legal_transform_clause() : Manipulasi norma struktural (Split/Merge/Renumber/Delete) (Pilar 1)
- legal_disposition_matrix(): Kelola matriks disposisi DIM per pasal (Pilar 6)
"""

from typing import Dict, Any, Optional, List
import asyncio
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.profiles.legal.connectors.llm_connector import LLMConnector
from agents.profiles.legal.connectors.kb_connector import KBConnector
from agents.profiles.legal.processors.spm_processor import SPMProcessor


class LegalTools:
    """MCP Tools Suite untuk Legal Agent."""
    
    def __init__(self):
        self.llm = LLMConnector()
        self.kb = KBConnector()
        self.spm_processor = SPMProcessor()
    
    async def verify_spm_classification(self, spm_data: Dict) -> Dict[str, Any]:
        """Tool: Verifikasi klasifikasi SPM."""
        return await self.spm_processor.verify_spm(spm_data)
    
    async def research_regulation(self, query: str, use_web: bool = True) -> Dict[str, Any]:
        """Tool: Riset regulasi dari KB dan web."""
        kb_results = self.kb.search_regulation(query)
        result = {
            "query": query,
            "local_results": kb_results,
            "web_results": None
        }
        if use_web:
            result["web_results"] = {
                "status": "available",
                "note": "Kueri regulasi dapat dikombinasikan dengan knowledge_search namespace 'legal_regulations'."
            }
        return result
    
    async def check_compliance(self, document: str, regulation: str = "UU 23/2014") -> Dict[str, Any]:
        """Tool: Check dokumen compliance terhadap regulasi tertentu."""
        system_prompt = f"""Anda adalah compliance checker untuk regulasi {regulation}.
        Analisis dokumen dan identifikasi:
        1. Bagian yang compliant
        2. Bagian yang tidak compliant
        3. Missing requirements
        4. Rekomendasi perbaikan"""
        
        prompt = f"""Analisis compliance dokumen berikut terhadap {regulation}:
        
        Dokumen:
        {document[:3000]}...
        
        Berikan hasil dalam format JSON murni:
        {{
            "compliance_score": 0.0-1.0,
            "is_compliant": true/false,
            "compliant_items": ["..."],
            "non_compliant_items": ["..."],
            "missing_requirements": ["..."],
            "recommendations": ["..."]
        }}
        """
        
        llm_result = await self.llm.generate(prompt, system_prompt)
        
        if llm_result.get('success'):
            try:
                raw = llm_result['content'].strip()
                if raw.startswith("```json"):
                    raw = raw[7:-3].strip()
                elif raw.startswith("```"):
                    raw = raw[3:-3].strip()
                analysis = json.loads(raw)
                return {
                    "success": True,
                    "compliance": analysis,
                    "regulation": regulation,
                    "model_used": llm_result.get('model_used')
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to parse LLM response: {e}",
                    "raw": llm_result.get('content')
                }
        
        return {
            "success": False,
            "error": llm_result.get('error', 'LLM generation failed')
        }

    async def evaluate_regulation_doctrine(
        self,
        regulation_text_or_ref: str,
        regulation_title: str = "Regulasi Teruji",
        metadata_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Tool: Evaluasi Yuridis Komprehensif berbasis Multi-Dimension Reasoning Graph (6 Dimensi & Preseden)."""
        from agents.profiles.legal.processors.dimension_router_node import run_multidimensional_analysis
        return await run_multidimensional_analysis(
            regulation_text_or_ref=regulation_text_or_ref,
            regulation_title=regulation_title,
            metadata_override=metadata_override,
        )

    def ingest_document(
        self,
        file_path: str,
        max_pages: int = 50,
        force_ocr: bool = False,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Tool: Multi-tier document ingestion (PDF Digital ➔ docTR OCR ➔ Tesseract) dengan cache terisolasi."""
        from agents.profiles.legal.processors.document_ingestion import ingest_legal_document
        return ingest_legal_document(
            file_path=file_path,
            max_pages=max_pages,
            force_ocr=force_ocr,
            use_cache=use_cache
        )

    def visualize_radar(
        self,
        dimension_scores: Dict[str, float],
        title: str = "Peta Keseimbangan Doktrin Hukum 6-Dimensi",
        width: int = 600,
        height: int = 500,
    ) -> Dict[str, Any]:
        """Tool: Menghasilkan visualisasi Radar Chart SVG 6-Dimensi Doktrin."""
        from agents.profiles.legal.processors.doctrine_visualizer import generate_svg_radar_chart
        svg_content = generate_svg_radar_chart(
            scores=dimension_scores,
            title=title,
            width=width,
            height=height
        )
        return {
            "success": True,
            "title": title,
            "scores": dimension_scores,
            "svg": svg_content
        }

    def verify_statutory(
        self,
        parent_law_query: str,
        derived_regulation_clause: str
    ) -> Dict[str, Any]:
        """Tool: Verifikasi keselarasan norma delegasi terhadap teks otentik UU induk via Knowledge RAG."""
        from agents.profiles.legal.processors.statutory_rag_verifier import verify_delegation_scope
        return verify_delegation_scope(
            parent_law_query=parent_law_query,
            derived_regulation_clause=derived_regulation_clause
        )

    def verify_correspondence(
        self,
        keywords: List[str],
        draft_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tool: Penyelarasan draf regulasi terhadap arsip korespondensi, SE kementerian, dan surat fasilitasi."""
        from agents.profiles.legal.processors.correspondence_verifier import find_related_correspondence
        results = find_related_correspondence(keywords=keywords, draft_title=draft_title)
        return {
            "success": True,
            "keywords": keywords,
            "total_matches": len(results),
            "correspondence": results
        }

    def verify_policy_code(
        self,
        regulation_text: str,
        codebase_root: Optional[str] = None,
        target_symbol: Optional[str] = None,
        custom_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tool: Policy-as-Code alignment verifier untuk formula matematis & logika bisnis pada source code via AST."""
        from agents.profiles.legal.processors.policy_as_code_verifier import (
            extract_regulatory_formulas,
            verify_code_alignment
        )
        formulas = extract_regulatory_formulas(regulation_text)
        alignment = verify_code_alignment(
            formulas,
            code_snippet_or_symbols=custom_code,
            codebase_root=Path(codebase_root) if codebase_root else None,
            target_symbol=target_symbol
        )
        return {
            "success": True,
            "formulas_extracted": formulas,
            "alignment_check": alignment
        }

    def analyze_dependencies(
        self,
        regulation_text: str
    ) -> Dict[str, Any]:
        """Tool: Membangun Normative Cross-Article Dependency Tree dan menghitung Blast Radius amandemen."""
        from agents.profiles.legal.processors.cross_article_dependency import build_normative_dependency_graph
        graph = build_normative_dependency_graph(regulation_text)
        return {
            "success": True,
            "dependency_graph": graph
        }

    def patch_clause(
        self,
        regulation_text: str,
        target_article: str,
        new_clause_text: str,
        target_ayat: Optional[str] = None,
        rationale: str = "Perbaikan redaksional rekomendasi Legal Agent (Anti-Ultra Vires)"
    ) -> Dict[str, Any]:
        """Tool: Melakukan structured/AST-like patching klausul pasal tanpa merusak hierarki regulasi."""
        from agents.profiles.legal.processors.legal_drafting_patcher import patch_legal_clause
        return patch_legal_clause(
            regulation_text=regulation_text,
            target_article=target_article,
            new_clause_text=new_clause_text,
            target_ayat=target_ayat,
            rationale=rationale
        )

    def search_tier2_precedents(
        self,
        query: str,
        top_k: int = 5,
        bidang_filter: Optional[str] = None,
        min_similarity: float = 0.15
    ) -> Dict[str, Any]:
        """Tool: Pencarian dinamis Tier 2 Vector RAG terhadap ratusan putusan MA & MK pada namespace 'putusan_pengadilan'."""
        from agents.profiles.legal.processors.tier2_precedent_vector_ingestor import search_tier2_precedents
        results = search_tier2_precedents(
            query=query,
            top_k=top_k,
            bidang_filter=bidang_filter,
            min_score=min_similarity
        )
        return {
            "success": True,
            "query": query,
            "total_matches": len(results),
            "precedents": results
        }

    def monitor_lifecycle(
        self,
        regulation_text: str,
        regulation_title: str = "Regulasi",
        base_date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tool: Analisis dan monitoring pasal peralihan, tenggat transisi, serta masa berlaku regulasi."""
        from agents.profiles.legal.processors.regulation_lifecycle_monitor import extract_transitional_deadlines
        deadlines = extract_transitional_deadlines(
            regulation_text=regulation_text,
            regulation_title=regulation_title,
            base_date_str=base_date_str
        )
        return {
            "success": True,
            "regulation_title": regulation_title,
            "total_deadlines": len(deadlines),
            "deadlines": deadlines
        }

    def dispatch_alert(
        self,
        regulation_title: str,
        dimension_findings: Dict[str, Any],
        target_phone: Optional[str] = None,
        force_send: bool = False
    ) -> Dict[str, Any]:
        """Tool: Mengirimkan Instant WhatsApp Red Alert jika terdeteksi cacat hukum materiil atau ultra vires."""
        from agents.profiles.legal.processors.legal_alert_dispatcher import (
            should_trigger_red_alert,
            format_whatsapp_red_alert,
            dispatch_whatsapp_red_alert
        )
        triggered = should_trigger_red_alert(dimension_findings) or force_send
        alert_msg = format_whatsapp_red_alert(regulation_title, dimension_findings)
        send_result = None
        if triggered:
            send_result = dispatch_whatsapp_red_alert(
                regulation_title=regulation_title,
                dimension_findings=dimension_findings,
                target_phone=target_phone
            )
        return {
            "triggered": triggered,
            "alert_message": alert_msg,
            "dispatch_status": send_result
        }

    async def comprehensive_audit(
        self,
        file_path_or_text: str,
        regulation_title: str = "Regulasi Teruji",
        metadata_override: Optional[Dict[str, Any]] = None,
        run_code_verifier: bool = True,
        send_red_alert: bool = True
    ) -> Dict[str, Any]:
        """Tool: End-to-end full legal audit pipeline (Ingestion ➔ 6D Graph ➔ Statutory/Memos RAG ➔ Code Check ➔ Canvas ➔ Alert)."""
        # 1. Ingestion jika file_path diberikan
        raw_text = file_path_or_text
        ingest_meta = {}
        is_potential_path = len(file_path_or_text) < 500 and "\n" not in file_path_or_text
        if is_potential_path and (Path(file_path_or_text).exists() or any(file_path_or_text.endswith(ext) for ext in ['.pdf', '.docx', '.txt', '.md'])):
            from agents.profiles.legal.processors.document_ingestion import ingest_legal_document
            ingest_res = ingest_legal_document(file_path_or_text)
            if ingest_res.get("success"):
                raw_text = ingest_res.get("text", "")
                ingest_meta = ingest_res.get("metadata", {})

        # 2. Multi-Dimension Reasoning Graph
        from agents.profiles.legal.processors.dimension_router_node import run_multidimensional_analysis
        doctrine_results = await run_multidimensional_analysis(
            regulation_text_or_ref=raw_text,
            regulation_title=regulation_title,
            metadata_override=metadata_override,
        )

        # 3. Policy-as-Code Verifier
        code_check = None
        if run_code_verifier:
            code_check = self.verify_policy_code(raw_text)

        # 4. Dependency Graph Analysis
        dep_graph = self.analyze_dependencies(raw_text)

        # 5. Red Alert Dispatcher
        alert_res = None
        if send_red_alert and doctrine_results.get("two_pass_decision", {}).get("pass2_triggered"):
            alert_res = self.dispatch_alert(
                regulation_title=regulation_title,
                dimension_findings=doctrine_results.get("synthesis", {})
            )

        return {
            "success": True,
            "regulation_title": regulation_title,
            "ingestion_metadata": ingest_meta,
            "doctrine_analysis": doctrine_results,
            "policy_as_code": code_check,
            "dependency_graph": dep_graph,
            "alert_dispatch": alert_res,
        }


# Global tool instance
legal_tools = LegalTools()


# ─────────────────────────────────────────────────────────────
# STANDALONE MCP FUNCTION EXPORTS
# ─────────────────────────────────────────────────────────────

async def legal_verify_spm(spm_data: Dict) -> Dict[str, Any]:
    """MCP Tool: Verify SPM classification and minimum service standards."""
    return await legal_tools.verify_spm_classification(spm_data)


async def legal_research(query: str, use_web: bool = True) -> Dict[str, Any]:
    """MCP Tool: Research regulation from local knowledge base and web."""
    return await legal_tools.research_regulation(query, use_web)


async def legal_check_compliance(document: str, regulation: str = "UU 23/2014") -> Dict[str, Any]:
    """MCP Tool: Check document compliance against reference legislation."""
    return await legal_tools.check_compliance(document, regulation)


async def legal_evaluate_doctrine(
    regulation_text_or_ref: str,
    regulation_title: str = "Regulasi Teruji",
    metadata_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """MCP Tool: Comprehensive Multi-Dimension Legal Doctrine Analysis (6 Dimensions + Precedents + Conditional Pass 2)."""
    return await legal_tools.evaluate_regulation_doctrine(
        regulation_text_or_ref=regulation_text_or_ref,
        regulation_title=regulation_title,
        metadata_override=metadata_override
    )


def legal_ingest_document(
    file_path: str,
    max_pages: int = 50,
    force_ocr: bool = False,
    use_cache: bool = True
) -> Dict[str, Any]:
    """MCP Tool: Multi-Tier Legal Document Ingestion (Digital PDF ➔ docTR OCR ➔ Tesseract) with isolated cache."""
    return legal_tools.ingest_document(
        file_path=file_path,
        max_pages=max_pages,
        force_ocr=force_ocr,
        use_cache=use_cache
    )


def legal_visualize_radar(
    dimension_scores: Dict[str, float],
    title: str = "Peta Keseimbangan Doktrin Hukum 6-Dimensi",
    width: int = 600,
    height: int = 500,
) -> Dict[str, Any]:
    """MCP Tool: Generate interactive SVG 6-Dimension Radar Chart for legal balance presentation."""
    return legal_tools.visualize_radar(
        dimension_scores=dimension_scores,
        title=title,
        width=width,
        height=height
    )


def legal_verify_statutory(
    parent_law_query: str,
    derived_regulation_clause: str
) -> Dict[str, Any]:
    """MCP Tool: Cross-reference and verify statutory authority and delegation against parent laws via Knowledge RAG."""
    return legal_tools.verify_statutory(
        parent_law_query=parent_law_query,
        derived_regulation_clause=derived_regulation_clause
    )


def legal_verify_correspondence(
    keywords: List[str],
    draft_title: Optional[str] = None
) -> Dict[str, Any]:
    """MCP Tool: Cross-reference regulatory draft against historical correspondence pool, ministerial circulars (SE), and gubernatorial facilitation notes."""
    return legal_tools.verify_correspondence(
        keywords=keywords,
        draft_title=draft_title
    )


def legal_verify_policy_code(
    regulation_text: str,
    codebase_root: Optional[str] = None,
    target_symbol: Optional[str] = None,
    custom_code: Optional[str] = None
) -> Dict[str, Any]:
    """MCP Tool: Policy-as-Code alignment verifier for regulatory formulas and algorithms against source code AST."""
    return legal_tools.verify_policy_code(
        regulation_text=regulation_text,
        codebase_root=codebase_root,
        target_symbol=target_symbol,
        custom_code=custom_code
    )


def legal_analyze_dependencies(
    regulation_text: str
) -> Dict[str, Any]:
    """MCP Tool: Build normative cross-article dependency tree and calculate amendment blast radius."""
    return legal_tools.analyze_dependencies(
        regulation_text=regulation_text
    )


def legal_patch_clause(
    regulation_text: str,
    target_article: str,
    new_clause_text: str,
    target_ayat: Optional[str] = None,
    rationale: str = "Perbaikan redaksional rekomendasi Legal Agent (Anti-Ultra Vires)"
) -> Dict[str, Any]:
    """MCP Tool: Safe AST/structural legal drafting patcher for modifying specific clauses without corrupting formatting."""
    return legal_tools.patch_clause(
        regulation_text=regulation_text,
        target_article=target_article,
        new_clause_text=new_clause_text,
        target_ayat=target_ayat,
        rationale=rationale
    )


def legal_monitor_lifecycle(
    regulation_text: str,
    regulation_title: str = "Regulasi",
    base_date_str: Optional[str] = None
) -> Dict[str, Any]:
    """MCP Tool: Extract and monitor transitional provisions, deadlines, and expiration dates of regulations."""
    return legal_tools.monitor_lifecycle(
        regulation_text=regulation_text,
        regulation_title=regulation_title,
        base_date_str=base_date_str
    )


def legal_dispatch_alert(
    regulation_title: str,
    dimension_findings: Dict[str, Any],
    target_phone: Optional[str] = None,
    force_send: bool = False
) -> Dict[str, Any]:
    """MCP Tool: Dispatch instant WhatsApp Red Alert if ultra vires or severe legal defects are detected."""
    return legal_tools.dispatch_alert(
        regulation_title=regulation_title,
        dimension_findings=dimension_findings,
        target_phone=target_phone,
        force_send=force_send
    )


async def legal_comprehensive_audit(
    file_path_or_text: str,
    regulation_title: str = "Regulasi Teruji",
    metadata_override: Optional[Dict[str, Any]] = None,
    run_code_verifier: bool = True,
    send_red_alert: bool = True
) -> Dict[str, Any]:
    """MCP Tool: End-to-end full legal audit pipeline (Ingestion ➔ 6D Graph ➔ Statutory/Memos RAG ➔ Code Check ➔ Canvas ➔ Alert)."""
    return await legal_tools.comprehensive_audit(
        file_path_or_text=file_path_or_text,
        regulation_title=regulation_title,
        metadata_override=metadata_override,
        run_code_verifier=run_code_verifier,
        send_red_alert=send_red_alert
    )


def legal_search_tier2_precedents(
    query: str,
    top_k: int = 5,
    bidang_filter: Optional[str] = None,
    min_similarity: float = 0.15
) -> Dict[str, Any]:
    """MCP Tool: Search Tier 2 dynamic vector repository of court precedents (MA & MK) under 'putusan_pengadilan'."""
    return legal_tools.search_tier2_precedents(
        query=query,
        top_k=top_k,
        bidang_filter=bidang_filter,
        min_similarity=min_similarity
    )


# ─── TASK-131: 7 Pilar DIM v2.0 — New MCP Tools ─────────────────────────────

def legal_ast_parse(
    regulation_text: str,
    title: str = "Peraturan Perundang-undangan",
    instrument_type: str = "PERDA_KABKOTA",
    level_hierarki: int = 7,
    issuer: str = "Unknown",
    year: Optional[int] = None,
    number: Optional[str] = None,
    build_cross_refs: bool = True
) -> Dict[str, Any]:
    """MCP Tool [Pilar 1 & 2]: Parse teks regulasi menjadi LegalDocument AST terstruktur.
    Menghasilkan pohon hirarki Bab→Pasal→Ayat→Huruf beserta cross-reference DAG."""
    try:
        from agents.profiles.legal.parsers.legal_ast_parser import parse_regulation_text
        from agents.profiles.legal.parsers.norm_transformation_engine import build_cross_reference_graph
        doc = parse_regulation_text(
            regulation_text=regulation_text,
            title=title,
            instrument_type=instrument_type,
            level_hierarki=level_hierarki,
            issuer=issuer,
            year=year,
            number=number
        )
        if build_cross_refs:
            doc = build_cross_reference_graph(doc)
        return {
            "success": True,
            "doc_id": doc.get("doc_id"),
            "total_bab": doc["metadata"]["total_bab"],
            "total_pasal": doc["metadata"]["total_pasal"],
            "total_ayat": doc["metadata"]["total_ayat"],
            "total_cross_refs": len(doc.get("cross_references", [])),
            "legal_doc": doc
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def legal_lint_editorial(
    regulation_text: str,
    title: str = "Peraturan",
    instrument_type: str = "PERDA_KABKOTA"
) -> Dict[str, Any]:
    """MCP Tool [Pilar 2]: Audit redaksional: PUEBI, typo, glosarium, cross-ref, style guide UU 12/2011."""
    try:
        from agents.profiles.legal.parsers.legal_ast_parser import parse_regulation_text
        from agents.profiles.legal.parsers.norm_transformation_engine import build_cross_reference_graph
        from agents.profiles.legal.parsers.editorial_linter import run_full_editorial_audit
        doc = parse_regulation_text(regulation_text, title=title, instrument_type=instrument_type)
        doc = build_cross_reference_graph(doc)
        report = run_full_editorial_audit(doc)
        return {"success": True, "editorial_report": report}
    except Exception as e:
        return {"success": False, "error": str(e)}


def legal_transform_clause(
    regulation_text: str,
    operation: str,
    article_id: str,
    rationale: str = "",
    new_text: str = "",
    clause_number: Optional[str] = None,
    split_plan: Optional[List[Dict[str, Any]]] = None,
    merge_article_ids: Optional[List[str]] = None,
    merged_number: Optional[int] = None,
    title: str = "Peraturan"
) -> Dict[str, Any]:
    """MCP Tool [Pilar 1]: Transformasi norma struktural.
    
    Operations: UBAH_SEBAGIAN | HAPUS | PECAH | GABUNG | RENUMBER_ALL
    """
    try:
        from agents.profiles.legal.parsers.legal_ast_parser import parse_regulation_text, serialize_to_markdown
        from agents.profiles.legal.parsers.norm_transformation_engine import (
            build_cross_reference_graph, amendment_mapping, delete_article,
            split_article, merge_articles, renumber_all_articles
        )
        doc = parse_regulation_text(regulation_text, title=title)
        doc = build_cross_reference_graph(doc)

        op = operation.upper()
        if op == "UBAH_SEBAGIAN":
            result = amendment_mapping(doc, article_id, clause_number, new_text, rationale)
        elif op == "HAPUS":
            result = delete_article(doc, article_id, rationale)
        elif op == "PECAH":
            result = split_article(doc, article_id, split_plan or [], rationale)
        elif op == "GABUNG":
            result = merge_articles(doc, merge_article_ids or [], merged_number or 0, article_id, rationale)
        elif op == "RENUMBER_ALL":
            result = renumber_all_articles(doc, rationale=rationale)
        else:
            return {"success": False, "error": f"Operasi tidak dikenal: '{operation}'"}

        if result.get("success") and "doc" in result:
            result["updated_text"] = serialize_to_markdown(result["doc"])
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def legal_disposition_matrix(
    regulation_text: str,
    disposition_list: List[Dict[str, Any]],
    title: str = "Peraturan",
    output_format: str = "summary"
) -> Dict[str, Any]:
    """MCP Tool [Pilar 6]: Kelola matriks disposisi DIM per pasal.
    
    Args:
        disposition_list: [{article_id, disposition, issue_summary, legal_basis, ...}]
        output_format: 'summary' | 'markdown_table' | 'full'
    """
    try:
        from agents.profiles.legal.parsers.legal_ast_parser import parse_regulation_text
        from agents.profiles.legal.parsers.norm_transformation_engine import build_cross_reference_graph
        from agents.profiles.legal.parsers.dim_disposition_engine import (
            batch_set_dispositions, get_dim_summary, format_dim_table_markdown
        )
        doc = parse_regulation_text(regulation_text, title=title)
        doc = build_cross_reference_graph(doc)
        batch_result = batch_set_dispositions(doc, disposition_list)
        updated_doc = batch_result.get("doc", doc)
        dim_summary = get_dim_summary(updated_doc)

        result = {
            "success": True,
            "total_processed": batch_result.get("total_processed", 0),
            "errors": batch_result.get("errors", []),
            "dim_summary": dim_summary,
            "dim_entries": batch_result.get("dim_entries", [])
        }
        if output_format == "markdown_table":
            result["dim_table_markdown"] = format_dim_table_markdown(updated_doc)
        elif output_format == "full":
            result["dim_table_markdown"] = format_dim_table_markdown(updated_doc)
            result["legal_doc"] = updated_doc
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── TASK-131: Pilar 3, 4, 5, 7 — New MCP Tools ─────────────────────────────

def legal_verify_hierarchy(
    regulation_text: str,
    instrument_type: str = "PERDA_KABKOTA",
    level_hierarki: int = 7,
    title: str = "Peraturan"
) -> Dict[str, Any]:
    """MCP Tool [Pilar 3]: Validasi hierarki regulasi (UU 12/2011) + klasifikasi Non-Statutory.
    
    Memeriksa kesesuaian jenis instrumen dengan level hierarki dan mendeteksi
    potensi ultra vires materi muatan.
    """
    try:
        from agents.profiles.legal.parsers.legal_ast_parser import parse_regulation_text
        from agents.profiles.legal.parsers.norm_transformation_engine import build_cross_reference_graph
        from agents.profiles.legal.parsers.hierarchy_validator import (
            classify_instrument_type, validate_hierarchy_compliance, run_full_hierarchy_audit
        )
        doc = parse_regulation_text(regulation_text, title=title, instrument_type=instrument_type, level_hierarki=level_hierarki)
        doc = build_cross_reference_graph(doc)
        result = run_full_hierarchy_audit(doc)
        return {"success": True, "hierarchy_audit": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def legal_verify_jurisdiction(
    regulation_text: str,
    primary_kl: str,
    instrument_type: str = "PERDA_KABKOTA",
    generate_skb: bool = False,
    skb_participating_kl: Optional[List[str]] = None,
    skb_title: Optional[str] = None
) -> Dict[str, Any]:
    """MCP Tool [Pilar 4]: Analisis batas kewenangan portofolio K/L & generator SKB.
    
    Mendeteksi irisan kewenangan antar-K/L (UU 23/2014) dan menghasilkan
    template Peraturan Bersama/SKB jika diperlukan.
    """
    try:
        from agents.profiles.legal.parsers.jurisdiction_analyzer import (
            detect_portfolio_overlap, generate_skb_framework
        )
        overlap = detect_portfolio_overlap(regulation_text, primary_kl, instrument_type)
        result: Dict[str, Any] = {"success": True, "portfolio_analysis": overlap}
        
        if generate_skb and skb_participating_kl:
            skb = generate_skb_framework(
                regulation_title=skb_title or "Peraturan Bersama",
                subject_matter=f"koordinasi penyelenggaraan urusan {primary_kl}",
                participating_kl=skb_participating_kl
            )
            result["skb_framework"] = skb
        
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def legal_mandate_check(
    regulation_text: str,
    title: str = "Peraturan",
    check_spbe: bool = True,
    check_fiscal: bool = True,
    check_facility: bool = True
) -> Dict[str, Any]:
    """MCP Tool [Pilar 5]: Validasi mandat SPBE, keterkaitan fiskal APBD/RKP, dan standar fasilitas.
    
    Memvalidasi keselarasan regulasi dengan Perpres SPBE 95/2018, kejelasan
    sumber anggaran, dan rujukan ke standar nasional fasilitas/kapasitas.
    """
    try:
        from agents.profiles.legal.parsers.instrument_mandate_mapper import (
            check_spbe_alignment, analyze_fiscal_statutory_linkage, map_facility_capacity_standards
        )
        result: Dict[str, Any] = {"success": True, "title": title}
        if check_spbe:
            result["spbe_alignment"] = check_spbe_alignment(regulation_text, title)
        if check_fiscal:
            result["fiscal_linkage"] = analyze_fiscal_statutory_linkage(regulation_text, title)
        if check_facility:
            result["facility_standards"] = map_facility_capacity_standards(regulation_text)
        
        total_issues = (
            result.get("spbe_alignment", {}).get("total_issues", 0) +
            result.get("fiscal_linkage", {}).get("total_issues", 0) +
            result.get("facility_standards", {}).get("total_gaps", 0)
        )
        result["total_pilar5_issues"] = total_issues
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def legal_governance_loop(
    regulation_text: str,
    title: str = "Peraturan",
    instrument_type: str = "PERBUP",
    year: Optional[int] = None,
    compliance_issues: Optional[List[Dict[str, Any]]] = None,
    ex_post_findings: Optional[List[str]] = None,
    current_iteration: int = 1
) -> Dict[str, Any]:
    """MCP Tool [Pilar 7]: Monitoring siklus hidup, deteksi sunset trigger, dan closed-loop revision.
    
    Mengevaluasi apakah regulasi memerlukan review/revisi berdasarkan:
    - Usia regulasi (≥5 tahun → evaluasi berkala)
    - Tenggat waktu peralihan yang terlewat
    - Temuan kepatuhan & dampak lapangan (ex-post RIA+)
    
    Guardrail: Maksimal 2 iterasi otomatis. Iterasi ke-3 → Human Review wajib.
    """
    try:
        from agents.profiles.legal.parsers.legal_ast_parser import parse_regulation_text
        from agents.profiles.legal.parsers.norm_transformation_engine import build_cross_reference_graph
        from agents.profiles.legal.parsers.instrument_mandate_mapper import (
            extract_lifecycle_mandates, detect_sunset_trigger, generate_closed_loop_revision
        )
        doc = parse_regulation_text(regulation_text, title=title, instrument_type=instrument_type, year=year)
        doc = build_cross_reference_graph(doc)
        
        lifecycle = extract_lifecycle_mandates(doc)
        sunset = detect_sunset_trigger(doc)
        closed_loop = generate_closed_loop_revision(doc, compliance_issues, ex_post_findings, current_iteration=current_iteration)
        
        return {
            "success": True,
            "pilar_7_lifecycle": lifecycle,
            "pilar_7_sunset_trigger": sunset,
            "pilar_7_closed_loop": closed_loop
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# === Tools Baru (v5.0 — TASK-133: Dual-Track Legal Agent di atas MAF) ===
# ============================================================================

def legal_deontic_verify(norm_text: str) -> Dict[str, Any]:
    """MCP Tool [Track A]: Verifikasi kepatuhan 4 modalitas deontik dan deteksi diksi ambigu/terlarang."""
    try:
        from agents.profiles.legal.drafting.deontic_logic_verifier import DeonticLogicVerifier
        result = DeonticLogicVerifier.verify_clause(norm_text)
        return {
            "success": True,
            "modalitas": result.primary_modality.value,
            "detected_modalities": [m.value for m in result.detected_modalities],
            "apakah_sah": result.is_valid,
            "kesalahan": result.findings,
            "rekomendasi": result.recommendation,
            "ambiguous_terms": result.ambiguous_terms
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def legal_anatomy_validate(regulation_text: str) -> Dict[str, Any]:
    """MCP Tool [Track A]: Validasi anatomi peraturan perundang-undangan (236 Kaidah Lampiran II UU 12/2011)."""
    try:
        from agents.profiles.legal.drafting.legislative_drafter import LegislativeDrafter
        result = LegislativeDrafter.validate_anatomy(regulation_text)
        return {
            "success": True,
            "apakah_valid": result.get("is_ready_for_harmonisasi", False),
            "skor_kepatuhan": result.get("anatomy_score", 0),
            "status": result.get("status", ""),
            "kesalahan": result.get("findings", []),
            "deontic_compliance": result.get("deontic_compliance", {})
        }
    except Exception as e:
        return {"success": False, "error": str(e)}



def legal_naskah_akademik_generate(
        judul: str,
        jenis: str,
        urgensi: str,
        identifikasi_masalah: List[str],
        sasaran_jangkauan: str,
        landasan_filosofis: str,
        landasan_sosiologis: str,
        landasan_yuridis: str
) -> Dict[str, Any]:
    """MCP Tool [Track A]: Generator Sistematika 6 Bab Naskah Akademik (Lampiran I UU 12/2011)."""
    try:
        from agents.profiles.legal.drafting.naskah_akademik_generator import (
            NaskahAkademikGenerator,
            NaskahAkademikInput
        )
        inp = NaskahAkademikInput(
            title=judul,
            region_or_institution=jenis,
            background_issue=urgensi,
            objectives=identifikasi_masalah,
            filosofis_point=landasan_filosofis,
            sosiologis_point=landasan_sosiologis,
            yuridis_point=landasan_yuridis,
            scope_subjects=[sasaran_jangkauan]
        )
        na_doc = NaskahAkademikGenerator.generate(inp)
        md = NaskahAkademikGenerator.render_markdown(na_doc)
        bab_keys = [k for k in na_doc.keys() if k.startswith("bab_")]
        return {
            "success": True,
            "judul": na_doc["judul"],
            "sistematika_terpenuhi": bab_keys,
            "markdown_document": md
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def legal_harmonization_matrix(rancangan_text: str, jenis_peraturan: str = "PERDA") -> Dict[str, Any]:
    """MCP Tool [Track A]: Matriks 5 Kolom E-Harmonisasi SE Menkumham 2022 & Validasi Pasal 58 UU 13/2022."""
    try:
        import re
        from agents.profiles.legal.drafting.harmonization_gatekeeper import HarmonizationGatekeeper
        articles_data = []
        parts = re.split(r"(Pasal\s+\d+)", rancangan_text)
        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                ref = parts[i]
                body = parts[i+1].strip() if i+1 < len(parts) else ""
                articles_data.append({"ref": ref, "text": f"{ref}\n{body}"})
        else:
            articles_data.append({"ref": "Pasal 1", "text": rancangan_text.strip()})

        report = HarmonizationGatekeeper.audit_and_generate_matrix(
            title=f"Rancangan {jenis_peraturan}",
            pemrakarsa="Pemerintah Daerah",
            articles=articles_data
        )
        md = HarmonizationGatekeeper.render_matrix_markdown(report)
        has_sanksi_violation = any(
            "sanksi" in str(r.catatan_harmonisasi).lower() or "pidana" in str(r.catatan_harmonisasi).lower()
            for r in report.matrix_rows
        )

        return {
            "success": True,
            "jenis_peraturan": jenis_peraturan,
            "status_harmonisasi": report.status_label,
            "total_norma_dianalisis": report.total_articles,
            "readiness_index": report.readiness_index,
            "is_cleared": report.is_cleared,
            "pelanggaran_sanksi_perda": has_sanksi_violation or (not report.is_cleared),
            "markdown_report": md
        }
    except Exception as e:
        return {"success": False, "error": str(e)}




def legal_opinion_irac(
        judul_kasus: str,
        pemohon: str,
        nomor_memo: str,
        fakta: str,
        issues: List[Dict[str, Any]],
        rules: List[Dict[str, Any]],
        fakta_detail: Optional[Dict[str, Any]] = None,
        aspek_keuangan: Optional[Dict[str, Any]] = None,
        jenjang: str = "Ahli Madya"
) -> Dict[str, Any]:
    """MCP Tool [Track B]: Penyusunan Legal Opinion IRAC, AUPB Shield (UU 30/2014), dan Deteksi Tipikor/Kerugian Negara."""
    try:
        from agents.profiles.legal.counsel.opinion_agent import LegalOpinionAgent, LegalIssue, RuleReference
        agent = LegalOpinionAgent(jenjang=jenjang)
        parsed_issues = [
            LegalIssue(
                issue_id=i.get("id", f"ISS-{idx}"),
                pertanyaan_hukum=i.get("pertanyaan", ""),
                kategori=i.get("kategori", "substansi"),
                pihak_terkait=i.get("pihak", [])
            )
            for idx, i in enumerate(issues, start=1)
        ]
        parsed_rules = [
            RuleReference(
                peraturan=r.get("peraturan", ""),
                pasal=r.get("pasal", ""),
                bunyi_norma=r.get("bunyi", ""),
                tingkat_hierarki=r.get("hierarki", "UU/Perppu")
            )
            for r in rules
        ]
        result = agent.generate_opinion(
            judul_kasus=judul_kasus,
            pemohon=pemohon,
            nomor_memo=nomor_memo,
            fakta_peristiwa=fakta,
            issues=parsed_issues,
            rules=parsed_rules,
            fakta_kasus_detail=fakta_detail,
            aspek_keuangan=aspek_keuangan
        )
        md = agent.render_markdown(result)
        return {
            "success": True,
            "nomor_memo": result.nomor_memo,
            "kesimpulan": result.kesimpulan_dan_rekomendasi["kesimpulan_umum"],
            "level_risiko_keuangan": result.risiko_kerugian_negara["level_risiko"],
            "executive_summary": result.executive_summary,
            "markdown_document": md
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def legal_contract_vetting(
        judul_kontrak: str,
        nomor_draf: str,
        para_pihak: List[str],
        nilai_kontrak: float,
        jenis_kontrak: str,
        draf_pasal: Dict[str, str],
        jenjang: str = "Ahli Madya"
) -> Dict[str, Any]:
    """MCP Tool [Track B]: Audit & Vetting Klausul Kontrak PBJ (Perpres 12/2021) & PKS (1266 KUHPerdata, Celah BPK/APIP)."""
    try:
        from agents.profiles.legal.counsel.contract_agent import ContractVettingAgent
        agent = ContractVettingAgent(jenjang=jenjang)
        result = agent.audit_draf_kontrak(
            judul_kontrak=judul_kontrak,
            nomor_draf=nomor_draf,
            para_pihak=para_pihak,
            nilai_kontrak=nilai_kontrak,
            jenis_kontrak=jenis_kontrak,
            draf_pasal=draf_pasal
        )
        md = agent.render_markdown(result)
        return {
            "success": True,
            "nomor_draf": result.nomor_draf,
            "skor_kesehatan": result.skor_kesehatan_kontrak,
            "status_kelayakan": result.status_kelayakan,
            "total_temuan_risiko": len(result.temuan_risiko),
            "celah_audit_bpk": result.celah_audit_bpk_apip,
            "executive_summary": result.executive_summary,
            "markdown_document": md
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def legal_litigation_advocacy(
        nomor_perkara: str,
        judul_sengketa: str,
        instansi_tergugat: str,
        penggugat: str,
        forum: str,
        kronologi: List[Dict[str, str]],
        bukti: List[Dict[str, str]],
        fakta_formal: Dict[str, Any],
        jr_data: Optional[Dict[str, Any]] = None,
        jenjang: str = "Ahli Madya"
) -> Dict[str, Any]:
    """MCP Tool [Track B]: Berkas Advokasi Litigasi PTUN (Pasal 100 Bukti, Eksepsi 90 Hari) & Judicial Review MKRI/MA."""
    try:
        from agents.profiles.legal.counsel.litigation_agent import LitigationAdvocacyAgent
        agent = LitigationAdvocacyAgent(jenjang=jenjang)
        case = agent.construct_case_defense(
            nomor_perkara=nomor_perkara,
            judul_sengketa=judul_sengketa,
            instansi_tergugat=instansi_tergugat,
            penggugat=penggugat,
            forum=forum,
            kronologi_data=kronologi,
            bukti_data=bukti,
            fakta_formal=fakta_formal,
            jr_data=jr_data
        )
        md = agent.render_markdown(case)
        return {
            "success": True,
            "nomor_perkara": case.nomor_perkara,
            "prospek_kemenangan": case.prospek_kemenangan,
            "total_eksepsi": len(case.daftar_eksepsi),
            "total_alat_bukti": len(case.matriks_alat_bukti),
            "executive_summary": case.executive_summary,
            "markdown_document": md
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def register_tools(server=None) -> None:
    """Mendaftarkan seluruh tools Legal Agent Suite ke registry global MCP Unified."""
    from execution.registry import registry
    # === Tools Eksisting (v3.0) ===
    registry.register(name="legal_evaluate_doctrine")(legal_evaluate_doctrine)
    registry.register(name="legal_comprehensive_audit")(legal_comprehensive_audit)
    registry.register(name="legal_ingest_document")(legal_ingest_document)
    registry.register(name="legal_visualize_radar")(legal_visualize_radar)
    registry.register(name="legal_verify_statutory")(legal_verify_statutory)
    registry.register(name="legal_verify_correspondence")(legal_verify_correspondence)
    registry.register(name="legal_verify_policy_code")(legal_verify_policy_code)
    registry.register(name="legal_analyze_dependencies")(legal_analyze_dependencies)
    registry.register(name="legal_patch_clause")(legal_patch_clause)
    registry.register(name="legal_search_tier2_precedents")(legal_search_tier2_precedents)
    registry.register(name="legal_monitor_lifecycle")(legal_monitor_lifecycle)
    registry.register(name="legal_dispatch_alert")(legal_dispatch_alert)
    registry.register(name="legal_check_compliance")(legal_check_compliance)
    registry.register(name="legal_research")(legal_research)
    registry.register(name="legal_verify_spm")(legal_verify_spm)
    # === Tools Eksisting (v4.0 — TASK-131: 7 Pilar DIM v2.0) ===
    registry.register(name="legal_ast_parse")(legal_ast_parse)
    registry.register(name="legal_lint_editorial")(legal_lint_editorial)
    registry.register(name="legal_transform_clause")(legal_transform_clause)
    registry.register(name="legal_disposition_matrix")(legal_disposition_matrix)
    registry.register(name="legal_verify_hierarchy")(legal_verify_hierarchy)
    registry.register(name="legal_verify_jurisdiction")(legal_verify_jurisdiction)
    registry.register(name="legal_mandate_check")(legal_mandate_check)
    registry.register(name="legal_governance_loop")(legal_governance_loop)
    # === Tools Baru (v5.0 — TASK-133: Dual-Track Legal Agent di atas MAF) ===
    registry.register(name="legal_deontic_verify")(legal_deontic_verify)
    registry.register(name="legal_anatomy_validate")(legal_anatomy_validate)
    registry.register(name="legal_naskah_akademik_generate")(legal_naskah_akademik_generate)
    registry.register(name="legal_harmonization_matrix")(legal_harmonization_matrix)
    registry.register(name="legal_opinion_irac")(legal_opinion_irac)
    registry.register(name="legal_contract_vetting")(legal_contract_vetting)
    registry.register(name="legal_litigation_advocacy")(legal_litigation_advocacy)


try:
    register_tools()
except Exception:
    pass

