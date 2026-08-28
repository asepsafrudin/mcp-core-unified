"""
TASK-120: IDE Hybrid Router berbasis LangGraph.

Router ini menerima task dari Agentic IDE (Cline/Kimi), mengklasifikasikannya,
dan mengeksekusinya dengan salah satu dari tiga jalur:
1. `local_tools` — jalankan tools MCP lokal via ReAct agent.
2. `orchestrator` — delegasikan ke services/ai-orchestrator untuk RAG/memory/web.
3. `general_chat` — jawab langsung via LLM.
"""

import asyncio
import inspect
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool, ToolException
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import create_model

# Ensure project root is available for imports when this module is imported standalone
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from execution import registry
from execution.registry import ALLOWED_CATEGORIES
from intelligence.ide_agent_state import IDEAgentState, IDEMode, IDEResponse, ToolCallRecord
from tools.orchestrator_bridge import call_ai_orchestrator_sync


def _webhook_secret() -> str:
    return os.getenv("MCP_WEBHOOK_SECRET") or os.getenv("WEBHOOK_SECRET") or ""


# =============================================================================
# Keyword-based classification heuristics
# =============================================================================

_LOCAL_TOOLS_KEYWORDS = [
    r"\bfile\b", r"\bfiles?\b", r"\bread\b", r"\bwrite\b", r"\bedit\b",
    r"\bcreate\b", r"\bdelete\b", r"\bmove\b", r"\bcopy\b", r"\bfind\b",
    r"\bgrep\b", r"\bsearch\b", r"\bcode\b", r"\bkode\b", r"\brefactor\b",
    r"\bfix\b", r"\brun\b", r"\bexecute\b", r"\bshell\b", r"\bterminal\b",
    r"\bcommand\b", r"\bperintah\b", r"\bls\b", r"\bdir\b", r"\bpath\b",
    r"\bsyntax\b", r"\blint\b", r"\btest\b", r"\bpytest\b",
]
_LOCAL_TOOLS_PATTERN = re.compile("|".join(_LOCAL_TOOLS_KEYWORDS), re.IGNORECASE)

_ORCHESTRATOR_KEYWORDS = [
    r"\bregulasi\b", r"\buu\b", r"\bundang[-\s]?undang\b", r"\bperda\b",
    r"\bpermen\b", r"\bpasal\b", r"\bayat\b", r"\bpuu\b",
    r"\bknowledge\b", r"\bpengetahuan\b", r"\bingest\b", r"\bnamespace\b",
    r"\bmemori\b", r"\bmemory\b", r"\bltm\b", r"\bingat\b",
    r"\bweb\b", r"\binternet\b", r"\bcari di\b", r"\bsummarize\b", r"\bringkasan\b",
    r"\bkontak\b", r"\bcontact\b", r"\bwhatsapp\b", r"\bwa\b",
    r"\bmeeting\b", r"\brapat\b", r"\bdisposisi\b", r"\bagenda\b",
    r"\bghs\b", r"\bronda\b", r"\biuran\b",
    r"\bjam\b", r"\bwaktu\b", r"\btanggal\b", r"\bhari\b", r"\bsekarang\b",
    r"\btime\b", r"\bdate\b", r"\bclock\b",
]
_ORCHESTRATOR_PATTERN = re.compile("|".join(_ORCHESTRATOR_KEYWORDS), re.IGNORECASE)


def _detect_mode(task: str) -> IDEMode:
    """Klasifikasikan task ke mode berdasarkan keyword heuristic."""
    if not task or not isinstance(task, str):
        return IDEMode.GENERAL_CHAT

    text = task.lower()

    # Local tools: file/shell/code operations
    if _LOCAL_TOOLS_PATTERN.search(text):
        return IDEMode.LOCAL_TOOLS

    # Orchestrator: knowledge, memory, web, contacts, office, regulations
    if _ORCHESTRATOR_PATTERN.search(text):
        return IDEMode.ORCHESTRATOR

    return IDEMode.GENERAL_CHAT


# =============================================================================
# Tool wrapping: expose execution.registry tools to LangGraph ReAct agent
# =============================================================================

def _create_safe_args_schema(func: Any, model_name: str):
    sig = inspect.signature(func)
    fields = {}
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "args", "kwargs"):
            continue
        field_type = str
        if param.annotation != inspect.Parameter.empty:
            if param.annotation == str:
                field_type = str
            elif param.annotation == int:
                field_type = int
            elif param.annotation == float:
                field_type = float
            elif param.annotation == bool:
                field_type = bool
            elif param.annotation == list:
                field_type = list
            elif param.annotation == dict:
                field_type = dict
            else:
                field_type = Any
        if param.default == inspect.Parameter.empty:
            fields[param_name] = (field_type, ...)
        else:
            fields[param_name] = (field_type, param.default)
    return create_model(model_name, **fields)


@lru_cache(maxsize=1)
def _get_local_tools() -> List[StructuredTool]:
    """Wrap execution.registry tools into LangChain StructuredTool instances."""
    tools: List[StructuredTool] = []
    if not registry:
        return tools

    registered_tools = registry.list_tools()
    for t in registered_tools:
        tool_name = t["name"]
        if not any(tool_name.startswith(p) for p in ALLOWED_CATEGORIES):
            continue
        if len(tools) >= 128:
            break

        tool_desc = t.get("description", "MCP Tool")
        tool_func = registry.get_tool(tool_name)
        if not tool_func:
            continue

        try:

            def _sync_wrapper_factory(name=tool_name):
                def sync_wrapper(*args, **kwargs) -> Any:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            result = [None]
                            err = [None]

                            def run_in_thread():
                                new_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(new_loop)
                                try:
                                    result[0] = new_loop.run_until_complete(registry.execute(name, kwargs))
                                except Exception as e:
                                    err[0] = e
                                finally:
                                    new_loop.close()

                            import threading

                            t_thread = threading.Thread(target=run_in_thread)
                            t_thread.start()
                            t_thread.join()
                            if err[0]:
                                raise err[0]
                            return result[0]
                        else:
                            return loop.run_until_complete(registry.execute(name, kwargs))
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        return loop.run_until_complete(registry.execute(name, kwargs))
                    except Exception as e:
                        raise ToolException(f"Error calling MCP tool '{name}': {e}")

                return sync_wrapper

            safe_schema = _create_safe_args_schema(tool_func, f"{tool_name}_schema")
            lc_tool = StructuredTool(
                name=tool_name,
                description=tool_desc,
                func=_sync_wrapper_factory(tool_name),
                args_schema=safe_schema,
                handle_tool_error=True,
            )

            async def _arun_wrapper(name=tool_name, **kwargs):
                return await registry.execute(name, kwargs)

            lc_tool._arun = _arun_wrapper
            tools.append(lc_tool)
        except Exception as e:
            print(f"[IDERouter] Failed to wrap tool '{tool_name}': {e}")

    return tools


def _get_llm() -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY tidak dikonfigurasi")
    return ChatOpenAI(api_key=api_key, model="gpt-4o", temperature=0, timeout=30, max_retries=2)


# =============================================================================
# LangGraph nodes
# =============================================================================

def classify_node(state: IDEAgentState) -> dict:
    """Klasifikasikan task ke mode yang sesuai."""
    mode = _detect_mode(state["task"])
    print(f"[IDERouter] Classified mode={mode.value} for task: {state['task'][:80]}...")
    return {"mode": mode}


def route_by_mode(state: IDEAgentState) -> str:
    return state["mode"].value


async def local_tools_node(state: IDEAgentState) -> dict:
    """Jalankan ReAct agent dengan tools lokal dari execution.registry."""
    print("[IDERouter] Executing via local_tools")
    try:
        llm = _get_llm()
        tools = _get_local_tools()
        if not tools:
            return {
                "final_answer": "Tidak ada tools lokal yang tersedia saat ini.",
                "tool_calls": [],
                "token_usage": {},
            }

        agent = create_react_agent(llm, tools)
        system_msg = SystemMessage(
            content=(
                "Kamu adalah coding assistant untuk Agentic IDE. "
                "Gunakan tools yang tersedia untuk menjawab task user. "
                "Jika butuh membaca banyak file, gunakan search/grep terlebih dahulu. "
                "Jawaban akhir harus ringkas dan actionable."
            )
        )
        messages = [system_msg, HumanMessage(content=state["task"])]
        result = await agent.ainvoke({"messages": messages}, config={"recursion_limit": 12})

        # Extract tool calls from messages for observability
        tool_calls: List[ToolCallRecord] = []
        for msg in result.get("messages", []):
            if isinstance(msg, ToolMessage):
                tool_calls.append(
                    ToolCallRecord(
                        tool=msg.name or "unknown",
                        arguments={},
                        result=str(msg.content)[:500],
                        success=True,
                    )
                )

        final_msg = result["messages"][-1]
        answer = final_msg.content if isinstance(final_msg, (AIMessage, BaseMessage)) else str(final_msg)
        return {
            "final_answer": answer,
            "tool_calls": tool_calls,
            "token_usage": {},
        }
    except Exception as e:
        return {
            "final_answer": f"",
            "tool_calls": [],
            "token_usage": {},
            "error": f"local_tools error: {e}",
        }


async def orchestrator_node(state: IDEAgentState) -> dict:
    """Delegasikan task ke AI Orchestrator."""
    print("[IDERouter] Delegating to ai-orchestrator")
    try:
        result = await call_ai_orchestrator_sync(
            message=state["task"],
            user_id=state.get("user_id", "ide-agent"),
            platform="ide",
            context=state.get("context", ""),
            conversation_id=state.get("conversation_id"),
        )
        return {
            "final_answer": result.get("response", ""),
            "tool_calls": [
                ToolCallRecord(
                    tool="call_ai_orchestrator_sync",
                    arguments={"message": state["task"]},
                    result=f"status={result.get('status')}",
                    success=result.get("status") == "ok",
                )
            ],
            "token_usage": {},
            "error": result.get("error", ""),
        }
    except Exception as e:
        return {
            "final_answer": "",
            "tool_calls": [],
            "token_usage": {},
            "error": f"orchestrator delegation error: {e}",
        }


async def general_chat_node(state: IDEAgentState) -> dict:
    """Jawab langsung via LLM tanpa tools."""
    print("[IDERouter] General chat")
    try:
        llm = _get_llm()
        messages = [
            SystemMessage(content="Kamu adalah asisten AI untuk Agentic IDE. Jawab dengan ringkas dan jelas."),
            HumanMessage(content=state["task"]),
        ]
        res = await llm.ainvoke(messages)
        return {
            "final_answer": res.content,
            "tool_calls": [],
            "token_usage": {},
        }
    except Exception as e:
        return {
            "final_answer": "",
            "tool_calls": [],
            "token_usage": {},
            "error": f"general_chat error: {e}",
        }


def synthesizer_node(state: IDEAgentState) -> dict:
    """Finalisasi output; tidak melakukan transformasi signifikan."""
    return {}


# =============================================================================
# Build graph
# =============================================================================

workflow = StateGraph(IDEAgentState)
workflow.add_node("classify", classify_node)
workflow.add_node("local_tools", local_tools_node)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("general_chat", general_chat_node)
workflow.add_node("synthesizer", synthesizer_node)

workflow.set_entry_point("classify")
workflow.add_conditional_edges(
    "classify",
    route_by_mode,
    {
        IDEMode.LOCAL_TOOLS.value: "local_tools",
        IDEMode.ORCHESTRATOR.value: "orchestrator",
        IDEMode.GENERAL_CHAT.value: "general_chat",
    },
)
workflow.add_edge("local_tools", "synthesizer")
workflow.add_edge("orchestrator", "synthesizer")
workflow.add_edge("general_chat", "synthesizer")
workflow.add_edge("synthesizer", END)

compiled_ide_router = workflow.compile()


# =============================================================================
# Public entry point
# =============================================================================

async def run_ide_agent(
    task: str,
    context: str = "",
    user_id: str = "ide-agent",
    conversation_id: str = "",
) -> IDEResponse:
    """
    Entry point utama untuk Agentic IDE.

    Args:
        task: Task/pesan dari user IDE.
        context: Konteks tambahan (misalnya file yang sedang diedit).
        user_id: Identifier user/session.
        conversation_id: ID percakapan untuk tracing.

    Returns:
        IDEResponse dengan mode, jawaban, dan metadata tool calls.
    """
    import uuid as _uuid

    if not conversation_id:
        conversation_id = str(_uuid.uuid4())

    initial_state: IDEAgentState = {
        "messages": [HumanMessage(content=task)],
        "task": task,
        "context": context,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "mode": IDEMode.GENERAL_CHAT,  # default, akan di-overwrite oleh classify_node
        "tool_calls": [],
        "observations": [],
        "final_answer": "",
        "token_usage": {},
        "error": "",
    }

    try:
        result = await compiled_ide_router.ainvoke(initial_state)
        status = "error" if result.get("error") else "ok"
        return IDEResponse(
            status=status,
            mode=result.get("mode", IDEMode.GENERAL_CHAT),
            answer=result.get("final_answer", ""),
            tool_calls=result.get("tool_calls", []),
            token_usage=result.get("token_usage", {}),
            request_id=conversation_id,
            error=result.get("error", ""),
        )
    except Exception as e:
        return IDEResponse(
            status="error",
            mode=IDEMode.ERROR,
            answer="",
            tool_calls=[],
            token_usage={},
            request_id=conversation_id,
            error=f"Router error: {e}",
        )
