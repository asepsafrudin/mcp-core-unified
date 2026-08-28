"""
TASK-120: State dan response schema untuk IDE Hybrid Router.

Modul ini mendefinisikan:
- `IDEAgentState`: TypedDict untuk LangGraph state machine.
- `IDEResponse`: Pydantic model untuk response yang konsisten ke caller.
- Enum/helper untuk mode klasifikasi.
"""

from enum import Enum
from typing import Annotated, List, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
import operator


class IDEMode(str, Enum):
    """Mode klasifikasi task oleh IDE Hybrid Router."""

    LOCAL_TOOLS = "local_tools"
    ORCHESTRATOR = "orchestrator"
    GENERAL_CHAT = "general_chat"
    ERROR = "error"


class ToolCallRecord(BaseModel):
    """Satu record tool call yang dieksekusi oleh router."""

    tool: str = Field(..., description="Nama tool yang dipanggil.")
    arguments: dict = Field(default_factory=dict, description="Argumen tool.")
    result: str = Field(default="", description="Hasil eksekusi tool (ringkas).")
    success: bool = Field(default=True, description="Apakah tool sukses dieksekusi.")


class IDEAgentState(TypedDict):
    """
    State untuk LangGraph IDE Hybrid Router.
    """

    messages: Annotated[Sequence[BaseMessage], operator.add]
    task: str
    context: str
    conversation_id: str
    user_id: str
    mode: IDEMode
    tool_calls: List[ToolCallRecord]
    observations: List[str]
    final_answer: str
    token_usage: dict
    error: str


class IDEResponse(BaseModel):
    """
    Response standar dari IDE Hybrid Router ke caller (Agentic IDE / MCP client).
    """

    status: str = Field(..., description="ok | error")
    mode: IDEMode = Field(..., description="Mode yang dipilih router.")
    answer: str = Field(default="", description="Jawaban akhir untuk user.")
    tool_calls: List[ToolCallRecord] = Field(
        default_factory=list, description="Daftar tool call yang dieksekusi."
    )
    token_usage: dict = Field(default_factory=dict, description="Ringkasan token usage.")
    request_id: str = Field(default="", description="Conversation/request ID.")
    error: str = Field(default="", description="Error message jika status error.")

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "mode": self.mode.value,
            "answer": self.answer,
            "tool_calls": [tc.model_dump() for tc in self.tool_calls],
            "token_usage": self.token_usage,
            "request_id": self.request_id,
            "error": self.error,
        }
