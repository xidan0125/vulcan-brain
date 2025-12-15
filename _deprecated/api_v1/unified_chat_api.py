"""
Vulcan Brain - 统一聊天 API v3
支持 ReAct 工具调用 + Session 持久化 + 思考内容分离
"""

from datetime import datetime, timezone
from typing import Optional, List, Literal, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import httpx
import os

from auth_api import get_current_user
from vulcan_libs.llm_client import get_llm_client, ChatMessage, ModelType, StreamChunk
from tool_definitions import TOOL_DEFINITIONS, execute_tool, get_tool_names
from services.session_manager import get_session_manager
from services.context_manager import compact_session, should_compact, build_context, MAX_HISTORY_TURNS
from services.memory_service import get_memory_service

# ==================== 路由器 ====================

router = APIRouter(prefix="/unified-chat", tags=["Unified Chat"])

# ==================== 配置 ====================

MAX_TOOL_ITERATIONS = 5
MAX_HISTORY_TURNS = 20  # 最大历史轮数
QWEN3_BASE_URL = "http://localhost:8000/v1"
# 动态获取 vllm 模型名
def _get_vllm_model():
    try:
        import httpx
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
    """统一聊天请求"""
    messages: List[MessageInput]
    model: Literal["gemini", "qwen3"] = "qwen3"
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 4096
    enable_search: bool = False
    enable_tools: bool = False
    session_id: Optional[str] = None  # 传入则继续会话，不传则新建
    agent_id: Optional[str] = None


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: str


class ChatResponse(BaseModel):
    """聊天响应"""
    content: str
    model: str
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    session_id: Optional[str] = None
    timestamp: str


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    agent_id: str
    message_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    summary: Optional[str] = None


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    description: str
    features: List[str]
    is_local: bool


# ==================== Session 端点 ====================

@router.get("/sessions")
async def list_sessions(
    current_user: dict = Depends(get_current_user)
) -> List[SessionInfo]:
    """获取用户的会话列表"""
    manager = get_session_manager()
    user_id = current_user.get("user_id", current_user.get("username", "anonymous"))
    sessions = await manager.get_user_sessions(user_id)

    return [
        SessionInfo(
            session_id=s["session_id"],
            agent_id=s["agent_id"],
            message_count=s["message_count"],
            created_at=s["created_at"].isoformat() if s.get("created_at") else None,
            updated_at=s["updated_at"].isoformat() if s.get("updated_at") else None,
            summary=s.get("summary")
        )
        for s in sessions
    ]


@router.post("/sessions")
async def create_session(
    agent_id: str = "general",
    current_user: dict = Depends(get_current_user)
) -> SessionInfo:
    """创建新会话"""
    manager = get_session_manager()
    user_id = current_user.get("user_id", current_user.get("username", "anonymous"))

    session_id = await manager.create_session(user_id, agent_id)
    session = await manager.get_session(session_id)

    return SessionInfo(
        session_id=session_id,
        agent_id=agent_id,
        message_count=0,
        created_at=session["created_at"].isoformat() if session.get("created_at") else None,
        updated_at=session["updated_at"].isoformat() if session.get("updated_at") else None
    )


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取会话详情"""
    manager = get_session_manager()
    session = await manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除会话"""
    manager = get_session_manager()
    success = await manager.delete_session(session_id)

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"status": "deleted", "session_id": session_id}


# ==================== 聊天端点 ====================

@router.get("/models")
async def list_models() -> List[ModelInfo]:
    """列出可用模型"""
    return [
        ModelInfo(
            id="gemini",
            name="Gemini",
            description="Google Gemini 云端模型，支持联网搜索",
            features=["联网搜索", "多模态", "长上下文"],
            is_local=False
        ),
        ModelInfo(
            id="qwen3",
            name="Qwen3-Coder",
            description="本地 Qwen3-Coder 模型，支持工具调用",
            features=["代码生成", "工具调用", "快速响应", "本地运行"],
            is_local=True
        )
    ]


@router.get("/tools")
async def list_tools():
    """列出可用工具"""
    return {
        "tools": get_tool_names(),
        "definitions": TOOL_DEFINITIONS
    }


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    统一聊天接口 (流式 + ReAct + Session + 思考内容分离)

    SSE 事件类型:
    - {"type": "session", "session_id": "..."} - 会话ID (首个事件)
    - {"type": "thinking", "content": "..."} - 思考过程 (新增!)
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

            # 发送 session_id
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

            # 2. 获取历史消息 (截断到最大轮数)
            history = await manager.get_history(session_id, max_turns=MAX_HISTORY_TURNS)

            # 2.5 注入记忆上下文 (如果有)
            try:
                memory_service = get_memory_service()
                memory_context = await memory_service.build_context(user_id)
                if memory_context:
                    # 在历史开头插入 system 消息
                    system_msg = f"[用户记忆]\n{memory_context}\n[/用户记忆]"
                    # 检查是否已有 system 消息
                    if history and history[0].get("role") == "system":
                        # 合并到现有 system 消息
                        history[0]["content"] = system_msg + "\n\n" + history[0]["content"]
                    else:
                        # 插入新 system 消息
                        history.insert(0, {"role": "system", "content": system_msg})
            except Exception as e:
                import logging
                logging.warning(f"Memory context injection failed: {e}")

            # 3. 合并历史 + 当前消息
            # 只取当前请求的最后一条 user 消息
            current_user_msg = None
            for m in reversed(request.messages):
                if m.role == "user":
                    current_user_msg = m.content
                    break

            if current_user_msg:
                # 保存用户消息到 session
                await manager.add_message(session_id, "user", current_user_msg)
                history.append({"role": "user", "content": current_user_msg})

            # 4. 调用 LLM
            full_response = ""

            if False:  # TEMP: tools disabled until vLLM restart
                # if request.model == "qwen3" and request.enable_tools:
                async for event in react_chat_stream_with_history(request, history):
                    if event["type"] == "token":
                        full_response += event.get("content", "")
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            else:
                async for event in simple_chat_stream_with_history(request, history):
                    if event["type"] == "token":
                        full_response += event.get("content", "")
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # 5. 保存助手响应到 session
            if full_response:
                await manager.add_message(session_id, "assistant", full_response)

            # 检查是否需要压缩 (异步执行，不阻塞响应)
            session = await manager.get_session(session_id)
            if session and should_compact(session.get("message_count", 0), session.get("is_compacted", False)):
                import asyncio
                asyncio.create_task(compact_session(manager, session_id))

        except Exception as e:
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


# ==================== 简单聊天 (无工具) ====================

async def simple_chat_stream_with_history(
    request: ChatRequest,
    history: List[dict]
) -> AsyncGenerator[dict, None]:
    """
    简单流式聊天，使用历史上下文
    新增: 思考内容分离 (返回 thinking 和 token 两种事件)
    """
    client = get_llm_client()

    messages = [
        ChatMessage(role=m["role"], content=m["content"])
        for m in history
    ]

    model_type = ModelType.GEMINI if request.model == "gemini" else ModelType.QWEN3

    stream = await client.chat(
        messages=messages,
        model=model_type,
        stream=True,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        enable_search=request.enable_search,
        enable_thinking=True  # 启用思考内容分离
    )

    async for chunk in stream:
        # 新格式: StreamChunk 对象
        if isinstance(chunk, StreamChunk):
            if chunk.type == "thinking":
                yield {"type": "thinking", "content": chunk.text}
            else:  # content
                yield {"type": "token", "content": chunk.text}
        else:
            # 向后兼容: 纯字符串
            yield {"type": "token", "content": chunk}

    yield {"type": "done", "content": ""}


# ==================== ReAct 聊天 (带工具) ====================

async def react_chat_stream_with_history(
    request: ChatRequest,
    history: List[dict]
) -> AsyncGenerator[dict, None]:
    """ReAct 流式聊天，使用历史上下文"""
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    iteration = 0

    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1

        response = await call_qwen3_with_tools(
            messages=messages,
            tools=TOOL_DEFINITIONS,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        assistant_message = response["choices"][0]["message"]
        tool_calls = assistant_message.get("tool_calls", [])
        content = assistant_message.get("content", "")

        if content:
            yield {"type": "token", "content": content}

        if not tool_calls:
            yield {"type": "done", "content": ""}
            return

        messages.append(assistant_message)

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]
            tool_id = tool_call["id"]

            yield {
                "type": "tool_call",
                "id": tool_id,
                "name": tool_name,
                "arguments": tool_args
            }

            result = execute_tool(tool_name, tool_args)

            yield {
                "type": "tool_result",
                "id": tool_id,
                "name": tool_name,
                "result": result
            }

            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "name": tool_name,
                "content": result
            })

    yield {"type": "token", "content": "\n\n[达到最大工具调用轮数]"}
    yield {"type": "done", "content": ""}


async def call_qwen3_with_tools(
    messages: List[dict],
    tools: List[dict],
    temperature: float = 0.7,
    max_tokens: int = 4096
) -> dict:
    """调用 Qwen3 vLLM API (带工具)"""
    payload = {
        "model": QWEN3_MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{QWEN3_BASE_URL}/chat/completions",
            json=payload
        )
        response.raise_for_status()
        return response.json()


# ==================== 同步聊天端点 ====================

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """统一聊天接口 (同步)"""
    client = get_llm_client()

    messages = [
        ChatMessage(role=m.role, content=m.content)
        for m in request.messages
    ]

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
    """健康检查"""
    client = get_llm_client()
    manager = get_session_manager()

    status = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "models": {},
        "tools_enabled": True,
        "available_tools": get_tool_names(),
        "session_enabled": True
    }

    # 检查 Qwen3
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get(f"{QWEN3_BASE_URL}/models")
            if resp.status_code == 200:
                status["models"]["qwen3"] = "online"
            else:
                status["models"]["qwen3"] = "error"
    except:
        status["models"]["qwen3"] = "offline"

    # Gemini
    status["models"]["gemini"] = "online" if client.gemini_api_key else "no_api_key"

    return status


# ==================== 测试端点 ====================

@router.post("/test/react")
async def test_react(request: ChatRequest):
    """测试 ReAct (无需认证)"""
    events = []
    async for event in react_chat_stream_with_history(request, request.messages):
        events.append(event)
    return {"events": events}
