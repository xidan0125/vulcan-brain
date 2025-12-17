"""
Vulcan Brain - 统一聊天 API v4
重构: 使用 AgentExecutor 编排架构
"""

from datetime import datetime, timezone
from typing import Optional, List, Literal, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import re
import httpx
import os
import asyncio
import logging

from auth_api import get_current_user
from vulcan_libs.llm_client import get_llm_client, ChatMessage, ModelType
from core.tools import execute_tool, get_tool_names, get_tool_schemas, ToolExecutor
from core.tools.base import ToolContext
from services.session_manager import get_session_manager
from services.context_manager import compact_session, should_compact, MAX_HISTORY_TURNS
from services.memory_service import get_memory_service
from services.memory_extractor import get_memory_extractor

# ==================== 编排层 V2 ====================
from core.orchestration import get_executor, EventType, StreamEvent

logger = logging.getLogger(__name__)

# Feature flags
USE_AGENT_EXECUTOR = True  # 开关: 使用新架构
FALLBACK_ON_ERROR = True   # 出错时回退到旧逻辑

# ==================== 异步记忆提取 ====================

async def extract_memories_async(user_id: str, session_id: str, message: str):
    """异步提取记忆 (不阻塞主响应)"""
    try:
        extractor = get_memory_extractor()
        svc = get_memory_service()
        
        extractions = await extractor.extract(message)
        
        if not extractions:
            return
        
        for ext in extractions:
            await svc.add_pending(
                user_id=user_id,
                session_id=session_id,
                key=ext["key"],
                value=ext["value"],
                category=ext.get("category", "fact"),
                confidence=ext.get("confidence", 0.8),
                context=message
            )
        
        logger.info(f"Extracted {len(extractions)} memories for user {user_id}")
    except Exception as e:
        logger.warning(f"Memory extraction failed: {e}")


# ==================== AgentExecutor 适配器 ====================

async def run_with_executor(
    user_input: str,
    history: List[dict],
    session_id: str = None
) -> AsyncGenerator[dict, None]:
    """
    使用 AgentExecutor 处理请求
    
    将 StreamEvent 转换为 SSE 事件格式
    """
    executor = get_executor()
    
    # 注入历史到 executor 的 session
    # (AgentExecutor 内部维护 session，这里同步外部历史)
    executor.session.clear()
    for msg in history:
        if msg.get("role") in ["user", "assistant"]:
            executor.session.add_message(msg["role"], msg.get("content", ""))
    
    # 执行
    print(f"[RUN_EXECUTOR] Starting process with input: {user_input[:30] if user_input else 'EMPTY'}")
    try:
        async for event in executor.process(user_input, session_id):
            print(f"[RUN_EXECUTOR] Got event: {event.type}")
            # 转换 StreamEvent -> SSE dict
            sse_event = _event_to_sse(event)
            if sse_event:
                yield sse_event
    except Exception as e:
        print(f"[RUN_EXECUTOR] Exception: {e}")
        import traceback
        traceback.print_exc()
        raise


def _event_to_sse(event: StreamEvent) -> Optional[dict]:
    """StreamEvent -> SSE 事件格式"""
    
    if event.type == EventType.ROUTING:
        return {
            "type": "routing",
            "intent": event.content,
            "model_tier": event.metadata.get("model_tier"),
            "reasoning": event.metadata.get("reasoning"),
            "use_tools": event.metadata.get("use_tools"),
            "confidence": event.metadata.get("confidence")
        }
    
    elif event.type == EventType.THINKING:
        return {
            "type": "thinking",
            "content": event.content
        }
    
    elif event.type == EventType.TOKEN:
        return {
            "type": "token",
            "content": event.content
        }
    
    elif event.type == EventType.TOOL_CALL:
        return {
            "type": "tool_call",
            "name": event.content,
            "arguments": event.metadata.get("arguments") or event.metadata.get("params"),
            "id": event.metadata.get("tool_call", {}).get("id", "tc_" + str(hash(event.content))[:8])
        }
    
    elif event.type == EventType.TOOL_RESULT:
        return {
            "type": "tool_result",
            "name": event.metadata.get("name"),
            "result": event.content,
            "success": event.metadata.get("success", True)
        }
    
    elif event.type == EventType.ANSWER:
        return {
            "type": "token",
            "content": event.content
        }
    
    elif event.type == EventType.ERROR:
        return {
            "type": "error",
            "content": event.content
        }
    
    elif event.type == EventType.DONE:
        return {
            "type": "done",
            "content": ""
        }
    
    return None


# ==================== 路由器 ====================

router = APIRouter(prefix="/unified-chat", tags=["Unified Chat"])

# ==================== 配置 ====================

MAX_TOOL_ITERATIONS = 5
QWEN3_BASE_URL = "http://localhost:8000/v1"

def _get_vllm_model():
    try:
        resp = httpx.get(f"{QWEN3_BASE_URL}/models", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            if models:
                return models[0]["id"]
    except:
        pass
    return os.getenv("QWEN3_MODEL", "default-model")

QWEN3_MODEL = _get_vllm_model()


# ==================== 请求/响应模型 ====================

class MessageInput(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class ChatRequest(BaseModel):
    messages: List[MessageInput]
    model: Literal["gemini", "qwen3"] = "qwen3"
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 4096
    enable_search: bool = False
    enable_tools: bool = False
    session_id: Optional[str] = None
    agent_id: Optional[str] = None


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: str


class ChatResponse(BaseModel):
    content: str
    model: str
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    session_id: Optional[str] = None
    timestamp: str


class SessionInfo(BaseModel):
    session_id: str
    agent_id: str
    message_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    summary: Optional[str] = None


# ==================== Session 端点 ====================

@router.get("/sessions")
async def list_sessions(
    current_user: dict = Depends(get_current_user)
) -> List[SessionInfo]:
    manager = get_session_manager()
    user_id = current_user.get("user_id", current_user.get("username", "anonymous"))
    sessions = await manager.get_user_sessions(user_id)
    
    return [
        SessionInfo(
            session_id=s["session_id"],
            agent_id=s.get("agent_id", "general"),
            message_count=s.get("message_count", 0),
            created_at=s.get("created_at"),
            updated_at=s.get("updated_at"),
            summary=s.get("summary")
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
) -> SessionInfo:
    manager = get_session_manager()
    session = await manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionInfo(
        session_id=session["session_id"],
        agent_id=session.get("agent_id", "general"),
        message_count=session.get("message_count", 0),
        created_at=session.get("created_at"),
        updated_at=session.get("updated_at"),
        summary=session.get("summary")
    )


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    max_turns: int = 50,
    current_user: dict = Depends(get_current_user)
):
    manager = get_session_manager()
    history = await manager.get_history(session_id, max_turns=max_turns)
    return {"session_id": session_id, "messages": history}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    manager = get_session_manager()
    await manager.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


# ==================== 核心聊天端点 ====================

@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    统一聊天接口 (流式) - V4 使用 AgentExecutor
    
    SSE 事件类型:
    - {"type": "session", "session_id": "..."} - 会话ID
    - {"type": "routing", ...} - 路由决策 (intent, model_tier)
    - {"type": "thinking", "content": "..."} - 思考过程
    - {"type": "token", "content": "..."} - 文本 token
    - {"type": "tool_call", ...} - 工具调用
    - {"type": "tool_result", ...} - 工具结果
    - {"type": "done", "content": ""} - 完成
    - {"type": "error", "content": "..."} - 错误
    """
    user_id = current_user.get("user_id", current_user.get("username", "anonymous"))
    manager = get_session_manager()
    
    async def generate():
        try:
            # 1. 获取或创建 Session
            session = await manager.get_or_create_session(
                user_id=user_id,
                session_id=request.session_id,
                agent_id=request.agent_id or "general"
            )
            session_id = session["_id"]
            
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
            
            # 2. 获取历史消息
            history = await manager.get_history(session_id, max_turns=MAX_HISTORY_TURNS)
            
            # 3. 注入记忆上下文
            try:
                memory_service = get_memory_service()
                memory_context = await memory_service.build_context(user_id)
                
                system_msg = "你是 Vulcan Brain AI 助手，专注于高效完成用户任务。"
                if memory_context:
                    system_msg += f"\n\n[用户记忆]\n{memory_context}\n[/用户记忆]"
                
                if history and history[0].get("role") == "system":
                    history[0]["content"] = system_msg + "\n\n" + history[0]["content"]
                else:
                    history.insert(0, {"role": "system", "content": system_msg})
            except Exception as e:
                logger.warning(f"Memory context injection failed: {e}")
            
            # 4. 提取当前用户消息
            current_user_msg = None
            for m in reversed(request.messages):
                if m.role == "user":
                    current_user_msg = m.content
                    break
            
            if current_user_msg:
                await manager.add_message(session_id, "user", current_user_msg)
                history.append({"role": "user", "content": current_user_msg})
            
            # 5. 使用 AgentExecutor 处理 ========== 核心变化 ==========
            full_response = ""
            
            if USE_AGENT_EXECUTOR:
                try:
                    async for event in run_with_executor(current_user_msg or "", history, session_id):
                        if event.get("type") == "token":
                            full_response += event.get("content", "")
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except Exception as e:
                    logger.exception("AgentExecutor failed")
                    if FALLBACK_ON_ERROR:
                        yield f"data: {json.dumps({'type': 'error', 'content': f'Executor error: {e}, falling back'})}\n\n"
                        # 回退到旧逻辑
                        async for event in _legacy_chat(request, history):
                            if event.get("type") == "token":
                                full_response += event.get("content", "")
                            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            else:
                # 旧逻辑 (feature flag off)
                async for event in _legacy_chat(request, history):
                    if event.get("type") == "token":
                        full_response += event.get("content", "")
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            
            # 6. 保存助手响应
            if full_response:
                await manager.add_message(session_id, "assistant", full_response)
            
            # 7. 异步提取记忆
            if current_user_msg:
                asyncio.create_task(extract_memories_async(user_id, session_id, current_user_msg))
            
            # 8. 检查压缩
            session = await manager.get_session(session_id)
            if session and should_compact(session.get("message_count", 0), session.get("is_compacted", False)):
                asyncio.create_task(compact_session(manager, session_id))
        
        except Exception as e:
            logger.exception("Chat stream error")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ==================== 旧版逻辑 (回退用) ====================

async def _legacy_chat(request: ChatRequest, history: List[dict]) -> AsyncGenerator[dict, None]:
    """旧版 ReAct 聊天逻辑 (回退用)"""
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    tools = get_tool_schemas() if request.enable_tools else []
    
    iteration = 0
    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1
        
        response = await _call_qwen3_with_tools(
            messages=messages,
            tools=tools,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        assistant_msg = response["choices"][0]["message"]
        tool_calls = assistant_msg.get("tool_calls", [])
        content = assistant_msg.get("content", "")
        
        if not tool_calls:
            # 最终回复
            if content:
                thinking, final = _parse_thinking(content)
                if thinking:
                    yield {"type": "thinking", "content": thinking}
                if final:
                    yield {"type": "token", "content": final}
            yield {"type": "done", "content": ""}
            return
        
        # 有工具调用
        if content:
            yield {"type": "thinking", "content": content}
        
        messages.append(assistant_msg)
        
        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            tool_args = tc["function"]["arguments"]
            tool_id = tc["id"]
            
            yield {"type": "tool_call", "id": tool_id, "name": tool_name, "arguments": tool_args}
            
            ctx = ToolContext(user_id="system", permissions=["execute_destructive"])
            result_obj = await ToolExecutor.execute_async(tool_name, tool_args, ctx)
            result = result_obj.to_llm_string()
            
            yield {"type": "tool_result", "id": tool_id, "name": tool_name, "result": result}
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "name": tool_name,
                "content": result
            })
    
    yield {"type": "token", "content": "\n\n[达到最大工具调用轮数]"}
    yield {"type": "done", "content": ""}


async def _call_qwen3_with_tools(
    messages: List[dict],
    tools: List[dict],
    temperature: float = 0.7,
    max_tokens: int = 4096
) -> dict:
    """调用 Qwen3 vLLM API"""
    # 禁用思考
    processed = []
    for i, msg in enumerate(messages):
        if i == 0 and msg.get("role") == "system":
            processed.append({"role": "system", "content": msg.get("content", "") + " /no_think"})
        else:
            processed.append(msg)
    
    if not processed or processed[0].get("role") != "system":
        processed.insert(0, {"role": "system", "content": "你是一个高效的AI助手。/no_think"})
    
    payload = {
        "model": QWEN3_MODEL,
        "messages": processed,
        "tools": tools if tools else None,
        "tool_choice": "auto" if tools else None,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    # 清理 None 值
    payload = {k: v for k, v in payload.items() if v is not None}
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{QWEN3_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()


def _parse_thinking(content: str) -> tuple:
    """解析 </think> 标签"""
    match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
    if match:
        thinking = match.group(1).strip()
        final = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        return thinking, final
    return None, content


# ==================== 同步聊天 ====================

@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """统一聊天接口 (同步)"""
    client = get_llm_client()
    
    messages = [ChatMessage(role=m.role, content=m.content) for m in request.messages]
    model_type = ModelType.GEMINI if request.model == "gemini" else ModelType.QWEN3
    
    try:
        response = await client.chat(
            messages=messages,
            model=model_type,
            stream=False,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            enable_search=request.enable_search
        )
        
        return ChatResponse(
            content=response.content,
            model=response.model,
            finish_reason=response.finish_reason,
            session_id=request.session_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 健康检查 ====================

@router.get("/health")
async def health_check():
    manager = get_session_manager()
    
    status = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "architecture": "AgentExecutor v4" if USE_AGENT_EXECUTOR else "Legacy",
        "models": {},
        "tools_enabled": True,
        "available_tools": get_tool_names(),
        "session_enabled": True
    }
    
    # 检查 GPU (8000)
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get(f"{QWEN3_BASE_URL}/models")
            status["models"]["gpu"] = "online" if resp.status_code == 200 else "error"
    except:
        status["models"]["gpu"] = "offline"
    
    # 检查 CPU (8002)
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get("http://localhost:8002/v1/models")
            status["models"]["cpu"] = "online" if resp.status_code == 200 else "error"
    except:
        status["models"]["cpu"] = "offline"
    
    return status


# ==================== 模型信息 ====================

@router.get("/models")
async def list_models():
    return {
        "models": [
            {"id": "qwen3", "name": "Qwen3-30B (GPU)", "tier": "gpu", "local": True},
            {"id": "qwen3-cpu", "name": "Qwen3-8B (CPU)", "tier": "cpu", "local": True},
            {"id": "gemini", "name": "Gemini (Cloud)", "tier": "cloud", "local": False}
        ]
    }


# ==================== 工具信息 ====================

@router.get("/tools")
async def list_tools():
    return {
        "tools": get_tool_names(),
        "count": len(get_tool_names())
    }
