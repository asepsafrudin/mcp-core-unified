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
        - Presentation structuring
        - Canva Design API Orchestration
    """
    
    @property
    def profile(self) -> AgentProfile:
        return AgentProfile(
            name="designer_agent",
            description="Graphic Design and Presentation specialist (powered by Canva API)",
            domain="media_and_design",
            capabilities={
                AgentCapability.TOOL_USE,
                AgentCapability.SKILL_COMPOSITION,
                AgentCapability.PLANNING,
                AgentCapability.REASONING,
            },
            preferred_skills=[
                "create_canva_presentation_pipeline",
            ],
            tools_whitelist=[
                # === Media/Vision tools ===
                "search_unsplash_image",
                "download_unsplash_image",
                "search_pexels_image",
                "download_pexels_image",
                "upload_canva_asset",
                "create_canva_design",
                "vane_search",
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
            "design", "presentation", "presentasi", "ppt", "canva", "gambar", "image", "visual"
        }
        
        if any(dt in task_type for dt in design_tasks):
            return True
            
        payload_str = str(task.payload).lower()
        if any(dt in payload_str for dt in design_tasks):
            return True
            
        return False
        
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute design-related tasks using Canva pipeline.
        """
        from skills.media.graphic_design_skill import create_canva_presentation_pipeline
        
        payload = task.payload
        topic = payload.get("topic") or payload.get("query") or "Presentasi AI"
        images = payload.get("images", [])
        
        # Fallback to extract images from query if not provided
        if not images and "query" in payload:
            images = [topic + " background", topic + " modern"]
            
        try:
            print(f"[DesignerAgent] Executing with topic: {topic}, images: {images}")
            result = await create_canva_presentation_pipeline(
                topic=topic,
                image_queries=images
            )
            
            if result["errors"]:
                logger.warning(f"Pipeline completed with errors: {result['errors']}")
                
            return TaskResult.success_result(
                task_id=task.id,
                data=result,
                context={"agent": self.name, "action": "create_presentation", "tool": "canva"}
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[DesignerAgent] Failed: {e}")
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code="DESIGNER_AGENT_ERROR"
            )
