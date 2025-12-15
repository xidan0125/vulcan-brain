# bicameral_api.py
"""
Vulcan Brain - Bicameral Mind API 路由
V5.1 双脑系统 REST API
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth_api import get_current_user
from vulcan_libs.bicameral_graph import BicameralRunner, get_bicameral_runner
from vulcan_libs.bicameral_stream import BicameralStreamHandler, get_bicameral_stream_handler


# ==================== 路由器 ====================

router = APIRouter(prefix="/bicameral", tags=["Bicameral"])


# ==================== 请求模型 ====================

class BicameralChatRequest(BaseModel):
    """Bicameral 聊天请求"""
    message: str
    thread_id: Optional[str] = None
    max_steps: int = 10
    agent_type: Optional[str] = None  # 前端入口类型，可用于个性化提示词


class BicameralResponse(BaseModel):
    """Bicameral 响应"""
    success: bool
    answer: str
    thread_id: str
    timestamp: str


# ==================== API 端点 ====================

@router.post("/chat", response_model=BicameralResponse)
async def bicameral_chat(
    request: BicameralChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Bicameral Mind 同步聊天

    CEO 分析用户意图，必要时委派 CTO 执行代码
    支持 PostgreSQL 状态持久化
    """
    # 生成或使用提供的 thread_id
    thread_id = request.thread_id or f"user_{current_user.get('user_id', 'anon')}_{uuid.uuid4().hex[:8]}"

    try:
        runner = get_bicameral_runner()
        answer = await runner.run(
            user_message=request.message,
            thread_id=thread_id,
            agent_type=request.agent_type  # 传递 Agent 类型
        )

        return BicameralResponse(
            success=True,
            answer=answer,
            thread_id=thread_id,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def bicameral_chat_stream(
    request: BicameralChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Bicameral Mind 流式聊天 (SSE)

    实时流式输出:
    - node_start: 节点开始 (CEO/CTO/Synthesizer)
    - node_end: 节点结束
    - thinking: 思考过程
    - token: 输出文本
    - code: 代码块
    - done: 完成

    使用示例 (JavaScript):
    ```
    const eventSource = new EventSource('/api/bicameral/chat/stream?message=...');
    eventSource.addEventListener('token', (e) => {
        const data = JSON.parse(e.data);
        console.log(data.content);
    });
    ```
    """
    # 生成或使用提供的 thread_id
    thread_id = request.thread_id or f"user_{current_user.get('user_id', 'anon')}_{uuid.uuid4().hex[:8]}"

    handler = get_bicameral_stream_handler()

    return StreamingResponse(
        handler.stream_sse(
            user_message=request.message,
            thread_id=thread_id,
            max_steps=request.max_steps,
            agent_type=request.agent_type  # 传递 Agent 类型
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
        }
    )


@router.get("/health")
async def bicameral_health():
    """健康检查"""
    return {
        "status": "healthy",
        "version": "5.1",
        "features": [
            "CEO-CTO 双脑架构",
            "PostgreSQL 状态持久化",
            "SSE 流式输出",
            "代码自我修复"
        ]
    }


@router.get("/threads/{thread_id}")
async def get_thread_history(
    thread_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取对话历史

    从 PostgreSQL 检查点加载历史状态
    """
    # TODO: 实现从 checkpointer 加载历史
    return {
        "thread_id": thread_id,
        "messages": [],
        "note": "历史加载功能待实现"
    }


# ==================== 简易测试端点 ====================

@router.get("/test")
async def bicameral_test():
    """测试端点 - 不需要认证"""
    runner = get_bicameral_runner()

    # 简单测试
    result = await runner.run("1+1等于多少？", thread_id="test_quick")

    return {
        "test": "quick_math",
        "result": result,
        "status": "success"
    }
