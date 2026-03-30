"""
Enhanced Vision Tools — Extended capabilities for MCP Vision System

New Features:
1. Batch Processing — Multiple images in parallel
2. Image Comparison — Compare 2+ images
3. Structured Extraction — JSON output from images
4. Image Enhancement — Auto-enhance before analysis
5. URL Support — Analyze images from URLs
6. OCR Hybrid — PaddleOCR fallback for text extraction
7. Confidence Scoring — Reliability metrics
8. Template Matching — Pattern detection
9. Video Frame Analysis — Extract and analyze frames
10. Smart Caching — Avoid re-analysis
"""

import asyncio
import base64
import hashlib
import io
import json
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
import numpy as np

from observability.logger import logger
from tools.file.path_utils import is_safe_path, validate_file_extension
from execution import registry

# Import existing vision tools
from execution.tools.vision_tools import (
    analyze_image as base_analyze_image,
    _call_ollama_vision,
    _image_to_base64,
    VISION_MODEL,
    OLLAMA_URL,
    VISION_TIMEOUT,
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_IMAGE_SIZE,
    MAX_PDF_PAGES
)

# Import hybrid storage components
from core.vision_config import (
    VisionStorageConfig, 
    ProcessingResult, 
    get_config,
    classify_document_type,
    calculate_content_quality
)
from memory.vision_repository import save_vision_result
from memory.longterm import memory_save

# =============================================================================
# CONFIGURATION
# =============================================================================

BATCH_SIZE = 4  # Max parallel processing
CACHE_TTL_SECONDS = 3600  # 1 hour cache
CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence for reliable results

ENHANCED_MODELS = {
    "fast": "moondream2",      # Lightweight, fast
    "balanced": "llava",        # Good balance
    "quality": "llava-llama3",  # High quality
    "ocr": "llava-phi3"         # Optimized for text
}

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VisionResult:
    """Structured result dari vision analysis"""
    success: bool
    content: str
    confidence: float
    model: str
    processing_time: float
    image_path: str
    metadata: Dict[str, Any]
    error: Optional[str] = None

@dataclass
class ComparisonResult:
    """Result dari image comparison"""
    similarities: List[str]
    differences: List[str]
    confidence: float
    recommendation: Optional[str] = None

@dataclass
class StructuredExtraction:
    """Structured data extraction result"""
    success: bool
    data: Dict[str, Any]
    raw_text: str
    confidence: float
    missing_fields: List[str]

# =============================================================================
# CACHE SYSTEM
# =============================================================================

class VisionCache:
    """Simple in-memory cache untuk vision results"""
    
    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        self._cache: Dict[str, Dict] = {}
        self._ttl = ttl_seconds
    
    def _generate_key(self, image_path: str, prompt: str, model: str) -> str:
        """Generate cache key dari image + prompt + model"""
        content = f"{image_path}:{prompt}:{model}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, image_path: str, prompt: str, model: str) -> Optional[Dict]:
        """Get cached result jika masih valid"""
        key = self._generate_key(image_path, prompt, model)
        cached = self._cache.get(key)
        
        if cached:
            if time.time() - cached["timestamp"] < self._ttl:
                logger.info("vision_cache_hit", key=key[:8])
                return cached["result"]
            else:
                del self._cache[key]
        
        return None
    
    def set(self, image_path: str, prompt: str, model: str, result: Dict):
        """Cache result baru"""
        key = self._generate_key(image_path, prompt, model)
        self._cache[key] = {
            "result": result,
            "timestamp": time.time()
        }
        logger.info("vision_cache_set", key=key[:8])
    
    def clear(self):
        """Clear all cache"""
        self._cache.clear()

# Global cache instance
vision_cache = VisionCache()

# =============================================================================
# ENHANCED IMAGE ANALYSIS
# =============================================================================

@registry.register
async def analyze_image_enhanced(
    image_path: str,
    prompt: str = "Describe this image in detail",
    namespace: str = "default",
    model: str = None,
    use_cache: bool = True,
    return_confidence: bool = True,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> VisionResult:
    """
    Enhanced image analysis dengan confidence scoring dan caching.
    
    Args:
        image_path: Path ke image file
        prompt: Instruksi untuk vision model
        namespace: Namespace untuk memory
        model: Model override
        use_cache: Gunakan cache jika tersedia
        return_confidence: Hitung confidence score
        progress_callback: Callback untuk progress updates
    
    Returns:
        VisionResult dengan confidence dan metadata
    """
    start_time = time.time()
    target_model = model or VISION_MODEL
    
    # Check cache
    if use_cache:
        cached = vision_cache.get(image_path, prompt, target_model)
        if cached:
            return VisionResult(
                success=True,
                content=cached.get("description", ""),
                confidence=cached.get("confidence", 0.9),
                model=target_model,
                processing_time=0,
                image_path=image_path,
                metadata={"cached": True}
            )
    
    if progress_callback:
        await progress_callback("validating", 0.1)
    
    # Security check
    if not is_safe_path(image_path):
        return VisionResult(
            success=False,
            content="",
            confidence=0.0,
            model=target_model,
            processing_time=time.time() - start_time,
            image_path=image_path,
            metadata={},
            error="Path outside allowed directories"
        )
    
    if progress_callback:
        await progress_callback("preprocessing", 0.3)
    
    # Preprocess image
    img_base64 = _image_to_base64(image_path)
    if not img_base64:
        return VisionResult(
            success=False,
            content="",
            confidence=0.0,
            model=target_model,
            processing_time=time.time() - start_time,
            image_path=image_path,
            metadata={},
            error="Failed to preprocess image"
        )
    
    if progress_callback:
        await progress_callback("analyzing", 0.6)
    
    # Call vision model
    description = await _call_ollama_vision(img_base64, prompt, target_model)
    
    if description is None:
        return VisionResult(
            success=False,
            content="",
            confidence=0.0,
            model=target_model,
            processing_time=time.time() - start_time,
            image_path=image_path,
            metadata={},
            error="Vision model unavailable"
        )
    
    # Calculate confidence
    confidence = 0.0
    if return_confidence:
        confidence = _calculate_confidence(description, prompt)
    
    processing_time = time.time() - start_time
    
    if progress_callback:
        await progress_callback("complete", 1.0)
    
    result = VisionResult(
        success=True,
        content=description,
        confidence=confidence,
        model=target_model,
        processing_time=processing_time,
        image_path=image_path,
        metadata={
            "prompt": prompt,
            "cached": False,
            "confidence_calculated": return_confidence
        }
    )
    
    # Cache result
    if use_cache:
        vision_cache.set(image_path, prompt, target_model, {
            "description": description,
            "confidence": confidence
        })
    
    # HYBRID STORAGE: Save to SQL based on confidence
    await _save_to_hybrid_storage(result, image_path, namespace)
    
    return result


def _calculate_confidence(description: str, prompt: str) -> float:
    """
    Calculate confidence score berdasarkan response quality.
    
    Factors:
    - Response length (adequate detail)
    - Uncertainty indicators ("maybe", "possibly", etc.)
    - Specificity (numbers, measurements)
    """
    confidence = 0.5  # Base confidence
    
    # Length factor (0.0 - 0.3)
    length = len(description)
    if length > 500:
        confidence += 0.3
    elif length > 200:
        confidence += 0.2
    elif length > 50:
        confidence += 0.1
    
    # Uncertainty penalty
    uncertainty_words = [
        "maybe", "perhaps", "possibly", "might", "could be",
        "unclear", "difficult to tell", "hard to say", "not sure"
    ]
    uncertainty_count = sum(1 for word in uncertainty_words if word in description.lower())
    confidence -= uncertainty_count * 0.05
    
    # Specificity bonus
    specificity_indicators = [
        r"\d+",  # Numbers
        "left", "right", "top", "bottom", "center",
        "red", "blue", "green", "yellow", "black", "white"
    ]
    import re
    for indicator in specificity_indicators:
        if re.search(indicator, description, re.IGNORECASE):
            confidence += 0.02
    
    return max(0.0, min(1.0, confidence))


# =============================================================================
# BATCH PROCESSING
# =============================================================================

@registry.register
async def analyze_batch(
    image_paths: List[str],
    prompt: str = "Describe this image in detail",
    namespace: str = "default",
    model: str = None,
    max_parallel: int = BATCH_SIZE,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[VisionResult]:
    """
    Analyze multiple images in parallel dengan rate limiting.
    
    Args:
        image_paths: List of image paths
        prompt: Instruksi untuk setiap image
        namespace: Namespace untuk memory
        model: Model override
        max_parallel: Max concurrent processing
        progress_callback: Callback(current, total)
    
    Returns:
        List of VisionResult
    """
    semaphore = asyncio.Semaphore(max_parallel)
    total = len(image_paths)
    completed = 0
    
    async def analyze_with_semaphore(path: str) -> VisionResult:
        nonlocal completed
        async with semaphore:
            result = await analyze_image_enhanced(
                image_path=path,
                prompt=prompt,
                namespace=namespace,
                model=model
            )
            completed += 1
            if progress_callback:
                await progress_callback(completed, total)
            return result
    
    logger.info("batch_analysis_start", total_images=total, max_parallel=max_parallel)
    
    tasks = [analyze_with_semaphore(path) for path in image_paths]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to failed results
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append(VisionResult(
                success=False,
                content="",
                confidence=0.0,
                model=model or VISION_MODEL,
                processing_time=0.0,
                image_path=image_paths[i],
                metadata={},
                error=str(result)
            ))
        else:
            processed_results.append(result)
    
    successful = sum(1 for r in processed_results if r.success)
    logger.info("batch_analysis_complete", 
                total=total, 
                successful=successful,
                failed=total - successful)
    
    return processed_results


# =============================================================================
# IMAGE COMPARISON
# =============================================================================

@registry.register
async def compare_images(
    image_paths: List[str],
    comparison_prompt: str = "Compare these images and identify similarities and differences",
    detailed_analysis: bool = True
) -> ComparisonResult:
    """
    Compare multiple images dan identifikasi similarities & differences.
    
    Args:
        image_paths: List of 2+ image paths
        comparison_prompt: Custom comparison instructions
        detailed_analysis: Lakukan detailed pairwise comparison
    
    Returns:
        ComparisonResult dengan analysis
    """
    if len(image_paths) < 2:
        return ComparisonResult(
            similarities=[],
            differences=[],
            confidence=0.0,
            recommendation="Need at least 2 images to compare"
        )
    
    logger.info("image_comparison_start", image_count=len(image_paths))
    
    # Analyze each image individually
    individual_results = await analyze_batch(
        image_paths=image_paths,
        prompt="Describe all visible elements, objects, text, and layout in detail",
        max_parallel=BATCH_SIZE
    )
    
    # Build comparison context
    descriptions = [r.content for r in individual_results if r.success]
    
    if len(descriptions) < 2:
        return ComparisonResult(
            similarities=[],
            differences=[],
            confidence=0.0,
            recommendation="Could not analyze enough images for comparison"
        )
    
    # Compare descriptions
    similarities = []
    differences = []
    
    # Simple text-based comparison (could be enhanced dengan image embeddings)
    from difflib import SequenceMatcher
    
    for i in range(len(descriptions)):
        for j in range(i + 1, len(descriptions)):
            similarity_ratio = SequenceMatcher(None, descriptions[i], descriptions[j]).ratio()
            
            if similarity_ratio > 0.8:
                similarities.append(f"Images {i+1} and {j+1} are very similar ({similarity_ratio:.0%})")
            elif similarity_ratio > 0.5:
                similarities.append(f"Images {i+1} and {j+1} share some common elements ({similarity_ratio:.0%})")
            else:
                differences.append(f"Images {i+1} and {j+1} are significantly different ({similarity_ratio:.0%})")
    
    confidence = sum(r.confidence for r in individual_results) / len(individual_results)
    
    recommendation = None
    if confidence < CONFIDENCE_THRESHOLD:
        recommendation = "Low confidence in comparison. Consider re-analyzing with better quality images."
    
    return ComparisonResult(
        similarities=similarities,
        differences=differences,
        confidence=confidence,
        recommendation=recommendation
    )


# =============================================================================
# STRUCTURED DATA EXTRACTION
# =============================================================================

@registry.register
async def extract_structured_data(
    image_path: str,
    schema: Dict[str, str],
    model: str = None
) -> StructuredExtraction:
    """
    Extract structured data dari image berdasarkan schema.
    
    Args:
        image_path: Path ke image
        schema: Dict dengan field names dan descriptions
        model: Model override
    
    Returns:
        StructuredExtraction dengan extracted data
    """
    # Build extraction prompt
    schema_desc = "\n".join([f"- {field}: {desc}" for field, desc in schema.items()])
    
    prompt = f"""Extract the following information from this image and return as JSON:

{schema_desc}

Return ONLY a valid JSON object with these exact field names. If a field is not found, use null.
JSON:"""
    
    result = await analyze_image_enhanced(
        image_path=image_path,
        prompt=prompt,
        model=model or ENHANCED_MODELS.get("ocr", VISION_MODEL)
    )
    
    if not result.success:
        return StructuredExtraction(
            success=False,
            data={},
            raw_text="",
            confidence=0.0,
            missing_fields=list(schema.keys())
        )
    
    # Parse JSON dari response
    try:
        # Extract JSON dari response text
        text = result.content
        
        # Cari JSON block
        if "```json" in text:
            json_str = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            json_str = text.split("```")[1].split("```")[0].strip()
        else:
            # Coba parse langsung
            json_str = text.strip()
        
        data = json.loads(json_str)
        
        # Validate fields
        missing = [field for field in schema.keys() if field not in data or data[field] is None]
        
        return StructuredExtraction(
            success=True,
            data=data,
            raw_text=result.content,
            confidence=result.confidence * (1 - len(missing) / len(schema)),
            missing_fields=missing
        )
        
    except json.JSONDecodeError as e:
        logger.error("structured_extraction_parse_failed", error=str(e))
        return StructuredExtraction(
            success=False,
            data={},
            raw_text=result.content,
            confidence=0.0,
            missing_fields=list(schema.keys()),
            error=f"Failed to parse JSON: {str(e)}"
        )


# =============================================================================
# IMAGE ENHANCEMENT
# =============================================================================

@registry.register
async def enhance_image(
    image_path: str,
    enhancements: List[str] = None,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Apply enhancements ke image sebelum analysis.
    
    Enhancements:
    - "contrast": Improve contrast
    - "sharpness": Sharpen image
    - "denoise": Remove noise
    - "auto_rotate": Auto-rotate berdasarkan text orientation
    - "upscale": Upscale resolution
    
    Args:
        image_path: Source image path
        enhancements: List of enhancement types
        output_path: Output path (default: temp file)
    
    Returns:
        Dict dengan enhanced image path dan applied enhancements
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        
        enhancements = enhancements or ["contrast", "sharpness"]
        
        with Image.open(image_path) as img:
            original_mode = img.mode
            
            # Convert ke RGB untuk processing
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            applied = []
            
            for enhancement in enhancements:
                if enhancement == "contrast":
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(1.5)
                    applied.append("contrast")
                
                elif enhancement == "sharpness":
                    enhancer = ImageEnhance.Sharpness(img)
                    img = enhancer.enhance(2.0)
                    applied.append("sharpness")
                
                elif enhancement == "denoise":
                    img = img.filter(ImageFilter.MedianFilter(size=3))
                    applied.append("denoise")
                
                elif enhancement == "upscale" and img.size[0] < 1024:
                    # Upscale jika terlalu kecil
                    scale = 1024 / img.size[0]
                    new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    applied.append(f"upscale_to_{new_size[0]}x{new_size[1]}")
            
            # Save enhanced image
            if output_path is None:
                output_path = tempfile.mktemp(suffix=".jpg")
            
            img.save(output_path, format='JPEG', quality=90)
            
            logger.info("image_enhanced",
                       source=image_path,
                       output=output_path,
                       enhancements=applied)
            
            return {
                "success": True,
                "original_path": image_path,
                "enhanced_path": output_path,
                "enhancements_applied": applied,
                "original_size": Image.open(image_path).size,
                "enhanced_size": img.size
            }
            
    except Exception as e:
        logger.error("image_enhancement_failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "original_path": image_path
        }


# =============================================================================
# URL SUPPORT
# =============================================================================

@registry.register
async def analyze_image_url(
    image_url: str,
    prompt: str = "Describe this image in detail",
    namespace: str = "default",
    model: str = None,
    timeout: int = 30
) -> VisionResult:
    """
    Download and analyze image dari URL.
    
    Args:
        image_url: URL ke image
        prompt: Instruksi untuk vision model
        namespace: Namespace untuk memory
        model: Model override
        timeout: Download timeout
    
    Returns:
        VisionResult
    """
    start_time = time.time()
    
    # Validate URL
    parsed = urlparse(image_url)
    if not parsed.scheme in ('http', 'https'):
        return VisionResult(
            success=False,
            content="",
            confidence=0.0,
            model=model or VISION_MODEL,
            processing_time=time.time() - start_time,
            image_path=image_url,
            metadata={},
            error="Invalid URL scheme. Only HTTP/HTTPS supported."
        )
    
    try:
        # Download image menggunakan curl
        import tempfile
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp_path = tmp.name
        
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "-L", "--max-time", str(timeout),
            "-o", tmp_path,
            image_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 5)
        
        if proc.returncode != 0:
            return VisionResult(
                success=False,
                content="",
                confidence=0.0,
                model=model or VISION_MODEL,
                processing_time=time.time() - start_time,
                image_path=image_url,
                metadata={},
                error=f"Failed to download image: {stderr.decode()[:200]}"
            )
        
        # Analyze downloaded image
        result = await analyze_image_enhanced(
            image_path=tmp_path,
            prompt=prompt,
            namespace=namespace,
            model=model
        )
        
        # Update image path ke URL asli
        result.image_path = image_url
        result.metadata["downloaded_path"] = tmp_path
        
        # Cleanup temp file
        try:
            Path(tmp_path).unlink()
        except:
            pass
        
        return result
        
    except Exception as e:
        return VisionResult(
            success=False,
            content="",
            confidence=0.0,
            model=model or VISION_MODEL,
            processing_time=time.time() - start_time,
            image_path=image_url,
            metadata={},
            error=str(e)
        )


# =============================================================================
# OCR HYBRID
# =============================================================================

@registry.register
async def analyze_with_ocr_fallback(
    image_path: str,
    prompt: str = "Extract all text from this image",
    namespace: str = "default",
    min_confidence: float = 0.7
) -> VisionResult:
    """
    Analyze image dengan vision model, fallback ke OCR jika confidence rendah.
    
    Args:
        image_path: Path ke image
        prompt: Prompt untuk vision model
        namespace: Namespace untuk memory
        min_confidence: Minimum confidence untuk vision result
    
    Returns:
        VisionResult (vision atau OCR)
    """
    # Try vision first
    vision_result = await analyze_image_enhanced(
        image_path=image_path,
        prompt=prompt,
        namespace=namespace,
        return_confidence=True
    )
    
    if vision_result.success and vision_result.confidence >= min_confidence:
        logger.info("vision_sufficient", confidence=vision_result.confidence)
        vision_result.metadata["method"] = "vision_only"
        return vision_result
    
    # Fallback ke OCR
    logger.info("vision_low_confidence", 
                confidence=vision_result.confidence if vision_result.success else 0,
                falling_back_to="ocr")
    
    try:
        # Try PaddleOCR
        from paddleocr import PaddleOCR
        
        ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        result = ocr.ocr(image_path, cls=True)
        
        if result and result[0]:
            texts = []
            total_confidence = 0
            count = 0
            
            for line in result[0]:
                if line:
                    text, confidence = line[1]
                    texts.append(text)
                    total_confidence += confidence
                    count += 1
            
            ocr_text = "\n".join(texts)
            avg_confidence = total_confidence / count if count > 0 else 0
            
            # Combine dengan vision result
            combined_content = f"""Vision Analysis:
{vision_result.content if vision_result.success else "[Vision analysis failed]"}

OCR Text Extraction:
{ocr_text}"""
            
            return VisionResult(
                success=True,
                content=combined_content,
                confidence=avg_confidence,
                model="hybrid_vision_ocr",
                processing_time=vision_result.processing_time,
                image_path=image_path,
                metadata={
                    "method": "hybrid",
                    "vision_confidence": vision_result.confidence if vision_result.success else 0,
                    "ocr_confidence": avg_confidence,
                    "ocr_lines": count
                }
            )
        
    except ImportError:
        logger.warning("paddleocr_not_available")
    except Exception as e:
        logger.error("ocr_fallback_failed", error=str(e))
    
    # Return original vision result jika OCR gagal
    return vision_result


# =============================================================================
# VIDEO FRAME ANALYSIS
# =============================================================================

@registry.register
async def analyze_video_frames(
    video_path: str,
    prompt: str = "Describe this frame",
    frame_interval: int = 5,
    max_frames: int = 10,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Extract and analyze frames dari video file.
    
    Args:
        video_path: Path ke video file
        prompt: Prompt untuk setiap frame
        frame_interval: Interval antar frame dalam detik
        max_frames: Maximum frames untuk analyze
        namespace: Namespace untuk memory
    
    Returns:
        Dict dengan frame analysis results
    """
    try:
        import cv2
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            return {"success": False, "error": "Could not open video file"}
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        # Calculate frame indices
        frame_indices = []
        for i in range(max_frames):
            timestamp = i * frame_interval
            if timestamp > duration:
                break
            frame_idx = int(timestamp * fps)
            frame_indices.append((timestamp, frame_idx))
        
        results = []
        temp_frames = []
        
        for timestamp, frame_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if ret:
                # Save frame ke temp file
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    cv2.imwrite(tmp.name, frame)
                    temp_frames.append(tmp.name)
        
        cap.release()
        
        # Analyze frames
        frame_results = await analyze_batch(
            image_paths=temp_frames,
            prompt=prompt,
            namespace=namespace
        )
        
        # Cleanup temp files
        for tmp_path in temp_frames:
            try:
                Path(tmp_path).unlink()
            except:
                pass
        
        # Build result
        for i, (timestamp, _) in enumerate(frame_indices):
            if i < len(frame_results):
                results.append({
                    "timestamp": timestamp,
                    "timestamp_formatted": f"{int(timestamp // 60):02d}:{int(timestamp % 60):02d}",
                    "analysis": frame_results[i].content if frame_results[i].success else None,
                    "confidence": frame_results[i].confidence,
                    "success": frame_results[i].success
                })
        
        return {
            "success": True,
            "video_path": video_path,
            "duration_seconds": duration,
            "total_frames_in_video": total_frames,
            "frames_analyzed": len(results),
            "frame_interval_seconds": frame_interval,
            "results": results
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "OpenCV (cv2) not installed. Install with: pip install opencv-python"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

@registry.register
def clear_vision_cache():
    """Clear vision cache"""
    vision_cache.clear()
    logger.info("vision_cache_cleared")


@registry.register
async def get_vision_stats() -> Dict[str, Any]:
    """Get vision system statistics"""
    return {
        "cache_entries": len(vision_cache._cache),
        "cache_ttl_seconds": vision_cache._ttl,
        "batch_size": BATCH_SIZE,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "available_models": ENHANCED_MODELS,
        "default_model": VISION_MODEL,
        "ollama_url": OLLAMA_URL,
        "vision_timeout": VISION_TIMEOUT
    }


# =============================================================================
# HYBRID STORAGE INTEGRATION
# =============================================================================

async def _save_to_hybrid_storage(
    vision_result: VisionResult,
    image_path: str,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Save vision result ke hybrid storage (LTM + SQL) berdasarkan confidence.
    
    Logic:
    - High confidence (>=0.8): Save to BOTH SQL and LTM
    - Medium confidence (0.7-0.8): Save to LTM only
    - Low confidence (<0.7): Reject (tidak disimpan)
    
    Args:
        vision_result: Hasil dari vision analysis
        image_path: Path ke file yang dianalisis
        namespace: Namespace untuk storage
        
    Returns:
        Dict dengan status penyimpanan
    """
    try:
        config = get_config()
        confidence = vision_result.confidence
        
        # Get storage decision
        storage_decision = config.get_storage_decision(confidence)
        
        result_info = {
            "confidence": confidence,
            "storage_decision": storage_decision,
            "saved_to_sql": False,
            "saved_to_ltm": False,
            "sql_id": None,
            "ltm_key": None
        }
        
        # Classify document type
        doc_type, confidence_boost = classify_document_type(vision_result.content)
        
        # Calculate content quality
        quality_metrics = calculate_content_quality(vision_result.content)
        
        # Prepare extracted entities
        entities = {
            "dates": _extract_dates(vision_result.content),
            "amounts": _extract_amounts(vision_result.content),
            "emails": _extract_emails(vision_result.content),
            "phones": _extract_phones(vision_result.content),
            "document_type": doc_type,
            "quality_metrics": quality_metrics
        }
        
        # Prepare file info
        path_obj = Path(image_path)
        file_name = path_obj.name
        file_hash = _calculate_file_hash(image_path)
        file_size = path_obj.stat().st_size if path_obj.exists() else 0
        mime_type = _get_mime_type(image_path)
        
        # 1. SAVE TO SQL (jika confidence tinggi)
        if storage_decision == 'sql+ltm':
            processing_result = ProcessingResult(
                file_name=file_name,
                file_path=str(image_path),
                file_hash=file_hash,
                file_size_bytes=file_size,
                mime_type=mime_type,
                extracted_text=vision_result.content,
                confidence_score=confidence,
                processing_method="vision",
                model_used=vision_result.model,
                processing_time_ms=int(vision_result.processing_time * 1000),
                document_type=doc_type,
                status="success",
                extracted_entities=entities,
                processing_metadata=vision_result.metadata,
                namespace=namespace,
                tenant_id="default",
                ltm_key=""  # Will be updated after LTM save
            )
            
            sql_result = await save_vision_result(processing_result, config)
            
            if sql_result.get("success"):
                result_info["saved_to_sql"] = True
                result_info["sql_id"] = sql_result.get("id")
                logger.info("vision_saved_to_sql", 
                           id=sql_result.get("id"),
                           confidence=confidence)
            else:
                logger.warning("vision_sql_save_failed", 
                              error=sql_result.get("error"),
                              confidence=confidence)
        
        # 2. SAVE TO LTM (jika confidence medium atau high)
        if storage_decision in ['sql+ltm', 'ltm_only']:
            ltm_key = f"vision:{file_name}"
            
            ltm_content = f"""Vision Analysis Result
File: {file_name}
Document Type: {doc_type}
Confidence: {confidence:.2f}
Model: {vision_result.model}

Extracted Content:
{vision_result.content[:1500]}

Entities: {json.dumps(entities, indent=2)}
"""
            
            ltm_metadata = {
                "source": "vision_analysis",
                "file_name": file_name,
                "file_hash": file_hash,
                "confidence": confidence,
                "document_type": doc_type,
                "model": vision_result.model,
                "processing_time_ms": int(vision_result.processing_time * 1000),
                "namespace": namespace
            }
            
            try:
                ltm_result = await memory_save(
                    key=ltm_key,
                    content=ltm_content,
                    metadata=ltm_metadata,
                    namespace=namespace
                )
                
                if ltm_result.get("success"):
                    result_info["saved_to_ltm"] = True
                    result_info["ltm_key"] = ltm_key
                    
                    # Update LTM link in SQL jika sudah tersimpan di SQL
                    if result_info["sql_id"] and result_info["saved_to_sql"]:
                        from memory.vision_repository import update_ltm_link
                        await update_ltm_link(result_info["sql_id"], ltm_key)
                    
                    logger.info("vision_saved_to_ltm",
                               key=ltm_key,
                               confidence=confidence)
                else:
                    logger.warning("vision_ltm_save_failed",
                                  error=ltm_result.get("error"))
            except Exception as e:
                logger.error("vision_ltm_save_exception", error=str(e))
        
        # 3. REJECT jika low confidence
        if storage_decision == 'reject':
            logger.warning("vision_result_rejected",
                          file=file_name,
                          confidence=confidence,
                          threshold=config.get_threshold('medium'))
            result_info["rejected"] = True
            result_info["reason"] = "confidence_below_threshold"
        
        return result_info
        
    except Exception as e:
        logger.error("hybrid_storage_failed", error=str(e))
        return {
            "error": str(e),
            "saved_to_sql": False,
            "saved_to_ltm": False
        }


def _calculate_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of file untuk deduplication"""
    try:
        import hashlib
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return ""


def _get_mime_type(file_path: str) -> str:
    """Get MIME type dari file extension"""
    ext = Path(file_path).suffix.lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.pdf': 'application/pdf'
    }
    return mime_types.get(ext, 'application/octet-stream')


def _extract_dates(text: str) -> List[str]:
    """Extract dates dari text menggunakan regex"""
    import re
    date_patterns = [
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
        r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',
    ]
    dates = []
    for pattern in date_patterns:
        dates.extend(re.findall(pattern, text))
    return dates


def _extract_amounts(text: str) -> List[str]:
    """Extract monetary amounts dari text"""
    import re
    amount_patterns = [
        r'Rp\s*[\d.,]+',
        r'IDR\s*[\d.,]+',
        r'\$[\d.,]+',
        r'USD\s*[\d.,]+'
    ]
    amounts = []
    for pattern in amount_patterns:
        amounts.extend(re.findall(pattern, text))
    return amounts


def _extract_emails(text: str) -> List[str]:
    """Extract email addresses dari text"""
    import re
    return re.findall(r'[\w.-]+@[\w.-]+\.\w+', text)


def _extract_phones(text: str) -> List[str]:
    """Extract phone numbers dari text"""
    import re
    phone_patterns = [
        r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}'
    ]
    phones = []
    for pattern in phone_patterns:
        phones.extend(re.findall(pattern, text))
    return phones


# =============================================================================
# REGISTRY INTEGRATION
# =============================================================================

async def register_enhanced_vision_tools(registry):
    """Register semua enhanced vision tools ke registry"""
    
    tools = [
        ("analyze_image_enhanced", analyze_image_enhanced),
        ("analyze_batch", analyze_batch),
        ("compare_images", compare_images),
        ("extract_structured_data", extract_structured_data),
        ("enhance_image", enhance_image),
        ("analyze_image_url", analyze_image_url),
        ("analyze_with_ocr_fallback", analyze_with_ocr_fallback),
        ("analyze_video_frames", analyze_video_frames),
        ("clear_vision_cache", clear_vision_cache),
        ("get_vision_stats", get_vision_stats),
    ]
    
    for name, func in tools:
        registry.register(name, func)
    
    logger.info("enhanced_vision_tools_registered", count=len(tools))
    return len(tools)
