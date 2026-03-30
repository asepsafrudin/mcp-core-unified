from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    user_id: int = Field(default=123456789, description="Unique ID of the user or session (integer required by Telegram's memory_service)")
    message: str = Field(..., description="The user's input message")
    agentic: bool = Field(default=False, description="Whether to use the agentic ToolExecutor for function calling")
    stream: bool = Field(default=False, description="Whether to stream the response via Server-Sent Events (SSE)")
    system_prompt: Optional[str] = Field(default=None, description="Optional custom system prompt addition")

class ChatResponse(BaseModel):
    user_id: int
    message: str
    response: str
    agentic: bool
    used_tools: Optional[List[str]] = None

class HealthResponse(BaseModel):
    status: str
    providers: List[str]
    active_provider: str
    tools: List[str]
