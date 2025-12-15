"""
Vulcan Brain API - 核心对话路由
P0 核心对话功能 - SSE 流式响应
"""
import json
import uuid
import time
from datetime import datetime
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.dependencies import (
    get_kernel,
    performance_metrics,
    thinking_logs,
    update_performance,
    add_thinking_log
)
from auth_api import get_current_user

router = APIRouter(tags=["Core Chat"])


# === Pydantic Models ===
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    stream: bool = True


# === SSE Stream Generator ===
async def generate_sse_stream(user_message: str, conv_id: str) -> AsyncGenerator[str, None]:
    """
    SSE 流式生成器 + 性能追踪
    
    将 Kernel 的事件流转换为前端需要的 SSE 格式，同时记录性能指标
    """
    kernel = get_kernel()
    
    # 性能追踪
    start_time = time.time()
    first_token_time = None
    token_count = 0
    
    try:
        # 消费 Kernel 的流式输出
        async for event in kernel.run_stream(user_message):
            evt_type = event.get('type')
            content = event.get('content', '')
            
            # 记录首个 token 时间（TTFT）
            if evt_type == 'token' and first_token_time is None:
                first_token_time = time.time()
                ttft = first_token_time - start_time
                performance_metrics['ttft'] = ttft
            
            # 计数 token
            if evt_type == 'token':
                token_count += len(content)
            
            # 构建前端需要的数据结构
            if evt_type == 'token':
                is_thinking = event.get('is_thinking', False)
                data = {
                    'type': 'token',
                    'content': content,
                    'is_thinking': is_thinking
                }
                
                # 记录思考日志
                if is_thinking and content.strip():
                    add_thinking_log({
                        'step': len(thinking_logs) + 1,
                        'description': content[:50],
                        'timestamp': datetime.now().isoformat()
                    })
                
                yield f'event: message\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
            
            elif evt_type == 'code':
                data = {'type': 'code', 'content': content}
                yield f'event: message\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'

            elif evt_type == 'tool_output':
                data = {'type': 'tool_output', 'content': content}
                yield f'event: message\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'

            elif evt_type == 'error':
                data = {'type': 'error', 'content': content}
                yield f'event: message\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
        
        # 计算性能指标
        end_time = time.time()
        total_time = end_time - start_time
        
        if token_count > 0 and total_time > 0:
            tokens_per_sec = token_count / total_time
            latency = total_time / token_count
            update_performance(tokens_per_sec, performance_metrics.get('ttft', 0), latency)
        
        # 最后发送 done 事件
        done_data = {'conversation_id': conv_id}
        yield f'event: done\ndata: {json.dumps(done_data)}\n\n'
        
    except Exception as e:
        error_data = {'type': 'error', 'content': f'Server error: {str(e)}'}
        yield f'event: message\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n'
        yield f'event: done\ndata: {{}}\n\n'


# === API Endpoints ===
@router.post('/api/chat/stream')
async def chat_stream(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """
    P0 - 核心对话功能
    
    SSE 流式对话接口
    """
    conv_id = request.conversation_id or f'conv_{uuid.uuid4().hex[:8]}'
    
    return StreamingResponse(
        generate_sse_stream(request.message, conv_id),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )
