"""
Template Injection Skill — Fase 2: Pipeline Otomatisasi (Generative Templates)

Skill untuk pengisian template dokumen (.docx) dinas secara dinamis
menggunakan data terstruktur dari basis data PostgreSQL mcp_knowledge
atau payload JSON eksternal.
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional

from skills.base import BaseSkill, SkillDefinition, SkillComplexity, register_skill
from core.task import Task, TaskResult
from tools.office.template_tools import render_docx_template, validate_path


def format_tgl(d) -> str:
    """
    Format datetime/date object atau string ISO ke format tanggal Indonesia.
    Contoh: 2026-05-25 -> 25 Mei 2026
    """
    if not d:
        return "-"
        
    from datetime import date, datetime
    dt = None
    
    if isinstance(d, (date, datetime)):
        dt = d
    elif isinstance(d, str):
        try:
            dt = date.fromisoformat(d.split("T")[0])
        except Exception:
            return d
    else:
        return str(d)
        
    bulan_indo = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    return f"{dt.day:02d} {bulan_indo.get(dt.month, '')} {dt.year}"


@register_skill
class TemplateInjectionSkill(BaseSkill):
    """
    Skill untuk pengisian template dokumen dinas menggunakan docxtpl.
    Dapat mengambil data otomatis dari database PostgreSQL atau menerima context langsung.
    """
    
    skill_name = "template_injection"
    skill_description = (
        "Pengisian template dokumen (.docx) dinas secara otomatis menggunakan "
        "data terstruktur (JSON) atau data langsung dari database PostgreSQL mcp_knowledge."
    )
    skill_complexity = "complex"
    
    @property
    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="template_injection",
            description=self.skill_description,
            complexity=SkillComplexity.COMPLEX,
            dependencies=[],
            tags=["document", "template", "docxtpl", "mailmerge", "postgres"],
        )
        
    async def execute(self, task: Task) -> TaskResult:
        """
        Entry point utama skill. Dispatch berdasarkan task.payload['action'].
        
        Payload yang didukung:
            action: 'inject_from_db' | 'inject_from_json'
            template_path: str
            output_path: Optional[str] (path output lengkap, opsional untuk inject_from_db)
            unique_id: str (wajib jika action='inject_from_db')
            context: Dict[str, Any] (wajib jika action='inject_from_json')
        """
        action = task.payload.get('action', 'inject_from_db')
        template_path = task.payload.get('template_path', '')
        output_path = task.payload.get('output_path')
        
        try:
            if not template_path:
                return TaskResult.failure_result(
                    task_id=task.id,
                    error="template_path is required",
                    error_code="MISSING_PARAMETER"
                )
                
            if action == 'inject_from_db':
                unique_id = task.payload.get('unique_id', '')
                if not unique_id:
                    return TaskResult.failure_result(
                        task_id=task.id,
                        error="unique_id is required for action 'inject_from_db'",
                        error_code="MISSING_PARAMETER"
                    )
                result = await self.inject_template_from_db(
                    unique_id=unique_id,
                    template_path=template_path,
                    output_path=output_path
                )
            elif action == 'inject_from_json':
                context = task.payload.get('context')
                if context is None:
                    return TaskResult.failure_result(
                        task_id=task.id,
                        error="context dict is required for action 'inject_from_json'",
                        error_code="MISSING_PARAMETER"
                    )
                if not output_path:
                    return TaskResult.failure_result(
                        task_id=task.id,
                        error="output_path is required for action 'inject_from_json'",
                        error_code="MISSING_PARAMETER"
                    )
                result = await self.inject_template_from_json(
                    template_path=template_path,
                    output_path=output_path,
                    context=context
                )
            else:
                return TaskResult.failure_result(
                    task_id=task.id,
                    error=f"Unknown action: {action}. Use: inject_from_db, inject_from_json",
                    error_code="UNKNOWN_ACTION"
                )
                
            if result.get('success'):
                return TaskResult.success_result(
                    task_id=task.id,
                    data=result,
                    context={"skill": self.name}
                )
            else:
                return TaskResult.failure_result(
                    task_id=task.id,
                    error=result.get('error', 'Unknown error during rendering'),
                    error_code="RENDERING_ERROR"
                )
        except Exception as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code="SKILL_ERROR"
            )
            
    async def inject_template_from_db(
        self,
        unique_id: str,
        template_path: str,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query database mcp_knowledge, petakan kolom ke context template, dan render.
        
        Args:
            unique_id: ID surat unik di tabel surat_masuk_puu_internal
            template_path: Path absolut ke template .docx
            output_path: Path absolut untuk file output (.docx). Default ke /tmp/Disposisi_{agenda}.docx
            
        Returns:
            Dict berisi status sukses, output path, dan info data
        """
        from knowledge.config import get_knowledge_config
        import asyncpg
        
        config = get_knowledge_config()
        conn = await asyncpg.connect(config.database_url)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM surat_masuk_puu_internal WHERE unique_id = $1",
                unique_id
            )
            if not row:
                return {
                    'success': False,
                    'error': f"Data surat dengan unique_id '{unique_id}' tidak ditemukan di database."
                }
            data = dict(row)
        finally:
            await conn.close()
            
        # Pemetaan & Formatting data
        agenda_dispo = data.get('no_agenda_dispo') or '-'
        if isinstance(agenda_dispo, str) and not agenda_dispo.strip():
            agenda_dispo = '-'
            
        tgl_surat = format_tgl(data.get('tanggal_surat'))
        tgl_diterima = format_tgl(data.get('tanggal_diterima_puu'))
        if tgl_diterima == '-':
            # Layout placeholder kosong untuk tanggal diterima jika tidak terisi
            tgl_diterima = "                     /               / 2026"
            
        context = {
            "direktorat": data.get('dari') or '-',
            "nomor_nd": data.get('nomor_nd') or '-',
            "tanggal_surat": tgl_surat,
            "hal": data.get('hal') or '-',
            "tgl_diterima": tgl_diterima,
            "no_agenda_ses": agenda_dispo,
            "agenda_puu": data.get('agenda_puu') or agenda_dispo
        }
        
        # Tentukan output path default di /tmp jika tidak diisi
        if not output_path:
            safe_agenda = str(agenda_dispo).replace("/", "_")
            output_path = f"/tmp/Disposisi_{safe_agenda}.docx"
            
        # Render template
        render_result = render_docx_template(
            template_path=template_path,
            output_path=output_path,
            context=context
        )
        
        if render_result.get('success'):
            render_result['context_used'] = context
            render_result['database_record'] = {
                'id': data.get('id'),
                'unique_id': unique_id
            }
            
        return render_result
        
    async def inject_template_from_json(
        self,
        template_path: str,
        output_path: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Mengisi template secara langsung menggunakan parameter JSON context.
        """
        return render_docx_template(
            template_path=template_path,
            output_path=output_path,
            context=context
        )


__all__ = ['TemplateInjectionSkill']
