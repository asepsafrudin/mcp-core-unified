"""
Office Admin Agent - Business Administration Specialist

Agent untuk business/administrative tasks:
- Document management (DOCX, XLSX, PPTX, PDF)
- Template rendering & document generation
- Format conversion (docx↔pdf↔xlsx↔md)
- Meeting scheduling & calendar management
- Email correspondence (Gmail integration)
- Batch document processing

Perbedaan dari AdminAgent:
- AdminAgent: System Administration (infrastructure, monitoring, security)
- OfficeAdminAgent: Business Administration (documents, scheduler, correspondence)
"""

import logging
from typing import Dict, Any, List
from ..base import BaseAgent, AgentProfile, AgentCapability, register_agent
from core.task import Task, TaskResult

logger = logging.getLogger(__name__)


@register_agent
class OfficeAdminAgent(BaseAgent):
    """
    Office Administration Specialist — Fully Operational.

    Capabilities:
    - Document CRUD (DOCX, XLSX, PPTX read/write/edit)
    - Spreadsheet operations (formulas, charts, pivots, formatting)
    - Presentation management (create, add slides)
    - PDF handling (extract text, convert, info)
    - Template rendering (Jinja2-based DOCX templates)
    - Semantic document conversion (DOCX/XLSX → structured Markdown)
    - Cross-format conversion (docx↔pdf↔xlsx↔pptx)
    - Meeting scheduling (via scheduler tools)
    - Email/Calendar integration (via Google Workspace)
    - Batch document processing
    """

    @property
    def profile(self) -> AgentProfile:
        return AgentProfile(
            name="office_admin_agent",
            description="Office administration specialist (documents, scheduler, correspondence, templates)",
            domain="office_admin",
            capabilities={
                AgentCapability.TOOL_USE,
                AgentCapability.SKILL_COMPOSITION,
                AgentCapability.COMMUNICATION,
                AgentCapability.PLANNING,
            },
            preferred_skills=[
                "document_manager",
                "semantic_converter",
                "template_injection",
            ],
            tools_whitelist=[
                # === DOCX Tools ===
                "read_docx", "write_docx", "extract_text_docx", "edit_docx",
                "search_replace_docx", "apply_paragraph_style_docx",
                "add_header_footer_docx", "insert_image_docx",
                "add_hyperlink_docx", "add_list_docx", "set_page_setup_docx",
                "add_toc_docx", "merge_table_cells_docx",
                "modify_table_structure_docx", "style_table_cell_docx",
                # === XLSX Tools ===
                "read_xlsx", "write_xlsx", "extract_data_xlsx", "edit_xlsx",
                "format_xlsx", "import_csv_xlsx", "export_to_csv_xlsx",
                "set_cell_formula_xlsx", "create_pivot_xlsx", "add_chart_xlsx",
                "apply_conditional_formatting_xlsx", "add_data_validation_xlsx",
                "calculate_formulas_xlsx", "apply_filter_sort_xlsx",
                "merge_cells_xlsx", "unmerge_cells_xlsx", "freeze_panes_xlsx",
                # === PDF Tools ===
                "convert_to_pdf", "extract_text_pdf", "get_pdf_info",
                # === PPTX Tools ===
                "read_pptx", "write_pptx", "extract_text_pptx", "add_slide_pptx",
                # === Semantic Converter ===
                "convert_docx_to_markdown", "convert_xlsx_to_markdown",
                "defragment_docx_xml",
                # === Template Tools ===
                "render_docx_template",
                # === Scheduler ===
                "scheduler_create_job", "scheduler_list_jobs",
                "scheduler_get_status",
                # === Google Workspace ===
                "gmail_list_messages", "gmail_send_message",
                "calendar_list_events",
            ],
            max_concurrent_tasks=5,
            timeout_seconds=300.0
        )

    def can_handle(self, task: Task) -> bool:
        """
        Check if this agent can handle office admin tasks.

        Handles:
        - Document operations (docx, xlsx, pptx, pdf, template, convert)
        - Scheduling (meeting, calendar, appointment)
        - Correspondence (email, letter, mailroom)
        """
        task_type = task.type.lower()
        office_tasks = {
            "schedule", "calendar", "meeting", "appointment",
            "correspondence", "email", "letter", "mailroom",
            "document", "docx", "xlsx", "pptx", "pdf",
            "template", "convert", "spreadsheet", "presentation",
            "nota_dinas", "surat", "laporan",
        }
        if any(ot in task_type for ot in office_tasks):
            return True

        # Check payload keywords
        payload_str = str(task.payload).lower()
        payload_keywords = {
            "docx", "xlsx", "pptx", "pdf", "document", "spreadsheet",
            "template", "convert", "schedule", "meeting", "email",
            "nota dinas", "surat", "laporan", "rapat",
        }
        return any(kw in payload_str for kw in payload_keywords)

    async def execute(self, task: Task) -> TaskResult:
        """
        Execute office admin tasks by routing to appropriate tools and skills.
        """
        action = task.payload.get("action", "").lower()
        task_type = task.type.lower()
        payload = task.payload

        try:
            # === 1. DOCX Operations ===
            if action in ("read_docx", "write_docx", "edit_docx", "extract_text_docx") or "docx" in task_type:
                return await self._handle_docx(action or task_type, payload, task.id)

            # === 2. XLSX Operations ===
            elif action in ("read_xlsx", "write_xlsx", "edit_xlsx", "extract_data_xlsx",
                            "format_xlsx", "create_pivot", "add_chart") or "xlsx" in task_type or "spreadsheet" in task_type:
                return await self._handle_xlsx(action or task_type, payload, task.id)

            # === 3. PPTX Operations ===
            elif action in ("read_pptx", "write_pptx", "add_slide") or "pptx" in task_type or "presentation" in task_type:
                return await self._handle_pptx(action or task_type, payload, task.id)

            # === 4. PDF Operations ===
            elif action in ("extract_text_pdf", "convert_to_pdf", "get_pdf_info") or "pdf" in task_type:
                return await self._handle_pdf(action or task_type, payload, task.id)

            # === 5. Template Rendering ===
            elif action in ("render_template", "template") or "template" in task_type:
                return await self._handle_template(payload, task.id)

            # === 6. Semantic Conversion (to Markdown) ===
            elif action in ("convert_to_markdown", "semantic_convert", "to_markdown") or "markdown" in task_type:
                return await self._handle_semantic_convert(payload, task.id)

            # === 7. Format Conversion ===
            elif action in ("convert", "convert_format") or "convert" in task_type:
                return await self._handle_format_convert(payload, task.id)

            # === 8. Meeting Scheduling ===
            elif action in ("schedule_meeting", "create_schedule", "list_schedules") or "schedule" in task_type or "meeting" in task_type:
                return await self._handle_scheduling(action or task_type, payload, task.id)

            # === 9. Email / Correspondence ===
            elif action in ("send_email", "list_emails", "correspondence") or "email" in task_type or "correspondence" in task_type:
                return await self._handle_email(action or task_type, payload, task.id)

            # === 10. Calendar ===
            elif action in ("list_events", "calendar") or "calendar" in task_type:
                return await self._handle_calendar(payload, task.id)

            # === 11. Batch Document Processing (via DocumentManagerSkill) ===
            elif action in ("batch", "batch_process"):
                return await self._handle_batch(payload, task.id)

            # === Fallback: use DocumentManagerSkill for generic operations ===
            else:
                return await self._handle_document_manager(action or task_type, payload, task.id)

        except Exception as e:
            logger.error(f"OfficeAdminAgent error: {e}", exc_info=True)
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code="OFFICE_ADMIN_ERROR"
            )

    # ─── Handler Methods ────────────────────────────────────────────

    async def _handle_docx(self, action: str, payload: dict, task_id: str) -> TaskResult:
        """Handle DOCX operations."""
        from tools.office import (
            read_docx, write_docx, extract_text_docx, edit_docx,
            search_replace_docx, add_header_footer_docx,
            insert_image_docx, set_page_setup_docx
        )

        file_path = payload.get("file_path", "")

        if "read" in action:
            result = await read_docx(file_path)
        elif "write" in action or "create" in action:
            result = await write_docx(
                file_path=file_path,
                content=payload.get("content", []),
                title=payload.get("title"),
                author=payload.get("author")
            )
        elif "edit" in action:
            result = await edit_docx(
                file_path=file_path,
                edits=payload.get("edits", [])
            )
        elif "extract" in action:
            result = await extract_text_docx(file_path)
        elif "search_replace" in action:
            result = await search_replace_docx(
                file_path=file_path,
                search_text=payload.get("search_text", ""),
                replace_text=payload.get("replace_text", "")
            )
        else:
            result = await read_docx(file_path)

        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": f"docx_{action}"}
        )

    async def _handle_xlsx(self, action: str, payload: dict, task_id: str) -> TaskResult:
        """Handle XLSX operations."""
        from tools.office import (
            read_xlsx, write_xlsx, extract_data_xlsx, edit_xlsx,
            format_xlsx, create_pivot_xlsx, add_chart_xlsx,
            set_cell_formula_xlsx
        )

        file_path = payload.get("file_path", "")

        if "read" in action:
            result = await read_xlsx(file_path, sheet_name=payload.get("sheet_name"))
        elif "write" in action or "create" in action:
            result = await write_xlsx(
                file_path=file_path,
                data=payload.get("data", []),
                sheet_name=payload.get("sheet_name", "Sheet1")
            )
        elif "edit" in action:
            result = await edit_xlsx(
                file_path=file_path,
                edits=payload.get("edits", [])
            )
        elif "extract" in action:
            result = await extract_data_xlsx(file_path)
        elif "format" in action:
            result = await format_xlsx(
                file_path=file_path,
                formatting=payload.get("formatting", {})
            )
        elif "pivot" in action:
            result = await create_pivot_xlsx(
                file_path=file_path,
                **payload.get("pivot_config", {})
            )
        elif "chart" in action:
            result = await add_chart_xlsx(
                file_path=file_path,
                **payload.get("chart_config", {})
            )
        elif "formula" in action:
            result = await set_cell_formula_xlsx(
                file_path=file_path,
                cell=payload.get("cell", "A1"),
                formula=payload.get("formula", "")
            )
        else:
            result = await read_xlsx(file_path)

        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": f"xlsx_{action}"}
        )

    async def _handle_pptx(self, action: str, payload: dict, task_id: str) -> TaskResult:
        """Handle PPTX operations."""
        from tools.office import read_pptx, write_pptx, extract_text_pptx, add_slide_pptx

        file_path = payload.get("file_path", "")

        if "read" in action:
            result = await read_pptx(file_path)
        elif "write" in action or "create" in action:
            result = await write_pptx(
                file_path=file_path,
                slides=payload.get("slides", [])
            )
        elif "extract" in action:
            result = await extract_text_pptx(file_path)
        elif "add_slide" in action or "slide" in action:
            result = await add_slide_pptx(
                file_path=file_path,
                slide_data=payload.get("slide_data", {})
            )
        else:
            result = await read_pptx(file_path)

        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": f"pptx_{action}"}
        )

    async def _handle_pdf(self, action: str, payload: dict, task_id: str) -> TaskResult:
        """Handle PDF operations."""
        from tools.office import extract_text_pdf, convert_to_pdf, get_pdf_info

        file_path = payload.get("file_path", "")

        if "extract" in action:
            result = await extract_text_pdf(file_path)
        elif "convert" in action:
            result = await convert_to_pdf(
                file_path=file_path,
                output_path=payload.get("output_path")
            )
        elif "info" in action:
            result = await get_pdf_info(file_path)
        else:
            result = await extract_text_pdf(file_path)

        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": f"pdf_{action}"}
        )

    async def _handle_template(self, payload: dict, task_id: str) -> TaskResult:
        """Handle template rendering."""
        from tools.office import render_docx_template

        result = await render_docx_template(
            template_path=payload.get("template_path", ""),
            context_data=payload.get("context_data", {}),
            output_path=payload.get("output_path")
        )
        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": "render_template"}
        )

    async def _handle_semantic_convert(self, payload: dict, task_id: str) -> TaskResult:
        """Handle semantic conversion to structured Markdown."""
        from tools.office import convert_docx_to_markdown, convert_xlsx_to_markdown

        file_path = payload.get("file_path", "")
        ext = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""

        if ext in ("docx", "doc"):
            result = await convert_docx_to_markdown(file_path)
        elif ext in ("xlsx", "xls", "csv"):
            result = await convert_xlsx_to_markdown(file_path)
        else:
            return TaskResult.failure_result(
                task_id=task_id,
                error=f"Unsupported file extension for semantic conversion: .{ext}",
                error_code="UNSUPPORTED_FORMAT"
            )

        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": "semantic_convert"}
        )

    async def _handle_format_convert(self, payload: dict, task_id: str) -> TaskResult:
        """Handle cross-format document conversion."""
        from tools.office import convert_to_pdf, convert_docx_to_markdown, convert_xlsx_to_markdown

        file_path = payload.get("file_path", "")
        target_format = payload.get("target_format", "pdf").lower()
        output_path = payload.get("output_path")

        if target_format == "pdf":
            result = await convert_to_pdf(file_path=file_path, output_path=output_path)
        elif target_format in ("md", "markdown"):
            ext = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""
            if ext in ("docx", "doc"):
                result = await convert_docx_to_markdown(file_path)
            elif ext in ("xlsx", "xls"):
                result = await convert_xlsx_to_markdown(file_path)
            else:
                return TaskResult.failure_result(
                    task_id=task_id,
                    error=f"Cannot convert .{ext} to markdown",
                    error_code="UNSUPPORTED_CONVERSION"
                )
        else:
            return TaskResult.failure_result(
                task_id=task_id,
                error=f"Unsupported target format: {target_format}",
                error_code="UNSUPPORTED_FORMAT"
            )

        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": "format_convert"}
        )

    async def _handle_scheduling(self, action: str, payload: dict, task_id: str) -> TaskResult:
        """Handle meeting scheduling via scheduler tools."""
        try:
            from scheduler.tools import get_scheduler_tools
        except ImportError:
            return TaskResult.failure_result(
                task_id=task_id,
                error="Scheduler module not available",
                error_code="SCHEDULER_UNAVAILABLE"
            )

        from execution import registry

        if "list" in action:
            result = await registry.execute("scheduler_list_jobs", {
                "status": payload.get("status", "active")
            })
        elif "create" in action or "schedule" in action:
            result = await registry.execute("scheduler_create_job", {
                "name": payload.get("name", "Meeting"),
                "description": payload.get("description", ""),
                "schedule_type": payload.get("schedule_type", "once"),
                "scheduled_time": payload.get("scheduled_time"),
                "cron_expression": payload.get("cron_expression"),
                "action_type": payload.get("action_type", "notification"),
                "action_config": payload.get("action_config", {}),
            })
        elif "status" in action:
            result = await registry.execute("scheduler_get_status", {})
        else:
            result = await registry.execute("scheduler_list_jobs", {"status": "active"})

        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": f"schedule_{action}"}
        )

    async def _handle_email(self, action: str, payload: dict, task_id: str) -> TaskResult:
        """Handle email correspondence via Google Workspace."""
        try:
            from integrations.google_workspace.tools import gmail_list_messages, gmail_send_message
        except ImportError:
            return TaskResult.failure_result(
                task_id=task_id,
                error="Google Workspace integration not available",
                error_code="GMAIL_UNAVAILABLE"
            )

        if "send" in action:
            result = await gmail_send_message(
                to=payload.get("to", ""),
                subject=payload.get("subject", ""),
                body=payload.get("body", ""),
                cc=payload.get("cc"),
                bcc=payload.get("bcc")
            )
        else:
            result = await gmail_list_messages(
                query=payload.get("query", ""),
                max_results=payload.get("max_results", 10)
            )

        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": f"email_{action}"}
        )

    async def _handle_calendar(self, payload: dict, task_id: str) -> TaskResult:
        """Handle calendar operations via Google Workspace."""
        try:
            from integrations.google_workspace.tools import calendar_list_events
        except ImportError:
            return TaskResult.failure_result(
                task_id=task_id,
                error="Google Workspace Calendar integration not available",
                error_code="CALENDAR_UNAVAILABLE"
            )

        result = await calendar_list_events(
            max_results=payload.get("max_results", 10),
            time_min=payload.get("time_min"),
            time_max=payload.get("time_max")
        )
        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": "calendar_list"}
        )

    async def _handle_batch(self, payload: dict, task_id: str) -> TaskResult:
        """Handle batch document processing via DocumentManagerSkill."""
        from skills.office import DocumentManagerSkill

        skill = DocumentManagerSkill()
        batch_task = Task(
            type="document_batch",
            payload={
                "action": "batch",
                "operations": payload.get("operations", []),
            }
        )
        return await skill.execute(batch_task)

    async def _handle_document_manager(self, action: str, payload: dict, task_id: str) -> TaskResult:
        """Fallback: delegate to DocumentManagerSkill for generic operations."""
        from skills.office import DocumentManagerSkill

        skill = DocumentManagerSkill()
        doc_task = Task(
            type="document_operation",
            payload={
                "action": action if action else "read",
                "file_path": payload.get("file_path", ""),
                **{k: v for k, v in payload.items() if k not in ("action", "file_path")},
            }
        )
        return await skill.execute(doc_task)
