"""
MCP Tools untuk Document AI Service.
Namespace: docai

Tools:
  - docai_extract_tables    : ekstraksi tabel dari PDF via Google Document AI
  - docai_get_processor_info: info konfigurasi processor
  - docai_export_result     : export ulang hasil ekstraksi ke Markdown/JSONL
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from execution.registry import registry

from .config import load_config, is_configured, ConfigError
from .engine import DocumentAIEngine, DocumentAIError
from .pdf_handler import PDFProcessingError
from .exporter import export_to_markdown, export_to_jsonl, export_both, ExportError


def register_tools(server=None) -> None:
    """
    Register Document AI tools ke registry.

    Args:
        server: Unused parameter, kept for backward compatibility.
                The actual registration uses the global registry.
    """
    @registry.register(name="docai_extract_tables")
    async def extract_tables(
        file_path: str = None,
        pages: str = "all",
        output_format: str = "both",
        output_dir: str = None,
    ) -> dict:
        """
        Ekstraksi tabel dari file PDF menggunakan Google Cloud Document AI.

        Generic parser: membaca skema tabel apa saja tanpa hardcode nama kolom.
        Mendukung page range fleksibel ("all", "4-7", "1,3,5").

        Args:
            file_path: Path absolut ke file PDF lokal.
            pages: Rentang halaman ("all", "4-7", "1,3,5"). Default: "all".
            output_format: Format output ("markdown", "jsonl", "both"). Default: "both" (markdown + jsonl).
            output_dir: Direktori output. Default: storage/raw_documents/processed/documentai (sesuai kebijakan isolasi data). Bisa di-override via env DOCAI_OUTPUT_DIR.

        Returns:
            { "status", "output_files", "tables_count", "tables_preview", "error" }
        """
        try:
            # Validate input
            if not file_path:
                return {"status": "error", "message": "file_path is required"}

            path = Path(file_path)
            if not path.exists():
                return {"status": "error", "message": f"File not found: {file_path}"}

            if path.suffix.lower() != ".pdf":
                return {"status": "error", "message": f"Not a PDF file: {file_path}"}

            # Validate output format
            if output_format not in ("markdown", "jsonl", "both"):
                return {"status": "error", "message": f"Invalid output_format: {output_format}. Use 'markdown', 'jsonl', or 'both'."}

            # Check GCP config
            if not is_configured():
                return {
                    "status": "error",
                    "message": "GCP configuration missing. Set GCP_PROJECT_ID and DOCAI_PROCESSOR_ID environment variables.",
                }

            # Determine output directory
            # Default: storage/raw_documents/processed/documentai (sesuai kebijakan isolasi data)
            # Bisa di-override via env DOCAI_OUTPUT_DIR atau parameter output_dir
            if output_dir is None:
                output_dir = os.getenv(
                    "DOCAI_OUTPUT_DIR",
                    os.path.join(
                        os.path.expanduser("~"),
                        "MCP", "storage", "raw_documents", "processed", "documentai"
                    )
                )
            os.makedirs(output_dir, exist_ok=True)

            # Extract tables
            engine = DocumentAIEngine()
            tables = engine.extract_tables(file_path, pages)

            if not tables:
                return {
                    "status": "success",
                    "message": "No tables found in document",
                    "tables_count": 0,
                    "output_files": [],
                }

            # Export
            base_output = os.path.join(output_dir, f"{path.stem}_extracted")
            output_files = []

            if output_format in ("markdown", "both"):
                md_path = export_to_markdown(tables, f"{base_output}.md", str(path), pages)
                output_files.append(md_path)

            if output_format in ("jsonl", "both"):
                jsonl_path = export_to_jsonl(tables, f"{base_output}.jsonl", str(path), pages)
                output_files.append(jsonl_path)

            # Build preview (first table, first 5 rows)
            preview = []
            if tables:
                first = tables[0]
                preview = {
                    "headers": first.get("headers", []),
                    "rows_preview": first.get("rows", [])[:5],
                    "total_rows": len(first.get("rows", [])),
                }

            return {
                "status": "success",
                "message": f"Extracted {len(tables)} table(s) from {path.name}",
                "tables_count": len(tables),
                "output_files": output_files,
                "tables_preview": preview,
            }

        except ConfigError as e:
            return {"status": "error", "message": str(e)}
        except PDFProcessingError as e:
            return {"status": "error", "message": str(e)}
        except DocumentAIError as e:
            return {"status": "error", "message": str(e)}
        except ExportError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {e}"}

    @registry.register(name="docai_get_processor_info")
    async def get_processor_info() -> dict:
        """
        Mendapatkan informasi konfigurasi Document AI processor.

        Returns:
            { "status", "project_id", "location", "processor_id", "processor_name", "configured" }
        """
        try:
            cfg = load_config()
            configured = is_configured()

            info = {
                "status": "success",
                "configured": configured,
                "project_id": cfg.project_id or "(not set)",
                "location": cfg.location,
                "processor_id": cfg.processor_id or "(not set)",
            }

            if configured:
                info["processor_name"] = cfg.processor_name

            return info

        except Exception as e:
            return {"status": "error", "message": str(e)}

    @registry.register(name="docai_export_result")
    async def export_result(
        tables_json: str = None,
        output_path: str = None,
            output_format: str = "both",
    ) -> dict:
        """
        Export hasil ekstraksi tabel (JSON) ke Markdown/JSONL.

        Args:
            tables_json: JSON string berisi list of tables (headers + rows).
            output_path: Path output (tanpa ekstensi).
            output_format: Format output ("markdown", "jsonl", "both"). Default: "both".

        Returns:
            { "status", "output_files", "error" }
        """
        try:
            import json

            if not tables_json:
                return {"status": "error", "message": "tables_json is required"}

            if not output_path:
                return {"status": "error", "message": "output_path is required"}

            tables = json.loads(tables_json)
            if not isinstance(tables, list):
                return {"status": "error", "message": "tables_json must be a JSON array"}

            output_files = []

            if output_format in ("markdown", "both"):
                md_path = export_to_markdown(tables, f"{output_path}.md")
                output_files.append(md_path)

            if output_format in ("jsonl", "both"):
                jsonl_path = export_to_jsonl(tables, f"{output_path}.jsonl")
                output_files.append(jsonl_path)

            return {
                "status": "success",
                "message": f"Exported {len(tables)} table(s)",
                "output_files": output_files,
            }

        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"Invalid JSON: {e}"}
        except ExportError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {e}"}