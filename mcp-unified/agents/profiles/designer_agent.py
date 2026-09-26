import os
import sys
import logging
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base import BaseAgent, AgentProfile, AgentCapability, register_agent
from core.task import Task, TaskResult

logger = logging.getLogger(__name__)

@register_agent
class DesignerAgent(BaseAgent):
    """
    Agent specialized for Graphic Design and Presentation creation.
    
    Expertise:
        - Image search and curation (Unsplash, Pexels)
        - Presentation generation (Canva API with local python-pptx fallback)
        - Visual asset layout (infographics, banners, social media posts)
        - Slide editing and enhancement
    """
    
    @property
    def profile(self) -> AgentProfile:
        return AgentProfile(
            name="designer_agent",
            description="Graphic Design and Presentation specialist (Canva API + local PPTX fallback)",
            domain="media_and_design",
            capabilities={
                AgentCapability.TOOL_USE,
                AgentCapability.SKILL_COMPOSITION,
                AgentCapability.PLANNING,
                AgentCapability.REASONING,
            },
            preferred_skills=[
                "create_canva_presentation_pipeline",
                "create_plan",
            ],
            tools_whitelist=[
                # === Media/Vision tools ===
                "search_unsplash_image",
                "download_unsplash_image",
                "search_pexels_image",
                "download_pexels_image",
                "upload_canva_asset",
                "create_canva_design",
                "list_canva_designs",
                "get_design_edit_url",
                "vane_search",
                # === Local PPTX fallback tools ===
                "write_pptx",
                "read_pptx",
                "add_slide_pptx",
                "extract_text_pptx",
            ],
            max_concurrent_tasks=2,
            timeout_seconds=300.0
        )
        
    def can_handle(self, task: Task) -> bool:
        """
        Check if this agent can handle the task.
        """
        task_type = task.type.lower()
        
        # Check task type
        design_tasks = {
            "design", "presentation", "presentasi", "ppt", "pptx",
            "canva", "gambar", "image", "visual", "banner",
            "infographic", "infografis", "poster", "social_media"
        }
        
        if any(dt in task_type for dt in design_tasks):
            return True
            
        payload_str = str(task.payload).lower()
        return any(dt in payload_str for dt in design_tasks)
        
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute design-related tasks.
        
        Routes to:
        1. presentation: Canva presentation pipeline with local python-pptx fallback
        2. local_presentation: Explicit local python-pptx generation
        3. infographic / banner / poster / social_media: Canva preset creation
        4. search_images: Curate images from Unsplash / Pexels
        """
        payload = task.payload
        action = payload.get("action", "").lower()
        task_type = task.type.lower()
        effective_action = action or task_type
        
        try:
            # === 1. Local Presentation generation (explicit or pptx-only) ===
            if "local" in effective_action or "local_presentation" in effective_action or payload.get("force_local", False):
                return await self._handle_local_presentation(payload, task.id)
                
            # === 2. Image search & curation ===
            elif any(kw in effective_action for kw in ("search_image", "find_image", "image_search", "curate")):
                return await self._handle_image_search(payload, task.id)
                
            # === 3. Design Presets (infographic, banner, poster, social) ===
            elif any(kw in effective_action for kw in ("banner", "poster", "infographic", "infografis", "social")):
                return await self._handle_preset_design(effective_action, payload, task.id)
                
            # === 4. Presentation (default path with auto-fallback) ===
            else:
                return await self._handle_presentation_pipeline(payload, task.id)
                
        except Exception as e:
            logger.error(f"DesignerAgent error: {e}", exc_info=True)
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code="DESIGNER_AGENT_ERROR"
            )

    async def _handle_presentation_pipeline(self, payload: dict, task_id: str) -> TaskResult:
        """Create presentation via Canva, with graceful local PPTX fallback."""
        topic = payload.get("topic") or payload.get("query") or payload.get("title") or "Presentasi"
        images = payload.get("images", [])
        slides = payload.get("slides", [])
        
        if not images and ("topic" in payload or "query" in payload):
            images = [f"{topic} modern", f"{topic} professional"]
            
        # Try Canva Pipeline first
        canva_failed = False
        canva_error = None
        
        try:
            from skills.media.graphic_design_skill import create_canva_presentation_pipeline
            result = await create_canva_presentation_pipeline(
                topic=topic,
                image_queries=images
            )
            if result.get("design_url"):
                return TaskResult.success_result(
                    task_id=task_id,
                    data=result,
                    context={"agent": self.name, "action": "create_presentation", "tool": "canva"}
                )
            else:
                canva_failed = True
                canva_error = "Canva did not return design URL"
        except Exception as e:
            canva_failed = True
            canva_error = str(e)
            logger.warning(f"[DesignerAgent] Canva pipeline failed ({e}), switching to local PPTX fallback.")

        # Fallback to local python-pptx
        logger.info(f"[DesignerAgent] Falling back to local python-pptx for '{topic}'")
        return await self._handle_local_presentation(
            {
                "title": topic,
                "slides": slides,
                "output_path": payload.get("output_path", f"/home/aseps/MCP/storage/reports/{topic.replace(' ', '_').lower()[:30]}.pptx"),
                "fallback_reason": canva_error,
            },
            task_id
        )

    async def _handle_local_presentation(self, payload: dict, task_id: str) -> TaskResult:
        """Generate PowerPoint presentation locally using python-pptx."""
        from tools.office.pptx_tools import write_pptx
        from pathlib import Path

        title = payload.get("title") or payload.get("topic") or "Presentasi"
        output_path = payload.get("output_path") or f"/home/aseps/MCP/storage/reports/{title.replace(' ', '_').lower()[:30]}.pptx"
        
        # Ensure parent directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        slides_data = payload.get("slides", [])
        if not slides_data:
            # Generate default structured template slides
            slides_data = [
                {
                    "title": title,
                    "content": [
                        "Dibuat secara otomatis oleh DesignerAgent (Local Engine)",
                        f"Topik: {title}",
                        "Status: Siap dipresentasikan / disunting lebih lanjut"
                    ]
                },
                {
                    "title": "Agenda & Ruang Lingkup",
                    "content": [
                        "1. Latar Belakang & Pendahuluan",
                        "2. Analisis & Pembahasan Pokok",
                        "3. Rekomendasi Tindak Lanjut"
                    ]
                },
                {
                    "title": "Kesimpulan & Langkah Lanjut",
                    "content": [
                        "Poin kunci telah diidentifikasi secara komprehensif",
                        "Koordinasi lintas fungsi direkomendasikan untuk implementasi"
                    ]
                }
            ]

        result = write_pptx(file_path=output_path, slides=slides_data, title=title)
        
        if result.get("success"):
            return TaskResult.success_result(
                task_id=task_id,
                data={
                    **result,
                    "engine": "python-pptx-local",
                    "title": title,
                    "fallback_note": payload.get("fallback_reason"),
                },
                context={"agent": self.name, "action": "create_presentation", "tool": "python-pptx"}
            )
        else:
            return TaskResult.failure_result(
                task_id=task_id,
                error=result.get("error", "Local PPTX generation failed"),
                error_code="LOCAL_PPTX_ERROR"
            )

    async def _handle_preset_design(self, action: str, payload: dict, task_id: str) -> TaskResult:
        """Create specific Canva design preset (infographic, poster, banner, social_media)."""
        from tools.media.canva_tools import create_canva_design
        
        title = payload.get("title") or payload.get("topic") or "Visual Design"
        preset_map = {
            "infographic": "infographic",
            "infografis": "infographic",
            "poster": "poster",
            "banner": "banner",
            "social": "social_media",
            "social_media": "social_media"
        }
        
        preset_name = "presentation"
        for k, v in preset_map.items():
            if k in action:
                preset_name = v
                break

        try:
            design = create_canva_design(title=title, preset_name=preset_name)
            return TaskResult.success_result(
                task_id=task_id,
                data={
                    "success": True,
                    "title": title,
                    "preset": preset_name,
                    "design": design,
                    "url": design.get("url") or design.get("urls", {}).get("edit_url"),
                },
                context={"agent": self.name, "action": f"create_{preset_name}"}
            )
        except Exception as e:
            return TaskResult.failure_result(
                task_id=task_id,
                error=f"Canva design creation failed for preset {preset_name}: {str(e)}",
                error_code="CANVA_PRESET_ERROR"
            )

    async def _handle_image_search(self, payload: dict, task_id: str) -> TaskResult:
        """Search and curate images across Unsplash and Pexels."""
        from tools.media.unsplash_tools import search_unsplash_image
        from tools.media.pexels_tools import search_pexels_image

        query = payload.get("query") or payload.get("topic") or "technology"
        curated_results = {"query": query, "unsplash": None, "pexels": None}

        try:
            curated_results["unsplash"] = search_unsplash_image(query)
        except Exception as e:
            curated_results["unsplash"] = {"error": str(e)}

        try:
            curated_results["pexels"] = search_pexels_image(query)
        except Exception as e:
            curated_results["pexels"] = {"error": str(e)}

        return TaskResult.success_result(
            task_id=task_id,
            data=curated_results,
            context={"agent": self.name, "action": "curate_images"}
        )

