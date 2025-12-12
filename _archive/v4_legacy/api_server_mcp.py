#!/usr/bin/env python3
"""
Vulcan Brain API Server - MCP V5 版本
使用 MCP Kernel 的代码执行架构
"""
import asyncio
import json
import time
from datetime import datetime
from typing import AsyncGenerator, Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 导入 MCP Kernel V5
from kernel_mcp_v5 import VulcanMCPKernel
from config import LLM_MODEL_NAME

# GPU 监控
try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False
    print('[WARNING] GPU monitoring not available')

# ==================== FastAPI 应用 ====================

app = FastAPI(
    title='Vulcan Brain API (MCP V5)',
    description='AI Agent Backend with MCP Code Execution Architecture',
    version='5.0.0'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# ==================== 全局状态 ====================

_kernel_instance: Optional[VulcanMCPKernel] = None
_performance_metrics = {
    'tokens_per_second': 0.0,
    'ttft': 0.0,
    'latency': 0.0,
}

def get_kernel() -> VulcanMCPKernel:
    """获取 MCP Kernel 单例"""
    global _kernel_instance
    if _kernel_instance is None:
        print('[INFO] 初始化 MCP Kernel V5...')
        _kernel_instance = VulcanMCPKernel(model=LLM_MODEL_NAME)
    return _kernel_instance

# ==================== Pydantic Models ====================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    kernel: str
    gpu_available: bool

# ==================== API 端点 ====================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        version="5.0.0",
        kernel="MCP V5",
        gpu_available=GPU_AVAILABLE
    )

@app.get("/api/performance")
async def get_performance():
    """获取性能指标"""
    gpu_info = None
    if GPU_AVAILABLE:
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_info = {
                "memory_used_gb": round(memory.used / 1024**3, 2),
                "memory_total_gb": round(memory.total / 1024**3, 2),
                "utilization_percent": utilization.gpu
            }
        except:
            pass
    
    return {
        "metrics": _performance_metrics,
        "gpu": gpu_info
    }

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话 - MCP Code Execution"""
    
    async def generate() -> AsyncGenerator[str, None]:
        kernel = get_kernel()
        start_time = time.time()
        first_token_time = None
        token_count = 0
        
        try:
            async for event in kernel.run_stream(request.message):
                event_type = event.get("type", "")
                
                if event_type == "token":
                    content = event.get("content", "")
                    if content:
                        if first_token_time is None:
                            first_token_time = time.time()
                        token_count += 1
                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                
                elif event_type == "code_detected":
                    yield f"data: {json.dumps({'type': 'code', 'content': '💻 执行代码中...'})}\n\n"
                
                elif event_type == "code_result":
                    output = event.get("output", "")
                    yield f"data: {json.dumps({'type': 'code_result', 'content': output})}\n\n"
                
                elif event_type == "error":
                    error = event.get("error", "Unknown error")
                    yield f"data: {json.dumps({'type': 'error', 'content': error})}\n\n"
            
            # 更新性能指标
            end_time = time.time()
            total_time = end_time - start_time
            if first_token_time:
                _performance_metrics['ttft'] = round(first_token_time - start_time, 3)
            _performance_metrics['latency'] = round(total_time, 3)
            if total_time > 0 and token_count > 0:
                _performance_metrics['tokens_per_second'] = round(token_count / total_time, 1)
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
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

@app.get("/api/tools")
async def list_tools():
    """列出可用工具"""
    kernel = get_kernel()
    structure = kernel.discovery.get_directory_structure()
    categories = kernel.discovery.list_categories()
    return {
        "structure": structure,
        "categories": categories,
        "count": len(categories)
    }

@app.get("/api/memories")
async def list_memories():
    """列出记忆"""
    try:
        from mcp_tools.core.memory import list_memories
        memories = list_memories()
        return {"memories": memories, "count": len(memories)}
    except Exception as e:
        return {"error": str(e), "memories": [], "count": 0}

# ==================== 启动 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
