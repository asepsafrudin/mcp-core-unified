"""
Message Worker

Background worker untuk message processing.
Mendukung chunking dan progressive loading untuk pesan panjang.
"""

import logging
from typing import Any

from .base import BaseWorker, WorkerTask

logger = logging.getLogger(__name__)


class MessageWorker(BaseWorker):
    """
    Worker untuk message processing.
    
    Handles:
    - Long message chunking
    - Progressive loading
    - AI processing dengan streaming
    """
    
    def __init__(
        self,
        ai_manager,
        messaging_service,
        max_workers: int = 4,
        chunk_size: int = 4000
    ):
        super().__init__(max_workers=max_workers, chunk_size=chunk_size)
        self.ai_manager = ai_manager
        self.messaging_service = messaging_service
    
    async def execute(self, task: WorkerTask) -> Any:
        """
        Execute message processing task.
        
        Task types:
        - "process_message": Process text message dengan AI
        - "send_chunked": Send long message in chunks
        - "stream_response": Stream AI response
        """
        task_type = task.type
        payload = task.payload
        
        if task_type == "process_message":
            return await self._process_message(payload)
        elif task_type == "send_chunked":
            return await self._send_chunked(payload)
        elif task_type == "stream_response":
            return await self._stream_response(payload)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    async def _process_message(self, payload: dict) -> dict:
        """Process message dengan AI."""
        user_id = payload["user_id"]
        message = payload["message"]
        context = payload.get("context", "")
        
        ai_provider = self.ai_manager.current_provider
        if not ai_provider:
            raise RuntimeError("No AI provider available")
        
        # Generate response
        response = await ai_provider.generate_response(
            user_id=user_id,
            message=message,
            context=context
        )
        
        return {
            "text": response.text,
            "model": response.model,
            "provider": response.provider
        }
    
    async def _send_chunked(self, payload: dict) -> dict:
        """Send long message in chunks."""
        chat_id = payload["chat_id"]
        text = payload["text"]
        send_func = payload["send_func"]
        
        chunks = self.messaging_service.chunk_message(text)
        sent_count = 0
        
        for chunk in chunks:
            await send_func(chat_id, chunk.content)
            sent_count += 1
        
        return {
            "chunks_sent": sent_count,
            "total_chunks": len(chunks)
        }
    
    async def _stream_response(self, payload: dict) -> dict:
        """Stream AI response dengan progress updates."""
        user_id = payload["user_id"]
        message = payload["message"]
        context = payload.get("context", "")
        progress_callback = payload.get("progress_callback")
        
        ai_provider = self.ai_manager.current_provider
        if not ai_provider:
            raise RuntimeError("No AI provider available")
        
        full_response = ""
        chunk_count = 0
        
        async for chunk in ai_provider.generate_stream(
            user_id=user_id,
            message=message,
            context=context
        ):
            full_response += chunk
            chunk_count += 1
            
            # Report progress
            if progress_callback and chunk_count % 5 == 0:
                await progress_callback({
                    "chunks": chunk_count,
                    "current_text": full_response[:200] + "..." if len(full_response) > 200 else full_response
                })
        
        return {
            "text": full_response,
            "chunks": chunk_count
        }
