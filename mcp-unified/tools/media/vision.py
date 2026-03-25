"""
Vision Tools — Phase 6 Direct Registration

Image & PDF Analysis via Local Ollama.
Direct registration menggunakan @register_tool decorator.
"""
import asyncio
import base64
import json
import io
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from tools.file.path_utils import is_safe_path, validate_file_extension


# Configuration
VISION_MODEL = os.environ.get("MCP_VISION_MODEL", "llava")
OLLAMA_URL = "http://localhost:11434"
VISION_TIMEOUT = 60
ALLOWED_IMAGE_EXTENSIONS = frozenset(['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'])
MAX_IMAGE_SIZE = (1024, 1024)
MAX_PDF_PAGES = 50


async def _call_ollama_vision(image_base64: str, prompt: str, model: str = None) -> Optional[str]:
    """Panggil Ollama vision model dengan image base64."""
    target_model = model or VISION_MODEL
    payload = json.dumps({
        "model": target_model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False
    })
    
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s",
            "--max-time", str(VISION_TIMEOUT),
            "-X", "POST",
            f"{OLLAMA_URL}/api/generate",
            "-H", "Content-Type: application/json",
            "-d", payload,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=VISION_TIMEOUT + 5
        )
        
        if proc.returncode != 0:
            logger.error("ollama_vision_error", model=target_model, error=stderr.decode()[:200])
            return None
        
        response_data = json.loads(stdout)
        return response_data.get("response", "")
        
    except asyncio.TimeoutError:
        logger.error("ollama_vision_timeout", model=target_model, timeout=VISION_TIMEOUT)
        return None
    except Exception as e:
        logger.error("ollama_vision_failed", error=str(e))
        return None


def _image_to_base64(image_path: str) -> Optional[str]:
    """Load image, resize, convert ke base64."""
    try:
        from PIL import Image
        
        with Image.open(image_path) as img:
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            return base64.b64encode(buffer.getvalue()).decode()
            
    except Exception as e:
        logger.error("image_preprocessing_failed", path=image_path, error=str(e))
        return None


async def _save_vision_result(path: str, content: str, namespace: str, metadata: dict = None):
    """Helper: Simpan hasil vision ke long-term memory."""
    from memory.longterm import memory_save
    
    meta = metadata or {}
    meta["source"] = "vision_analysis"
    meta["file"] = path
    
    file_name = Path(path).name
    
    await memory_save(
        key=f"vision:{file_name}",
        content=content[:2000],
        metadata=meta,
        namespace=namespace
    )
    
    logger.info("vision_result_saved", file=file_name, namespace=namespace)


async def analyze_image_impl(
    image_path: str,
    prompt: str = "Describe this image in detail",
    namespace: str = "default",
    save_to_memory: bool = True,
    model: str = None
) -> Dict[str, Any]:
    """Analyze image menggunakan local vision model via Ollama."""
    if not is_safe_path(image_path):
        return {"success": False, "error": "Path outside allowed directories"}
    
    is_valid, ext_error = validate_file_extension(image_path, ALLOWED_IMAGE_EXTENSIONS)
    if not is_valid:
        return {"success": False, "error": ext_error}
    
    path = Path(image_path)
    if not path.exists():
        return {"success": False, "error": f"File not found: {image_path}"}
    
    logger.info("analyzing_image", path=image_path, model=model or VISION_MODEL, namespace=namespace)
    
    img_base64 = _image_to_base64(image_path)
    if not img_base64:
        return {"success": False, "error": "Failed to preprocess image"}
    
    description = await _call_ollama_vision(img_base64, prompt, model)
    if description is None:
        return {
            "success": False,
            "error": "Vision model unavailable. Pastikan Ollama berjalan dan model sudah di-pull."
        }
    
    if save_to_memory and description:
        await _save_vision_result(
            path=image_path,
            content=description,
            namespace=namespace,
            metadata={"type": "image_analysis", "prompt": prompt}
        )
    
    logger.info("image_analysis_complete", path=image_path, description_length=len(description))
    
    return {
        "success": True,
        "description": description,
        "model": model or VISION_MODEL,
        "image_path": str(path),
        "namespace": namespace
    }


async def analyze_pdf_pages_impl(
    pdf_path: str,
    prompt: str = "Extract all text and describe any charts, tables, and images",
    pages: Optional[List[int]] = None,
    namespace: str = "default",
    save_to_memory: bool = True,
    model: str = None
) -> Dict[str, Any]:
    """Extract dan analyze PDF pages sebagai images."""
    if not is_safe_path(pdf_path):
        return {"success": False, "error": "Path outside allowed directories"}
    
    is_valid, ext_error = validate_file_extension(pdf_path, frozenset(['.pdf']))
    if not is_valid:
        return {"success": False, "error": ext_error}
    
    path = Path(pdf_path)
    if not path.exists():
        return {"success": False, "error": f"File not found: {pdf_path}"}
    
    try:
        import fitz
    except ImportError:
        return {"success": False, "error": "PyMuPDF tidak terinstall. Jalankan: pip install pymupdf"}
    
    logger.info("analyzing_pdf", path=pdf_path, requested_pages=pages, model=model or VISION_MODEL)
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        if pages is None:
            page_indices = list(range(min(total_pages, MAX_PDF_PAGES)))
        else:
            page_indices = [p for p in pages if 0 <= p < total_pages][:MAX_PDF_PAGES]
        
        if not page_indices:
            doc.close()
            return {"success": False, "error": "No valid pages to process"}
        
        results = []
        
        for page_num in page_indices:
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")
            img_base64 = base64.b64encode(img_data).decode()
            
            page_prompt = f"[Page {page_num + 1} of {total_pages}] {prompt}"
            description = await _call_ollama_vision(img_base64, page_prompt, model)
            
            if description:
                results.append({"page": page_num + 1, "content": description})
                logger.info("pdf_page_analyzed", page=page_num + 1, total=total_pages)
            else:
                logger.warning("pdf_page_analysis_failed", page=page_num + 1)
                results.append({"page": page_num + 1, "content": "[Analysis failed for this page]"})
        
        doc.close()
        
        full_content = "\n\n".join([f"## Page {r['page']}\n{r['content']}" for r in results])
        
        if save_to_memory and full_content:
            await _save_vision_result(
                path=pdf_path,
                content=full_content,
                namespace=namespace,
                metadata={"type": "pdf_analysis", "pages_analyzed": len(results), "total_pages": total_pages, "prompt": prompt}
            )
        
        return {
            "success": True,
            "pages_analyzed": len(results),
            "total_pages": total_pages,
            "content": full_content,
            "per_page": results,
            "namespace": namespace
        }
        
    except Exception as e:
        logger.error("pdf_analysis_failed", error=str(e), path=pdf_path)
        return {"success": False, "error": str(e)}


async def list_vision_results_impl(namespace: str = "default", limit: int = 10) -> Dict[str, Any]:
    """List hasil vision analysis yang tersimpan di memory."""
    from memory.longterm import memory_search
    
    result = await memory_search(
        query="image analysis pdf vision",
        namespace=namespace,
        limit=limit,
        strategy="keyword"
    )
    return result


@register_tool
class AnalyzeImageTool(BaseTool):
    """Tool untuk analyze image menggunakan local vision model."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="analyze_image",
            description="Analyze image using local vision model via Ollama",
            parameters=[
                ToolParameter(name="image_path", type="string", description="Absolute path ke image file", required=True),
                ToolParameter(name="prompt", type="string", description="Instruksi untuk vision model", required=False, default="Describe this image in detail"),
                ToolParameter(name="namespace", type="string", description="Namespace untuk memory", required=False, default="default"),
                ToolParameter(name="save_to_memory", type="boolean", description="Simpan hasil ke LTM", required=False, default=True),
                ToolParameter(name="model", type="string", description="Override model", required=False, default=None)
            ],
            returns="Dict dengan success, description, model, image_path"
        )
    
    async def execute(self, task: Task) -> TaskResult:
        payload = task.payload
        result = await analyze_image_impl(
            image_path=payload.get("image_path"),
            prompt=payload.get("prompt", "Describe this image in detail"),
            namespace=payload.get("namespace", "default"),
            save_to_memory=payload.get("save_to_memory", True),
            model=payload.get("model")
        )
        
        if result.get("success"):
            return TaskResult.success_result(task_id=task.id, data=result, context={"tool": self.name})
        else:
            return TaskResult.failure_result(task_id=task.id, error=result.get("error"), error_code="VISION_ERROR")


@register_tool
class AnalyzePdfPagesTool(BaseTool):
    """Tool untuk extract dan analyze PDF pages."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="analyze_pdf_pages",
            description="Extract and analyze PDF pages as images using vision model",
            parameters=[
                ToolParameter(name="pdf_path", type="string", description="Absolute path ke PDF file", required=True),
                ToolParameter(name="prompt", type="string", description="Instruksi untuk setiap halaman", required=False, default="Extract all text and describe any charts, tables, and images"),
                ToolParameter(name="pages", type="array", description="List nomor halaman (0-indexed). None = semua", required=False, default=None),
                ToolParameter(name="namespace", type="string", description="Namespace untuk memory", required=False, default="default"),
                ToolParameter(name="save_to_memory", type="boolean", description="Simpan hasil ke LTM", required=False, default=True),
                ToolParameter(name="model", type="string", description="Override model", required=False, default=None)
            ],
            returns="Dict dengan pages_analyzed, content, per_page"
        )
    
    async def execute(self, task: Task) -> TaskResult:
        payload = task.payload
        result = await analyze_pdf_pages_impl(
            pdf_path=payload.get("pdf_path"),
            prompt=payload.get("prompt", "Extract all text and describe any charts, tables, and images"),
            pages=payload.get("pages"),
            namespace=payload.get("namespace", "default"),
            save_to_memory=payload.get("save_to_memory", True),
            model=payload.get("model")
        )
        
        if result.get("success"):
            return TaskResult.success_result(task_id=task.id, data=result, context={"tool": self.name})
        else:
            return TaskResult.failure_result(task_id=task.id, error=result.get("error"), error_code="PDF_VISION_ERROR")


@register_tool
class ListVisionResultsTool(BaseTool):
    """Tool untuk list vision analysis results."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_vision_results",
            description="List vision analysis results stored in memory",
            parameters=[
                ToolParameter(name="namespace", type="string", description="Namespace untuk filter", required=False, default="default"),
                ToolParameter(name="limit", type="integer", description="Maksimum hasil", required=False, default=10)
            ],
            returns="Dict dengan list vision memories"
        )
    
    async def execute(self, task: Task) -> TaskResult:
        payload = task.payload
        result = await list_vision_results_impl(
            namespace=payload.get("namespace", "default"),
            limit=payload.get("limit", 10)
        )
        
        return TaskResult.success_result(task_id=task.id, data=result, context={"tool": self.name})


# Backward compatibility - export functions
analyze_image = analyze_image_impl
analyze_pdf_pages = analyze_pdf_pages_impl
list_vision_results = list_vision_results_impl

__all__ = [
    "VISION_MODEL", "OLLAMA_URL", "VISION_TIMEOUT",
    "ALLOWED_IMAGE_EXTENSIONS", "MAX_IMAGE_SIZE", "MAX_PDF_PAGES",
    "analyze_image", "analyze_pdf_pages", "list_vision_results"
]
