"""
Knowledge Tools for MCP Unified.
Exposes RAG Engine and Ingestion capabilities as MCP tools.
"""

import json
import asyncio
from typing import Optional, List, Dict, Any, Union
from mcp.server.fastmcp import Context
from pathlib import Path

from knowledge.rag_engine import RAGEngine
from knowledge.ingestion.extractors.xlsx_extractor import XlsxExtractor
from integrations.google_workspace.client import get_google_client
from observability.logger import logger

# Singleton RAG Engine
rag_engine = RAGEngine()
_rag_initialized = False

async def get_rag_engine():
    global _rag_initialized
    if not _rag_initialized:
        await rag_engine.initialize()
        _rag_initialized = True
    return rag_engine

async def knowledge_search(query: str, namespace: str = "default", top_k: int = 5) -> str:
    """
    Search the knowledge base using semantic search.
    Returns relevant context from documents and spreadsheets.
    """
    try:
        rag = await get_rag_engine()
        result = await rag.query(query, namespace=namespace, top_k=top_k)
        
        return json.dumps({
            "success": True,
            "query": query,
            "context": result.context,
            "sources": result.sources,
            "namespace": namespace
        }, indent=2)
    except Exception as e:
        logger.error(f"knowledge_search_tool_failed: {e}")
        return json.dumps({"success": False, "error": str(e)})

async def knowledge_ingest_text(
    content: str,
    doc_id: str,
    namespace: str = "shared_tech",
    metadata: Dict[str, Any] = None,
    approval_token: Optional[str] = None
) -> str:
    """
    Ingest plain text into the knowledge base (Two-step staging gate).
    Requires explicit approval_token='APPROVED' to embed into pgvector.
    Namespace 'default' is strictly prohibited.
    """
    try:
        ns = (namespace or "").strip()
        if not ns or ns.lower() == "default":
            return json.dumps({
                "success": False,
                "error": "AKSES DITOLAK: Namespace 'default' dilarang keras sesuai Zero-Leakage Policy (Invariant #7). Gunakan namespace identitas resmi 'puu:{domain}:{agent}' atau 'shared_*'."
            }, indent=2)

        # Gate Staging Sisi Server (Pertahanan Lapis Ganda)
        if approval_token != "APPROVED":
            return json.dumps({
                "success": False,
                "status": "STAGING_PENDING_APPROVAL",
                "doc_id": doc_id,
                "namespace": ns,
                "character_count": len(content),
                "preview": content[:300] + ("..." if len(content) > 300 else ""),
                "message": "Dokumen ditahan di buffer staging. DILARANG meng-embed ke pgvector tanpa konfirmasi eksplisit pengguna di chat. Tampilkan pratinjau ini ke pengguna, minta persetujuan, lalu panggil kembali dengan parameter approval_token='APPROVED' jika disetujui."
            }, indent=2)

        rag = await get_rag_engine()
        success = await rag.add_document(
            doc_id=doc_id,
            content=content,
            metadata=metadata or {},
            namespace=ns
        )
        return json.dumps({"success": success, "doc_id": doc_id, "namespace": ns})
    except Exception as e:
        logger.error(f"knowledge_ingest_text_failed: {e}")
        return json.dumps({"success": False, "error": str(e)})

async def knowledge_ingest_spreadsheet(
    file_path: str,
    namespace: str = "shared_tech",
    approval_token: Optional[str] = None
) -> str:
    """
    Ingest an Excel (.xlsx) file into the knowledge base (Two-step staging gate).
    Requires explicit approval_token='APPROVED' to embed into pgvector.
    Namespace 'default' is strictly prohibited.
    """
    try:
        ns = (namespace or "").strip()
        if not ns or ns.lower() == "default":
            return json.dumps({
                "success": False,
                "error": "AKSES DITOLAK: Namespace 'default' dilarang keras sesuai Zero-Leakage Policy (Invariant #7). Gunakan namespace identitas resmi 'puu:{domain}:{agent}' atau 'shared_*'."
            }, indent=2)

        extractor = XlsxExtractor()
        extracted = await extractor.extract(file_path)

        if approval_token != "APPROVED":
            return json.dumps({
                "success": False,
                "status": "STAGING_PENDING_APPROVAL",
                "file_path": file_path,
                "namespace": ns,
                "sheet_count": extracted["metadata"]["sheet_count"],
                "character_count": len(extracted["text"]),
                "preview": extracted["text"][:300] + ("..." if len(extracted["text"]) > 300 else ""),
                "message": "Data spreadsheet ditahan di staging buffer. DILARANG meng-embed ke pgvector tanpa konfirmasi eksplisit pengguna di chat. Tampilkan pratinjau ini ke pengguna, minta persetujuan, lalu panggil kembali dengan parameter approval_token='APPROVED' jika disetujui."
            }, indent=2)
        
        rag = await get_rag_engine()
        doc_id = f"xlsx_{Path(file_path).stem}_{ns}"
        
        success = await rag.add_document(
            doc_id=doc_id,
            content=extracted["text"],
            metadata={
                "source_file": file_path,
                "file_type": "xlsx",
                "sheets": extracted["metadata"]["sheets"]
            },
            namespace=ns
        )
        
        return json.dumps({
            "success": success,
            "doc_id": doc_id,
            "namespace": ns,
            "sheet_count": extracted["metadata"]["sheet_count"]
        }, indent=2)
    except Exception as e:
        logger.error(f"knowledge_ingest_spreadsheet_failed: {e}")
        return json.dumps({"success": False, "error": str(e)})

async def knowledge_ingest_googlesheet(
    spreadsheet_id: str,
    range_name: str,
    namespace: str = "shared_tech",
    approval_token: Optional[str] = None
) -> str:
    """
    Ingest data from a Google Spreadsheet into the knowledge base (Two-step staging gate).
    Requires explicit approval_token='APPROVED' to embed into pgvector.
    Namespace 'default' is strictly prohibited.
    """
    try:
        ns = (namespace or "").strip()
        if not ns or ns.lower() == "default":
            return json.dumps({
                "success": False,
                "error": "AKSES DITOLAK: Namespace 'default' dilarang keras sesuai Zero-Leakage Policy (Invariant #7). Gunakan namespace identitas resmi 'puu:{domain}:{agent}' atau 'shared_*'."
            }, indent=2)

        client = get_google_client()
        sheets = client.sheets
        
        result = sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get("values", [])
        if not values or len(values) < 2:
            return json.dumps({"success": False, "error": "No data found in sheet (need at least header and one data row)"})

        headers = values[0]

        if approval_token != "APPROVED":
            return json.dumps({
                "success": False,
                "status": "STAGING_PENDING_APPROVAL",
                "spreadsheet_id": spreadsheet_id,
                "namespace": ns,
                "row_count": len(values) - 1,
                "headers": headers,
                "message": "Data Google Sheet ditahan di staging buffer. DILARANG meng-embed ke pgvector tanpa konfirmasi eksplisit pengguna di chat. Tampilkan pratinjau ini ke pengguna, minta persetujuan, lalu panggil kembali dengan parameter approval_token='APPROVED' jika disetujui."
            }, indent=2)
        rag = await get_rag_engine()
        ingested_count = 0
        
        for idx, row in enumerate(values[1:], 1):
            if not any(row): continue # Skip empty rows
            
            row_parts = []
            for i, val in enumerate(row):
                header = headers[i] if i < len(headers) else f"Col{i+1}"
                if val:
                    row_parts.append(f"{header}: {val}")
            
            row_text = " | ".join(row_parts)
            doc_id = f"gsheet_{spreadsheet_id[:8]}_{namespace}_row_{idx}"
            
            success = await rag.add_document(
                doc_id=doc_id,
                content=row_text,
                metadata={
                    "source": "google_sheets",
                    "spreadsheet_id": spreadsheet_id,
                    "range": range_name,
                    "row_index": idx
                },
                namespace=namespace
            )
            if success:
                ingested_count += 1
        
        return json.dumps({
            "success": True,
            "ingested_rows": ingested_count,
            "total_rows_processed": len(values) - 1,
            "namespace": namespace
        }, indent=2)
    except Exception as e:
        logger.error(f"knowledge_ingest_googlesheet_failed: {e}")
        return json.dumps({"success": False, "error": str(e)})

async def knowledge_list_namespaces() -> str:
    """
    List all available namespaces and their document counts.
    """
    try:
        rag = await get_rag_engine()
        namespaces = await rag.vector_store.list_namespaces()
        return json.dumps({"success": True, "namespaces": namespaces}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
