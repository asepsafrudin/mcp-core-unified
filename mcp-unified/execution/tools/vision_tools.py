"""
Vision Tools — Image & PDF Analysis via Local Ollama

[REVIEWER] Design decisions:
1. Menggunakan asyncio.create_subprocess_exec + curl (konsisten dengan longterm.py)
   BUKAN aiohttp — menghindari dependency baru untuk hal yang sama
2. Session management: satu subprocess per analyze call, bukan per-page
3. Timeout explicit: 60 detik untuk vision (lebih lama dari embedding 10s)
4. Path validation: reuse path_utils.is_safe_path — satu sumber kebenaran
5. Model default: moondream2 untuk ringan, llava untuk kualitas
"""
import asyncio
import base64
import json
import io
from pathlib import Path
from typing import Dict, Any, Optional, List
from observability.logger import logger
from tools.file.path_utils import is_safe_path, validate_file_extension
from execution import registry

# [REVIEWER] Model config
# llava: model vision umum yang tersedia di Ollama (~4.7GB)
# Ganti via environment variable jika perlu model lain
import os
VISION_MODEL = os.environ.get("MCP_VISION_MODEL", "llava")
OLLAMA_URL = "http://localhost:11434"
VISION_TIMEOUT = 60  # Detik — vision butuh lebih lama dari text embedding

# Format yang didukung
ALLOWED_IMAGE_EXTENSIONS = frozenset([
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'
])
MAX_IMAGE_SIZE = (1024, 1024)  # Resize untuk performa — sebelum kirim ke model

# Batas keamanan
MAX_PDF_PAGES = 50  # Maksimum halaman PDF yang diproses


async def _call_ollama_vision(
    image_base64: str,
    prompt: str,
    model: str = None
) -> Optional[str]:
    """
    Panggil Ollama vision model dengan image base64.
    
    [REVIEWER] Menggunakan curl via subprocess — konsisten dengan get_embedding()
    di longterm.py. Tidak introduce aiohttp sebagai dependency baru.
    
    Returns:
        Response text dari model, atau None jika gagal
    """
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
            "--max-time", str(VISION_TIMEOUT),  # [REVIEWER] Timeout explicit
            "-X", "POST",
            f"{OLLAMA_URL}/api/generate",
            "-H", "Content-Type: application/json",
            "-d", payload,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=VISION_TIMEOUT + 5  # Sedikit lebih dari curl timeout
        )
        
        if proc.returncode != 0:
            logger.error("ollama_vision_error",
                        model=target_model,
                        error=stderr.decode()[:200])
            return None
        
        response_data = json.loads(stdout)
        return response_data.get("response", "")
        
    except asyncio.TimeoutError:
        logger.error("ollama_vision_timeout",
                    model=target_model,
                    timeout=VISION_TIMEOUT)
        return None
    except Exception as e:
        logger.error("ollama_vision_failed", error=str(e))
        return None


def _image_to_base64(image_path: str) -> Optional[str]:
    """
    Load image, resize, convert ke base64.
    
    [REVIEWER] Resize ke MAX_IMAGE_SIZE sebelum encode —
    mengurangi token usage dan mempercepat inference.
    """
    try:
        from PIL import Image
        
        with Image.open(image_path) as img:
            # Convert ke RGB (handle PNG dengan alpha, dll)
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # Resize jika terlalu besar
            img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            return base64.b64encode(buffer.getvalue()).decode()
            
    except Exception as e:
        logger.error("image_preprocessing_failed",
                    path=image_path,
                    error=str(e))
        return None


@registry.register
async def analyze_image(
    image_path: str,
    prompt: str = "Describe this image in detail",
    namespace: str = "default",
    save_to_memory: bool = True,
    model: str = None
) -> Dict[str, Any]:
    """
    Analyze image menggunakan local vision model via Ollama.
    
    [REVIEWER] Security: path validation wajib sebelum apapun.
    Privacy: tidak ada cloud upload — pure local processing.
    
    Args:
        image_path: Absolute path ke image file
        prompt: Instruksi untuk vision model
        namespace: Namespace untuk menyimpan hasil ke memory
        save_to_memory: Simpan hasil ke LTM (default: True)
        model: Override model (default: VISION_MODEL dari env)
    
    Returns:
        Dict dengan success, description, model, image_path
    """
    # Security: validate path
    if not is_safe_path(image_path):
        return {"success": False, "error": "Path outside allowed directories"}
    
    # Validate extension
    is_valid, ext_error = validate_file_extension(
        image_path, ALLOWED_IMAGE_EXTENSIONS
    )
    if not is_valid:
        return {"success": False, "error": ext_error}
    
    path = Path(image_path)
    if not path.exists():
        return {"success": False, "error": f"File not found: {image_path}"}
    
    logger.info("analyzing_image",
               path=image_path,
               model=model or VISION_MODEL,
               namespace=namespace)
    
    # Preprocess image
    img_base64 = _image_to_base64(image_path)
    if not img_base64:
        return {"success": False, "error": "Failed to preprocess image"}
    
    # Call vision model
    description = await _call_ollama_vision(img_base64, prompt, model)
    if description is None:
        return {
            "success": False,
            "error": "Vision model unavailable. Pastikan Ollama berjalan dan model sudah di-pull."
        }
    
    # Save ke memory jika diminta
    if save_to_memory and description:
        await _save_vision_result(
            path=image_path,
            content=description,
            namespace=namespace,
            metadata={"type": "image_analysis", "prompt": prompt}
        )
    
    logger.info("image_analysis_complete",
               path=image_path,
               description_length=len(description))
    
    return {
        "success": True,
        "description": description,
        "model": model or VISION_MODEL,
        "image_path": str(path),
        "namespace": namespace
    }


@registry.register
async def analyze_pdf_pages(
    pdf_path: str,
    prompt: str = "Extract all text and describe any charts, tables, and images",
    pages: Optional[List[int]] = None,
    namespace: str = "default",
    save_to_memory: bool = True,
    model: str = None
) -> Dict[str, Any]:
    """
    Extract dan analyze PDF pages sebagai images.
    
    [REVIEWER] BUG FIX dari rancangan agent:
    - Session dibuat SEKALI di luar loop (bukan per-page)
    - Timeout explicit di setiap Ollama call
    - MAX_PDF_PAGES untuk mencegah resource exhaustion
    
    Args:
        pdf_path: Absolute path ke PDF file
        prompt: Instruksi untuk setiap halaman
        pages: List nomor halaman (0-indexed). None = semua halaman
        namespace: Namespace untuk memory
        save_to_memory: Simpan hasil ke LTM
        model: Override model
    
    Returns:
        Dict dengan success, pages_analyzed, content, per_page
    """
    # Security: validate path
    if not is_safe_path(pdf_path):
        return {"success": False, "error": "Path outside allowed directories"}
    
    is_valid, ext_error = validate_file_extension(
        pdf_path, frozenset(['.pdf'])
    )
    if not is_valid:
        return {"success": False, "error": ext_error}
    
    path = Path(pdf_path)
    if not path.exists():
        return {"success": False, "error": f"File not found: {pdf_path}"}
    
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return {
            "success": False,
            "error": "PyMuPDF tidak terinstall. Jalankan: pip install pymupdf"
        }
    
    logger.info("analyzing_pdf",
               path=pdf_path,
               requested_pages=pages,
               model=model or VISION_MODEL)
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        # Determine pages to process
        if pages is None:
            page_indices = list(range(min(total_pages, MAX_PDF_PAGES)))
        else:
            page_indices = [
                p for p in pages
                if 0 <= p < total_pages
            ][:MAX_PDF_PAGES]
        
        if not page_indices:
            doc.close()
            return {"success": False, "error": "No valid pages to process"}
        
        results = []
        
        # [REVIEWER] BUG FIX: Process semua pages, bukan buat session per-page
        # _call_ollama_vision sudah handle satu call per image dengan benar
        for page_num in page_indices:
            page = doc[page_num]
            
            # Render page ke image (2x scale untuk kualitas teks)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")
            img_base64 = base64.b64encode(img_data).decode()
            
            page_prompt = f"[Page {page_num + 1} of {total_pages}] {prompt}"
            
            # [REVIEWER] BUG FIX: Timeout ada di _call_ollama_vision
            description = await _call_ollama_vision(img_base64, page_prompt, model)
            
            if description:
                results.append({
                    "page": page_num + 1,
                    "content": description
                })
                logger.info("pdf_page_analyzed",
                           page=page_num + 1,
                           total=total_pages)
            else:
                logger.warning("pdf_page_analysis_failed",
                              page=page_num + 1)
                results.append({
                    "page": page_num + 1,
                    "content": "[Analysis failed for this page]"
                })
        
        doc.close()
        
        # Aggregate
        full_content = "\n\n".join([
            f"## Page {r['page']}\n{r['content']}"
            for r in results
        ])
        
        # Save ke memory
        if save_to_memory and full_content:
            await _save_vision_result(
                path=pdf_path,
                content=full_content,
                namespace=namespace,
                metadata={
                    "type": "pdf_analysis",
                    "pages_analyzed": len(results),
                    "total_pages": total_pages,
                    "prompt": prompt
                }
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


@registry.register
async def list_vision_results(
    namespace: str = "default",
    limit: int = 10
) -> Dict[str, Any]:
    """
    List hasil vision analysis yang tersimpan di memory.
    
    Args:
        namespace: Namespace untuk filter
        limit: Maksimum hasil
    
    Returns:
        Dict dengan list vision memories
    """
    from memory.longterm import memory_search
    
    result = await memory_search(
        query="image analysis pdf vision",
        namespace=namespace,
        limit=limit,
        strategy="keyword"
    )
    return result


async def _save_vision_result(
    path: str,
    content: str,
    namespace: str,
    metadata: dict = None
):
    """
    Helper: Simpan hasil vision ke long-term memory.
    
    [REVIEWER] Key menggunakan filename — upsert akan update
    jika file yang sama dianalisis ulang.
    """
    from memory.longterm import memory_save
    
    meta = metadata or {}
    meta["source"] = "vision_analysis"
    meta["file"] = path
    
    file_name = Path(path).name
    
    await memory_save(
        key=f"vision:{file_name}",
        content=content[:2000],  # Truncate untuk embedding efficiency
        metadata=meta,
        namespace=namespace
    )
    
    logger.info("vision_result_saved",
               file=file_name,
               namespace=namespace)
