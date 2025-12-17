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
import re
import httpx
import os

from auth_api import get_current_user
from vulcan_libs.llm_client import get_llm_client, ChatMessage, ModelType, StreamChunk
from core.tools import execute_tool, get_tool_names, get_tool_schemas, ToolExecutor
from core.tools.base import ToolContext
from services.session_manager import get_session_manager
from services.context_manager import compact_session, should_compact, build_context, MAX_HISTORY_TURNS
from services.memory_service import get_memory_service
from services.memory_extractor import get_memory_extractor

# ==================== 编排层 ====================
# Phase 1: IntentRouter 集成 - 解决 Sticky Tool 问题

ENABLE_ORCHESTRATION = True  # Feature flag, 关闭则回退旧逻辑

_intent_router = None

def get_intent_router():
    """获取 IntentRouter 单例"""
    global _intent_router
    if _intent_router is None:
        try:
            from core.orchestration import IntentRouter
            _intent_router = IntentRouter()
        except ImportError as e:
            import logging
            logging.getLogger(__name__).warning(f"IntentRouter not available: {e}")
            return None
    return _intent_router


def filter_tools_by_intent(intent_name: str, all_tool_schemas: list) -> list:
    """
    根据意图过滤工具 - 物理隔离防止 Sticky Tool

    关键: intent=chat 时返回空列表，模型无法调用任何工具
    """
    from core.orchestration import Intent, get_tools_for_intent

    try:
        intent = Intent(intent_name)
    except ValueError:
        # 未知意图，返回所有工具
        return all_tool_schemas

    allowed_tool_names = get_tools_for_intent(intent)

    if not allowed_tool_names:
        # 空列表 = 物理隔离
        return []

    # 过滤: 只保留 allowed 的工具
    return [t for t in all_tool_schemas if t.get("function", {}).get("name") in allowed_tool_names]


# ==================== 异步记忆提取 ====================

async def extract_memories_async(user_id: str, session_id: str, message: str):
    """异步提取记忆 (不阻塞主响应)"""
    try:
        from services.memory_service import get_memory_service
        from services.memory_extractor import get_memory_extractor
        
        extractor = get_memory_extractor()
        svc = get_memory_service()
        
        # LLM 提取
        extractions = await extractor.extract(message)
        
        if not extractions:
            return
        
        # 存入待确认
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
        
        import logging
        logging.getLogger(__name__).info(f"Extracted {len(extractions)} memories for user {user_id}")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Memory extraction failed: {e}")

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
        "definitions": get_tool_schemas()
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

            # 2.5 注入记忆上下文和工具使用指令
            try:
                memory_service = get_memory_service()
                memory_context = await memory_service.build_context(user_id)
                
                # 构建 system 消息 (包含记忆工具使用指南)
                memory_instruction = """你是 Vulcan Brain AI 助手，专注于高效完成用户任务。"""
                
                if memory_context:
                    system_msg = memory_instruction + f"\n\n[用户记忆]\n{memory_context}\n[/用户记忆]"
                else:
                    system_msg = memory_instruction
                
                # 检查是否已有 system 消息
                if history and history[0].get("role") == "system":
                    history[0]["content"] = system_msg + "\n\n" + history[0]["content"]
                else:
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

            if request.enable_tools:  # 启用工具时使用 ReAct 循环
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

            # 6. 异步提取记忆 (从用户消息中提取)
            if current_user_msg:
                import asyncio
                asyncio.create_task(extract_memories_async(user_id, session_id, current_user_msg))

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



# ==================== Thinking 内容分离 (ReAct 专用) ====================

def parse_thinking_content(raw_content: str):
    """
    解析原始内容，分离 thinking 和 final content
    
    支持两种格式:
    1. <think>思考内容</think>最终回复
    2. 思考内容</think>最终回复 (无开始标签，vLLM 常见行为)
    
    Returns: (thinking_text, content_text)
    """
    if not raw_content:
        return None, raw_content
    
    # 检查是否有 </think> 标签
    if "</think>" in raw_content:
        # 情况1: 有完整的 <think>...</think>
        if "<think>" in raw_content:
            match = re.search(r"<think>(.*?)</think>", raw_content, re.DOTALL)
            if match:
                thinking = match.group(1).strip()
                final_content = raw_content.split("</think>", 1)[-1].strip()
                return thinking, final_content
        else:
            # 情况2: 只有 </think> 结束标签 (vLLM 常见行为)
            parts = raw_content.split("</think>", 1)
            thinking = parts[0].strip()
            final_content = parts[1].strip() if len(parts) > 1 else ""
            return thinking, final_content
    
    return None, raw_content

    
    # 检查是否有 <think> 标签
    if "<think>" in raw_content and "</think>" in raw_content:
        match = re.search(r"<think>(.*?)</think>", raw_content, re.DOTALL)
        if match:
            thinking = match.group(1).strip()
            final_content = raw_content.split("</think>", 1)[-1].strip()
            return thinking, final_content
    
    return None, raw_content


# ==================== ReAct 聊天 (带工具) ====================

async def react_chat_stream_with_history(
    request: ChatRequest,
    history: List[dict]
) -> AsyncGenerator[dict, None]:
    """ReAct 流式聊天，使用历史上下文"""
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    # ====== Phase 1: 意图路由 (解决 Sticky Tool) ======
    current_tools = get_tool_schemas()  # 默认全部工具

    if ENABLE_ORCHESTRATION:
        router_instance = get_intent_router()
        if router_instance:
            # 获取最新用户消息
            user_message = ""
            for m in reversed(history):
                if m.get("role") == "user":
                    user_message = m.get("content", "")
                    break

            if user_message:
                try:
                    decision = await router_instance.route(user_message)

                    # 发送路由事件 (前端可展示)
                    yield {
                        "type": "routing",
                        "intent": decision.intent.value,
                        "model_tier": decision.model_tier.value,
                        "reasoning": decision.reasoning,
                        "use_tools": decision.use_tools
                    }

                    # 始终基于意图过滤工具 (CHAT 意图保留 remember/recall)
                    current_tools = filter_tools_by_intent(decision.intent.value, get_tool_schemas())

                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Routing failed, using all tools: {e}")

    # ====== 原有逻辑 ======
    iteration = 0

    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1

        response = await call_qwen3_with_tools(
            messages=messages,
            tools=current_tools,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        assistant_message = response["choices"][0]["message"]
        tool_calls = assistant_message.get("tool_calls", [])
        content = assistant_message.get("content", "")

        # 工具调用模式下的思考分离逻辑:
        # - 有 tool_calls: content 全部是思考过程
        # - 无 tool_calls: 需要解析 </think> 标签
        if tool_calls:
            # 有工具调用，content 是思考过程
            if content:
                yield {"type": "thinking", "content": content}
        else:
            # 无工具调用，这是最终回复，解析 </think>
            if content:
                thinking_text, final_content = parse_thinking_content(content)
                if thinking_text:
                    yield {"type": "thinking", "content": thinking_text}
                if final_content:
                    yield {"type": "token", "content": final_content}
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

            tool_context = ToolContext(user_id="system", permissions=["execute_destructive"])
            result_obj = await ToolExecutor.execute_async(tool_name, tool_args, tool_context)
            result = result_obj.to_llm_string()

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
    max_tokens: int = 4096,
    enable_thinking: bool = False  # 工具调用默认禁用思考
) -> dict:
    """调用 Qwen3 vLLM API (带工具)"""
    # 处理 messages - 禁用思考时加 /no_think
    processed_messages = []
    for i, msg in enumerate(messages):
        if not enable_thinking and i == 0 and msg.get("role") == "system":
            # 在 system prompt 末尾加 /no_think
            processed_messages.append({
                "role": "system",
                "content": msg.get("content", "") + " /no_think"
            })
        else:
            processed_messages.append(msg)
    
    # 如果没有 system message 且需要禁用思考，插入一条
    if not enable_thinking and (not processed_messages or processed_messages[0].get("role") != "system"):
        processed_messages.insert(0, {"role": "system", "content": "你是一个高效的AI助手，直接执行任务。/no_think"})
    
    payload = {
        "model": QWEN3_MODEL,
        "messages": processed_messages,
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
