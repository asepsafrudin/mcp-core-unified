import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from sse_starlette.sse import EventSourceResponse

from .models import ChatRequest, ChatResponse, HealthResponse
from .dependencies import get_deps, DependencyContainer

router = APIRouter(prefix="/api/v1", tags=["LLM"])
logger = logging.getLogger(__name__)

@router.get("/health", response_model=HealthResponse)
async def health_check(deps: DependencyContainer = Depends(get_deps)):
    """Check the health of the LLM API and listing active providers."""
    return HealthResponse(
        status="ok",
        providers=list(deps.ai_manager._providers.keys()),
        active_provider=deps.ai_manager.current_provider.__class__.__name__,
        tools=[t['function']['name'] for t in deps.tool_definitions]
    )

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, deps: DependencyContainer = Depends(get_deps)):
    """
    Standard complete chat (blocking until full response).
    Supports agentic / tool calling via 'agentic' boolean.
    """
    provider = deps.ai_manager.current_provider
    if not provider:
        raise HTTPException(status_code=503, detail="No AI provider available")

    # If pure agentic
    if request.agentic:
        try:
            # We use Qwen logic (generate_with_tools) from the provider
            response_text = await provider.generate_with_tools(
                user_id=request.user_id,
                message=request.message,
                tools=deps.tool_definitions,
                tool_executor=deps.tool_executor,
                system_prompt=request.system_prompt
            )
            return ChatResponse(
                user_id=request.user_id,
                message=request.message,
                response=response_text,
                agentic=True
            )
        except Exception as e:
            logger.error(f"Agentic error: {e}")
            raise HTTPException(status_code=500, detail=f"Agentic error: {str(e)}")

    # Else normal completion mode (no tools)
    try:
        enriched_context = await deps.memory_service.build_enriched_context(
            user_id=request.user_id,
            message=request.message
        )
        
        # We need a buffering method if we want to strip think tags directly, 
        # or we just let it generate entirely
        raw_full = ""
        async for chunk in provider.generate_stream(
            user_id=request.user_id, 
            message=request.message, 
            context=enriched_context,
            system_prompt=request.system_prompt
        ):
            raw_full += chunk

        clean_response = raw_full
        if hasattr(provider, 'strip_thinking_tags'):
            clean_response = provider.strip_thinking_tags(raw_full)
        else:
            import re
            clean_response = re.sub(r'<think>.*?</think>', '', raw_full, flags=re.DOTALL|re.IGNORECASE).strip()
            
        if not clean_response:
            clean_response = raw_full.strip()

        # Save History
        await deps.memory_service.save_conversation(
            user_id=request.user_id,
            message=request.message,
            response=clean_response
        )

        return ChatResponse(
            user_id=request.user_id,
            message=request.message,
            response=clean_response,
            agentic=False
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest, deps: DependencyContainer = Depends(get_deps)):
    """
    Server-Sent Events (SSE) Streaming endpoint.
    Filters <think> tags effectively. Focus for Non-Agentic mode.
    """
    provider = deps.ai_manager.current_provider
    if not provider:
        raise HTTPException(status_code=503, detail="No AI provider available")

    # Currently we do not mix streaming and agentic loop 
    # Because LLM Function Calls usually need the stream to complete first.
    if request.agentic:
        # Fallback to standard chat but chunk the string
        # Actually it's better to just stream the final response word by word
        async def mock_agentic_stream():
            try:
                response = await provider.generate_with_tools(
                    user_id=request.user_id,
                    message=request.message,
                    tools=deps.tool_definitions,
                    tool_executor=deps.tool_executor,
                    system_prompt=request.system_prompt
                )
                
                # Yield word by word to emulate stream
                yield "data: {\"status\": \"started\"}\n\n"
                import asyncio
                for word in response.split(" "):
                    yield f"data: {json.dumps({'chunk': word+' '})}\n\n"
                    await asyncio.sleep(0.01)
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                
        return StreamingResponse(mock_agentic_stream(), media_type="text/event-stream")

    # Pure Streaming
    async def event_generator():
        yield "data: {\"status\": \"started\"}\n\n"
        
        try:
            enriched_context = await deps.memory_service.build_enriched_context(
                user_id=request.user_id,
                message=request.message
            )

            # In SSE Web, we can stream the thinking process as well if we want,
            # but usually frontend doesn't expect it. So let's buffer the whole thing
            # and stream. Alternatively, we could yield only after </think> tag is found.
            
            # Implementation of real-time think tag filtering
            in_think_block = False
            async for chunk in provider.generate_stream(
                user_id=request.user_id,
                message=request.message,
                context=enriched_context,
                system_prompt=request.system_prompt
            ):
                if "<think>" in chunk:
                    in_think_block = True
                    # If chunk mixes think, extract before <think>
                    before_think = chunk.split("<think>")[0]
                    if before_think.strip():
                        yield f"data: {json.dumps({'chunk': before_think})}\n\n"
                    continue
                    
                if "</think>" in chunk:
                    in_think_block = False
                    # Extract after </think>
                    after_think = chunk.split("</think>")[-1]
                    if after_think.strip():
                        yield f"data: {json.dumps({'chunk': after_think})}\n\n"
                    continue
                    
                if not in_think_block:
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"SSE Streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
