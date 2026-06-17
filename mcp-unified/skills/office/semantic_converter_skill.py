"""
Semantic Converter Skill — Fase 1: Orkestrasi Konversi Dokumen Semantik

Skill yang meng-orkestrasikan tool pengonversi dokumen pada layer Tools
untuk menghasilkan Clean Markdown dari dokumen Office (.docx, .xlsx).

Skill ini menyediakan 3 kemampuan utama:
    1. convert_document   — Auto-detect format dan konversi ke Markdown.
    2. batch_convert      — Konversi batch untuk banyak file sekaligus.
    3. convert_and_embed  — Konversi lalu langsung embed ke RAG/LTM (pgvector).

╔══════════════════════════════════════════════════════════════════════╗
║  CATATAN ARSITEKTUR:                                                ║
║  Skill ini memanggil Tools (layer 2), bukan sebaliknya.            ║
║  Dependensi: document_converter_tool (tool), knowledge.rag_engine  ║
║  Sesuai dengan hierarki: Agents → Skills → Tools → Core            ║
╚══════════════════════════════════════════════════════════════════════╝
"""
from pathlib import Path
from typing import Dict, List, Optional, Any

from skills.base import BaseSkill, SkillDefinition, SkillComplexity, register_skill
from core.task import Task, TaskResult

# Import tools (layer 2) — sesuai arsitektur 4-Layer
from tools.office.document_converter_tool import (
    convert_docx_to_markdown,
    convert_xlsx_to_markdown,
    defragment_docx_xml,
)


@register_skill
class SemanticConverterSkill(BaseSkill):
    """
    Skill untuk konversi dokumen Office ke Clean Markdown yang ramah LLM.

    Skill ini BERBEDA dari DocumentManagerSkill (yang ada di document_manager.py):
      - DocumentManagerSkill → Operasi CRUD dokumen (read, write, edit, analyze)
      - SemanticConverterSkill → KONVERSI FORMAT ke Markdown terstruktur untuk
        konsumsi LLM, termasuk defragmentasi XML dan embedding ke memori.

    Gunakan skill ini ketika agent perlu:
      - Membaca dokumen sebagai konteks untuk LLM
      - Menyiapkan dokumen untuk RAG pipeline
      - Mengonversi batch dokumen ke format yang bisa diproses AI
    """

    skill_name = "semantic_converter"
    skill_description = (
        "Konversi dokumen Office (.docx, .xlsx) ke Clean Markdown terstruktur "
        "yang ramah LLM, dengan dukungan defragmentasi XML dan embedding ke LTM."
    )
    skill_complexity = "complex"

    # Supported formats untuk Fase 1 (pptx/pdf → fase terpisah)
    SUPPORTED_EXTENSIONS = {'.docx', '.xlsx', '.xls'}

    @property
    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="semantic_converter",
            description=self.skill_description,
            complexity=SkillComplexity.COMPLEX,
            dependencies=[],
            tags=["document", "markdown", "semantic", "converter", "rag"],
        )

    async def execute(self, task: Task) -> TaskResult:
        """
        Entry point utama skill. Dispatch berdasarkan task.payload['action'].

        Payload yang didukung:
            action: 'convert' | 'batch_convert' | 'convert_and_embed'
            file_path: str (untuk action='convert' dan 'convert_and_embed')
            file_paths: List[str] (untuk action='batch_convert')
            namespace: str (untuk action='convert_and_embed', default='default')
            defragment: bool (opsional, default=False, jalankan defragmentasi XML)
            sampling_mode: str (untuk xlsx, default='head')
            max_rows: int (untuk xlsx, default=100)
        """
        action = task.payload.get('action', 'convert')

        try:
            if action == 'convert':
                result = await self.convert_document(
                    file_path=task.payload.get('file_path', ''),
                    defragment=task.payload.get('defragment', False),
                    sampling_mode=task.payload.get('sampling_mode', 'head'),
                    max_rows=task.payload.get('max_rows', 100),
                )
            elif action == 'batch_convert':
                result = await self.batch_convert(
                    file_paths=task.payload.get('file_paths', []),
                    defragment=task.payload.get('defragment', False),
                )
            elif action == 'convert_and_embed':
                result = await self.convert_and_embed(
                    file_path=task.payload.get('file_path', ''),
                    namespace=task.payload.get('namespace', 'default'),
                    defragment=task.payload.get('defragment', False),
                )
            else:
                return TaskResult.failure_result(
                    task_id=task.id,
                    error=f"Unknown action: {action}. Use: convert, batch_convert, convert_and_embed",
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
                    error=result.get('error', 'Unknown error'),
                    error_code="CONVERSION_ERROR"
                )

        except Exception as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code="SKILL_ERROR"
            )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def convert_document(
        self,
        file_path: str,
        defragment: bool = False,
        sampling_mode: str = 'head',
        max_rows: int = 100,
        sheet_name: Optional[str] = None,
        chunk_index: int = 0,
        chunk_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Auto-detect format berdasarkan ekstensi lalu konversi ke Clean Markdown.

        Args:
            file_path: Path absolut ke dokumen
            defragment: Jika True, jalankan defragmentasi XML sebelum konversi (DOCX)
            sampling_mode: Mode sampling untuk XLSX ('head', 'tail', 'sample', 'chunk', 'full')
            max_rows: Batas baris untuk XLSX sampling
            sheet_name: Nama sheet XLSX (None = sheet pertama)
            chunk_index: Index chunk untuk mode 'chunk'
            chunk_size: Ukuran chunk untuk mode 'chunk'

        Returns:
            Dict dengan kunci 'success', 'markdown', 'metadata', 'statistics', dll.
        """
        path = Path(file_path)

        if not path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        ext = path.suffix.lower()

        if ext not in self.SUPPORTED_EXTENSIONS:
            return {
                'success': False,
                'error': (
                    f'Format {ext} belum didukung pada Fase 1. '
                    f'Supported: {", ".join(sorted(self.SUPPORTED_EXTENSIONS))}. '
                    f'Dukungan .pptx/.pdf akan ditambahkan pada fase terpisah.'
                )
            }

        if ext == '.docx':
            # Opsional: defragmentasi XML split runs sebelum konversi
            defrag_result = None
            if defragment:
                defrag_result = defragment_docx_xml(file_path)

            result = convert_docx_to_markdown(file_path)

            if defrag_result:
                result['defragmentation'] = defrag_result

            return result

        elif ext in ('.xlsx', '.xls'):
            return convert_xlsx_to_markdown(
                file_path=file_path,
                sheet_name=sheet_name,
                max_rows=max_rows,
                sampling_mode=sampling_mode,
                chunk_index=chunk_index,
                chunk_size=chunk_size,
            )

        return {'success': False, 'error': f'Unhandled extension: {ext}'}

    async def batch_convert(
        self,
        file_paths: List[str],
        defragment: bool = False,
    ) -> Dict[str, Any]:
        """
        Konversi batch untuk banyak dokumen sekaligus.

        Args:
            file_paths: List path dokumen
            defragment: Jalankan defragmentasi XML untuk file DOCX

        Returns:
            Dict dengan ringkasan hasil konversi batch
        """
        results = []
        errors = []

        for fp in file_paths:
            try:
                result = await self.convert_document(
                    file_path=fp,
                    defragment=defragment,
                )
                results.append({
                    'file_path': fp,
                    'success': result.get('success', False),
                    'word_count': result.get('statistics', {}).get('word_count', 0),
                    'markdown_preview': result.get('markdown', '')[:200] + '...'
                        if result.get('markdown') else '',
                })
            except Exception as e:
                errors.append({'file_path': fp, 'error': str(e)})

        successful = sum(1 for r in results if r['success'])

        return {
            'success': True,
            'total_files': len(file_paths),
            'successful': successful,
            'failed': len(file_paths) - successful,
            'results': results,
            'errors': errors,
        }

    async def convert_and_embed(
        self,
        file_path: str,
        namespace: str = 'default',
        defragment: bool = False,
    ) -> Dict[str, Any]:
        """
        Konversi dokumen ke Markdown, lalu embed langsung ke RAG/LTM (pgvector).

        Menghubungkan Fase 1 (konversi semantik) dengan infrastruktur Fase 4
        (PostgreSQL pgvector) yang sudah siap.

        Args:
            file_path: Path dokumen
            namespace: Namespace untuk isolasi di pgvector
            defragment: Jalankan defragmentasi XML untuk DOCX

        Returns:
            Dict dengan hasil konversi + status embedding
        """
        # Step 1: Konversi ke Markdown
        convert_result = await self.convert_document(
            file_path=file_path,
            defragment=defragment,
        )

        if not convert_result.get('success'):
            return convert_result

        markdown = convert_result.get('markdown', '')
        if not markdown:
            return {
                'success': False,
                'error': 'Conversion succeeded but produced empty Markdown',
                'file_path': file_path,
            }

        # Step 2: Embed ke RAG Engine (jika tersedia)
        embedding_result = {'embedded': False, 'reason': 'RAG engine not initialized'}

        try:
            from knowledge.rag_engine import RAGEngine

            rag = RAGEngine()
            initialized = await rag.initialize()

            if initialized:
                doc_id = Path(file_path).stem
                metadata = convert_result.get('metadata', {})
                metadata['source_file'] = file_path
                metadata['conversion_method'] = convert_result.get('conversion_method', '')

                success = await rag.add_document(
                    doc_id=doc_id,
                    content=markdown,
                    metadata=metadata,
                    namespace=namespace,
                )

                embedding_result = {
                    'embedded': success,
                    'doc_id': doc_id,
                    'namespace': namespace,
                    'content_length': len(markdown),
                }

                await rag.close()
            else:
                embedding_result = {
                    'embedded': False,
                    'reason': 'Failed to initialize RAG engine (database not available?)',
                }

        except ImportError:
            embedding_result = {
                'embedded': False,
                'reason': 'knowledge.rag_engine module not available',
            }
        except Exception as e:
            embedding_result = {
                'embedded': False,
                'reason': f'Embedding failed: {str(e)}',
            }

        return {
            'success': True,
            'file_path': file_path,
            'markdown': markdown,
            'metadata': convert_result.get('metadata', {}),
            'statistics': convert_result.get('statistics', {}),
            'embedding': embedding_result,
        }


__all__ = ['SemanticConverterSkill']
