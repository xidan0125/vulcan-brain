#!/usr/bin/env python3
"""
Vulcan Brain API Server - FastAPI Backend
对接新前端的 RESTful API 服务器 (P0 + P1)
"""
import asyncio
import json
import uuid
import time
from datetime import datetime
from typing import AsyncGenerator, Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException
from agent_session_store import get_agent_session, save_agent_session, delete_agent_session, list_user_sessions
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time as time_module
from vulcan_libs.logger import api_logger, log_request, log_error

from vulcan_libs.store import store
from auth_api import get_current_user
# 导入 Vulcan 核心组件
from config import LLM_MODEL_NAME
from kernel_codeact import VulcanCodeActKernel
from vulcan_libs.registry import ToolRegistry, ToolPackage
from vulcan_libs.tool_retriever import ToolRetriever
from tools.function_tools import get_time_tool
from tools.memory_tools import remember_tool, recall_tool, forget_tool
from tools.rag_tools import add_document_tool, search_knowledge_tool
from tools.alignment_tools import record_boss_feedback_tool, get_alignment_summary_tool
from tools.boss_insight_tool import save_boss_insight_tool
from tools.search_tools import web_search_tool
# AContext 会话记忆管理
from acontext_integration import get_acontext_manager

# Code Execution Sandbox (Programmatic Tool Calling)
from tools.code_executor import create_code_execution_tool, VulcanCodeSandbox

# GPU 监控（尝试导入，失败则用模拟数据）
try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False
    print('[WARNING] GPU monitoring not available, using mock data')

# ==================== FastAPI 应用初始化 ====================

app = FastAPI(
    title='Vulcan Brain API',
    description='AI Agent Backend with LOD Architecture',
    version='1.0.0'
)

# CORS 配置
# CORS 配置 - 生产环境限制来源
ALLOWED_ORIGINS = [
    "https://vsg-brain.com",
    "https://api.vsg-brain.com",
    "http://localhost:3000",  # 开发环境
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allow_headers=['*'],
)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time_module.time()
    response = await call_next(request)
    duration = (time_module.time() - start_time) * 1000
    
    # 获取用户信息（如果有）
    user = "anonymous"
    auth_header = request.headers.get("authorization", "")
    if auth_header:
        user = "authenticated"
    
    log_request(
        method=request.method,
        path=str(request.url.path),
        user=user,
        status=response.status_code,
        duration_ms=duration
    )
    return response

# Presentation 静态文件服务
app.mount("/presentation", StaticFiles(directory="presentation", html=True), name="presentation")

# ==================== 全局状态管理 ====================

_kernel_instance: Optional[VulcanCodeActKernel] = None
_performance_metrics = {
    'tokens_per_second': 0.0,
    'ttft': 0.0,
    'latency': 0.0,
    'last_query_time': None
}
_thinking_logs: List[Dict[str, Any]] = []

def get_kernel() -> VulcanCodeActKernel:
    """获取或初始化 Kernel 实例（单例模式）"""
    global _kernel_instance
    
    if _kernel_instance is None:
        print('[INFO] 初始化 Vulcan Kernel...')
        
        # 1. 创建工具注册表
        registry = ToolRegistry()
        
        # 核心包（常驻内存）
        registry.register(ToolPackage(
            name='core_tools',
            description='核心基础工具：时间查询、联网搜索、记忆管理',
            tools=[get_time_tool, web_search_tool, remember_tool, recall_tool, forget_tool],
            is_core=True,
            category='foundation'
        ))
        
        # RAG 扩展包
        registry.register(ToolPackage(
            name='rag_pkg',
            description='知识库检索能力：文档添加、语义搜索',
            tools=[add_document_tool, search_knowledge_tool],
            is_core=False,
            category='knowledge'
        ))
        
        # 对齐扩展包
        registry.register(ToolPackage(
            name='alignment_pkg',
            description='价值观对齐工具：记录 Boss 反馈、保存洞察',
            tools=[record_boss_feedback_tool, get_alignment_summary_tool, save_boss_insight_tool],
            is_core=False,
            category='alignment'
        ))

        # 代码执行扩展包 (Programmatic Tool Calling - 参考 Anthropic 架构)
        registry.register(ToolPackage(
            name='code_execution_pkg',
            description='代码执行沙箱：执行 Python 代码进行数据处理、计算、筛选和批量操作',
            tools=[create_code_execution_tool()],
            is_core=False,
            category='computation'
        ))

        # 2. 创建检索器
        retriever = ToolRetriever(registry, top_k=3)
        
        # 3. 创建内核
        _kernel_instance = VulcanCodeActKernel(
            model=LLM_MODEL_NAME,
            registry=registry,
            retriever=retriever,
            enable_lod=True
        )
        
        print('[INFO] Vulcan Kernel 初始化完成')
    
    return _kernel_instance

def get_gpu_stats() -> Dict[str, Any]:
    """获取 GPU 统计信息"""
    if not GPU_AVAILABLE:
        # 模拟数据（当GPU监控不可用时）
        return {
            'utilization': 85,
            'temperature': 68,
            'power_draw': 380
        }
    
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # GPU 0
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        power = pynvml.nvmlDeviceGetPowerUsage(handle) // 1000  # mW -> W
        
        return {
            'utilization': util.gpu,
            'temperature': temp,
            'power_draw': power
        }
    except Exception as e:
        print(f'[ERROR] GPU stats failed: {e}')
        return {'utilization': 0, 'temperature': 0, 'power_draw': 0}

def get_vram_stats() -> Dict[str, Any]:
    """获取 VRAM 统计信息"""
    if not GPU_AVAILABLE:
        # 模拟数据
        return {
            'used': 18432,
            'total': 24576,
            'percentage': 75
        }
    
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        
        return {
            'used': mem_info.used // (1024**2),  # bytes -> MB
            'total': mem_info.total // (1024**2),
            'percentage': int((mem_info.used / mem_info.total) * 100)
        }
    except Exception as e:
        print(f'[ERROR] VRAM stats failed: {e}')
        return {'used': 0, 'total': 0, 'percentage': 0}

# ==================== P0 - 核心对话功能 ====================

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    stream: bool = True

async def generate_sse_stream(user_message: str, conv_id: str) -> AsyncGenerator[str, None]:
    """
    SSE 流式生成器 + 性能追踪
    
    将 Kernel 的事件流转换为前端需要的 SSE 格式，同时记录性能指标
    """
    global _performance_metrics, _thinking_logs
    
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
                _performance_metrics['ttft'] = first_token_time - start_time
            
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
                    _thinking_logs.append({
                        'step': len(_thinking_logs) + 1,
                        'description': content[:50],  # 前50字符
                        'timestamp': datetime.now().isoformat()
                    })
                    # 只保留最近10条
                    if len(_thinking_logs) > 10:
                        _thinking_logs.pop(0)
                
                # SSE 格式输出
                yield f'event: message\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
            
            elif evt_type == 'code':
                data = {
                    'type': 'code',
                    'content': content
                }
                yield f'event: message\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'

            elif evt_type == 'tool_output':
                data = {
                    'type': 'tool_output',
                    'content': content
                }
                yield f'event: message\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'

            elif evt_type == 'error':
                data = {
                    'type': 'error',
                    'content': content
                }
                yield f'event: message\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
        
        # 计算性能指标
        end_time = time.time()
        total_time = end_time - start_time
        
        if token_count > 0 and total_time > 0:
            _performance_metrics['tokens_per_second'] = token_count / total_time
            _performance_metrics['latency'] = total_time / token_count
        
        _performance_metrics['last_query_time'] = datetime.now().isoformat()
        
        # 最后发送 done 事件
        done_data = {
            'conversation_id': conv_id
        }
        yield f'event: done\ndata: {json.dumps(done_data)}\n\n'
        
    except Exception as e:
        # 错误处理
        error_data = {
            'type': 'error',
            'content': f'Server error: {str(e)}'
        }
        yield f'event: message\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n'
        yield f'event: done\ndata: {{}}\n\n'

@app.post('/api/chat/stream')
async def chat_stream(request: ChatRequest):
    """
    P0 - 核心对话功能
    
    SSE 流式对话接口
    """
    # 生成或使用现有 conversation_id
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

# ==================== P1 - 实时系统状态 ====================

@app.get('/api/system/status')
async def system_status():
    """
    P1 - Inspector 面板数据
    
    返回实时系统状态（GPU、VRAM、性能指标、思考日志）
    建议前端每 1-2 秒轮询一次
    """
    return {
        'gpu': get_gpu_stats(),
        'vram': get_vram_stats(),
        'performance': {
            'tokens_per_second': round(_performance_metrics['tokens_per_second'], 2),
            'ttft': round(_performance_metrics['ttft'], 3),
            'latency': round(_performance_metrics['latency'], 4),
            'last_query': _performance_metrics['last_query_time']
        },
        'thinking_process': _thinking_logs[-5:],  # 最近5条
        'timestamp': datetime.now().isoformat()
    }

# ==================== 健康检查 ====================

@app.get('/api/health')
async def health_check():
    """健康检查接口"""
    return {
        'status': 'healthy',
        'service': 'Vulcan Brain API',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'gpu_monitoring': GPU_AVAILABLE
    }


# ==================== Code Execution API (Programmatic Tool Calling) ====================

class CodeExecutionRequest(BaseModel):
    """代码执行请求"""
    code: str
    timeout: int = 30

class CodeExecutionResponse(BaseModel):
    """代码执行响应"""
    success: bool
    output: str
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float

# 全局 sandbox 实例
_sandbox_instance: Optional[VulcanCodeSandbox] = None

def get_sandbox() -> VulcanCodeSandbox:
    """获取 Sandbox 单例"""
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = VulcanCodeSandbox(timeout_seconds=30)
    return _sandbox_instance

@app.post('/api/execute', response_model=CodeExecutionResponse)
async def execute_code(request: CodeExecutionRequest):
    """
    Code Execution Sandbox API

    执行 Python 代码并返回结果。用于：
    - AI 生成代码后需要执行
    - 数据处理和批量计算
    - 避免大量数据进入 LLM Context Window

    安全限制：
    - 禁止 os.system, subprocess
    - 禁止文件写入
    - 默认 30 秒超时

    示例请求:
    {
        "code": "result = [x**2 for x in range(10)]",
        "timeout": 30
    }
    """
    try:
        sandbox = get_sandbox()

        # 如果请求指定了不同的超时时间，创建新的 sandbox
        if request.timeout != 30:
            sandbox = VulcanCodeSandbox(timeout_seconds=request.timeout)

        result = await sandbox.execute_async(request.code)

        return CodeExecutionResponse(
            success=result.success,
            output=result.output,
            result=result.result,
            error=result.error,
            execution_time_ms=result.execution_time_ms
        )
    except Exception as e:
        return CodeExecutionResponse(
            success=False,
            output="",
            result=None,
            error=str(e),
            execution_time_ms=0
        )


# ==================== 启动入口 ====================

# ==================== P2 - 记忆系统 API (AContext SDK 集成) ====================

@app.get("/api/memory/profile")
async def get_memory_profile(current_user: dict = Depends(get_current_user)):
    """
    P2 - 获取用户画像 (VulcanStore + 用户绑定)
    """
    user_id = current_user["user_id"]
    try:
        # 1. 使用 VulcanStore 获取用户记忆
        memories = await store.get_memories(user_id, limit=50)
        memories_list = [
            {
                "id": str(mem.get("_id", "")),
                "content": mem.get("content", ""),
                "category": mem.get("category", "general"),
                "created_at": mem.get("created_at", "").isoformat() if mem.get("created_at") else ""
            }
            for mem in memories
        ]
        
        # 2. 获取对话统计
        chat_stats = None
        try:
            sessions = await store.list_sessions(user_id, limit=100)
            chat_stats = {
                "total_sessions": len(sessions),
                "recent_sessions": [
                    {"id": str(s.get("_id", "")), "title": s.get("title", "")}
                    for s in sessions[:5]
                ]
            }
        except Exception as e:
            print(f"[WARNING] Chat stats unavailable: {e}")
        
        return {
            "user_id": user_id,
            "memories": memories_list,
            "memory_count": len(memories_list),
            "chat_stats": chat_stats,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memory/timeline")
async def get_memory_timeline(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """
    P2 - 获取对话历史时间线 (AContext Sessions) - 用户绑定版
    """
    user_id = current_user["user_id"]
    try:
        from acontext_sdk_helper import list_sessions
        sessions = list_sessions(limit=limit)
        
        conversations = []
        for session in sessions:
            conversations.append({
                "id": session.id,
                "timestamp": session.created_at,
                "preview": f"Session {session.id[:8]}...",
                "space_id": session.space_id,
                "updated_at": session.updated_at
            })
        
        return {
            "conversations": conversations,
            "total_count": len(conversations)
        }
    except Exception as e:
        print(f"[WARNING] AContext timeline unavailable: {e}")
        return {
            "conversations": [],
            "total_count": 0,
            "error": str(e)
        }


# ==================== P3 - Knowledge Base API ====================

import os
import json
import hashlib
from datetime import datetime
from fastapi import UploadFile, File, HTTPException
from typing import List
from llama_index.core import Document

# Knowledge Base 存储配置
KB_STORAGE_DIR = './kb_storage'
KB_METADATA_FILE = os.path.join(KB_STORAGE_DIR, 'metadata.json')
KB_RAG_DIR = os.path.join(KB_STORAGE_DIR, 'rag_index')

# 确保目录存在
os.makedirs(KB_STORAGE_DIR, exist_ok=True)

# 加载/初始化 metadata
if os.path.exists(KB_METADATA_FILE):
    with open(KB_METADATA_FILE, 'r', encoding='utf-8') as f:
        _kb_metadata = json.load(f)
else:
    _kb_metadata = {}

def _save_metadata():
    """保存 metadata 到磁盘"""
    with open(KB_METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(_kb_metadata, f, ensure_ascii=False, indent=2)

def _rebuild_rag_index():
    """重建 RAG 索引"""
    from vulcan_libs.rag import VulcanRAG

    # 收集所有文档
    documents = []
    for doc_id, doc_info in _kb_metadata.items():
        file_path = doc_info['file_path']
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                documents.append(Document(
                    text=content,
                    doc_id=doc_id,
                    metadata={
                        'filename': doc_info['filename'],
                        'upload_time': doc_info['upload_time']
                    }
                ))

    # 重建索引
    if documents:
        rag = VulcanRAG(persist_dir=KB_RAG_DIR)
        rag.build_knowledge_base(documents)
        return len(documents)
    return 0



# ==================== Memory CRUD APIs ====================

@app.post("/api/memory")
async def add_memory(
    content: str,
    category: str = "general",
    current_user: dict = Depends(get_current_user)
):
    """添加新记忆"""
    user_id = current_user["user_id"]
    memory_id = await store.add_memory(user_id, content, category)
    return {"success": True, "memory_id": memory_id}

@app.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: str, current_user: dict = Depends(get_current_user)):
    """删除记忆"""
    user_id = current_user["user_id"]
    success = await store.delete_memory(memory_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"success": True}

@app.get("/api/memory/search")
async def search_memory(
    q: str,
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """搜索记忆"""
    user_id = current_user["user_id"]
    results = await store.search_memories(user_id, q, limit)
    return {"results": results, "count": len(results)}

@app.post('/api/knowledge/upload')
async def upload_document(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """
    P3 - 上传文档到知识库

    支持的文件类型: .txt, .md, .py, .json
    """
    # 验证文件类型
    allowed_extensions = ['.txt', '.md', '.py', '.json', '.yaml', '.yml']
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f'不支持的文件类型: {file_ext}。支持的类型: {allowed_extensions}'
        )

    # 读取文件内容
    content = await file.read()
    text_content = content.decode('utf-8')

    # 生成文档 ID（基于内容哈希）
    doc_id = hashlib.md5(text_content.encode()).hexdigest()[:16]

    # 保存文件
    file_path = os.path.join(KB_STORAGE_DIR, f'{doc_id}_{file.filename}')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text_content)

    # 更新 metadata (添加用户绑定)
    _kb_metadata[doc_id] = {
        'id': doc_id,
        'filename': file.filename,
        'file_path': file_path,
        'file_size': len(content),
        'upload_time': datetime.now().isoformat(),
        'file_type': file_ext,
        'user_id': current_user["user_id"]  # 用户绑定
    }
    _save_metadata()

    # 重建 RAG 索引
    doc_count = _rebuild_rag_index()

    return {
        'success': True,
        'document_id': doc_id,
        'filename': file.filename,
        'file_size': len(content),
        'total_documents': doc_count,
        'message': '文档上传成功并已加入知识库'
    }

@app.get('/api/knowledge/list')
async def list_documents():
    """
    P3 - 列出所有知识库文档
    """
    documents = []
    for doc_id, doc_info in _kb_metadata.items():
        documents.append({
            'id': doc_info['id'],
            'filename': doc_info['filename'],
            'file_size': doc_info['file_size'],
            'upload_time': doc_info['upload_time'],
            'file_type': doc_info['file_type']
        })

    # 按上传时间倒序排序
    documents.sort(key=lambda x: x['upload_time'], reverse=True)

    return {
        'documents': documents,
        'total_count': len(documents)
    }

@app.delete('/api/knowledge/{document_id}')
async def delete_document(document_id: str):
    """
    P3 - 删除指定文档
    """
    if document_id not in _kb_metadata:
        raise HTTPException(status_code=404, detail='文档不存在')

    doc_info = _kb_metadata[document_id]

    # 删除文件
    if os.path.exists(doc_info['file_path']):
        os.remove(doc_info['file_path'])

    # 从 metadata 删除
    del _kb_metadata[document_id]
    _save_metadata()

    # 重建 RAG 索引
    doc_count = _rebuild_rag_index()

    return {
        'success': True,
        'deleted_document_id': document_id,
        'deleted_filename': doc_info['filename'],
        'remaining_documents': doc_count,
        'message': '文档已删除并更新知识库索引'
    }



# ==================== P4 - Soul Config API ====================

import os
import json

# Soul Config 存储配置
SOUL_CONFIG_FILE = './soul_config.json'

# 默认灵魂配置
_default_soul_config = {
    'system_prompt': """你是 Vulcan Brain，一个高性能 AI Agent。

核心价值观:
- 专业性：提供准确、可靠的信息和分析
- 效率：快速响应，直击问题核心
- 透明度：清晰展示思考过程和不确定性
- 主动性：预判需求，提供前瞻性建议

工作方式:
1. 使用 <think> 标签展示内部推理过程
2. 调用工具时说明理由和预期效果
3. 提供多角度分析，必要时给出备选方案
4. 对不确定的内容明确标注""",
    'creativity': 70,
    'reasoning_depth': 80,
    'tool_use_preference': 60,
    'memory_retention': 75,
    'updated_at': None
}

# 加载/初始化配置
if os.path.exists(SOUL_CONFIG_FILE):
    with open(SOUL_CONFIG_FILE, 'r', encoding='utf-8') as f:
        _soul_config = json.load(f)
else:
    _soul_config = _default_soul_config.copy()

def _save_soul_config():
    """保存 Soul Config 到磁盘"""
    with open(SOUL_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(_soul_config, f, ensure_ascii=False, indent=2)

@app.get('/api/soul/config')
async def get_soul_config():
    """
    P4 - 获取当前灵魂配置
    """
    return {
        'config': _soul_config,
        'is_default': _soul_config.get('updated_at') is None
    }

@app.post('/api/soul/update')
async def update_soul_config(
    system_prompt: str = None,
    creativity: int = None,
    reasoning_depth: int = None,
    tool_use_preference: int = None,
    memory_retention: int = None
):
    """
    P4 - 更新灵魂配置
    """
    from datetime import datetime

    # 更新非空字段
    if system_prompt is not None:
        _soul_config['system_prompt'] = system_prompt
    if creativity is not None:
        _soul_config['creativity'] = max(0, min(100, creativity))
    if reasoning_depth is not None:
        _soul_config['reasoning_depth'] = max(0, min(100, reasoning_depth))
    if tool_use_preference is not None:
        _soul_config['tool_use_preference'] = max(0, min(100, tool_use_preference))
    if memory_retention is not None:
        _soul_config['memory_retention'] = max(0, min(100, memory_retention))

    _soul_config['updated_at'] = datetime.now().isoformat()
    _save_soul_config()

    return {
        'success': True,
        'config': _soul_config,
        'message': '灵魂配置已更新'
    }

@app.post('/api/soul/reset')
async def reset_soul_config():
    """
    P4 - 重置灵魂配置为默认值
    """
    global _soul_config
    _soul_config = _default_soul_config.copy()
    _soul_config['updated_at'] = None
    _save_soul_config()

    return {
        'success': True,
        'config': _soul_config,
        'message': '灵魂配置已重置为默认值'
    }




# ==================== Agent Chat API ====================
from agent_prompts import AGENT_PROMPTS, AGENT_METADATA, get_agent_prompt, list_agents

_agent_sessions: Dict[str, List[Dict[str, str]]] = {}

class AgentChatRequest(BaseModel):
    """Agent聊天请求"""
    message: str
    session_id: Optional[str] = None

class AgentChatResponse(BaseModel):
    """Agent聊天响应"""
    reply: str
    agent: str
    agent_name: str
    session_id: str

@app.get('/api/agents/list')
async def api_list_agents():
    """列出所有可用的Agent"""
    return {'agents': list_agents(), 'count': len(AGENT_METADATA)}

@app.get('/api/agents/{agent_type}/info')
async def api_get_agent_info(agent_type: str):
    """获取指定Agent的信息"""
    if agent_type not in AGENT_METADATA:
        raise HTTPException(status_code=404, detail=f'Agent {agent_type} not found')
    return {'id': agent_type, **AGENT_METADATA[agent_type], 'has_prompt': agent_type in AGENT_PROMPTS}

@app.post('/api/agents/{agent_type}/chat')
async def api_agent_chat(agent_type: str, request: AgentChatRequest, current_user: dict = Depends(get_current_user)):
    """与指定Agent进行对话 (用户绑定版)"""
    if agent_type not in AGENT_PROMPTS:
        raise HTTPException(status_code=404, detail=f'Agent {agent_type} not found')

    user_id = current_user["user_id"]
    session_id = request.session_id or str(uuid.uuid4())

    # 从MongoDB获取用户专属会话历史
    history = await get_agent_session(user_id, session_id)
    history.append({'role': 'user', 'content': request.message})

    if len(history) > 20:
        history = history[-20:]
        _agent_sessions[session_id] = history

    try:
        system_prompt = get_agent_prompt(agent_type)
        agent_name = AGENT_METADATA[agent_type]['name']

        from openai import OpenAI
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="not-needed")

        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append(msg)

        completion = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=2048
        )
        response_text = completion.choices[0].message.content

        history.append({'role': 'assistant', 'content': response_text})
        await save_agent_session(user_id, session_id, history, agent_type)

        return AgentChatResponse(
            reply=response_text,
            agent=agent_type,
            agent_name=agent_name,
            session_id=session_id
        )

    except Exception as e:
        print(f'[ERROR] Agent chat error: {e}')
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/agents/{agent_type}/chat/stream')
async def api_agent_chat_stream(agent_type: str, request: AgentChatRequest, current_user: dict = Depends(get_current_user)):
    """流式对话 - 返回 SSE 流"""
    if agent_type not in AGENT_PROMPTS:
        raise HTTPException(status_code=404, detail=f'Agent {agent_type} not found')

    system_prompt = get_agent_prompt(agent_type)
    session_id = request.session_id or str(uuid.uuid4())

    async def generate():
        try:
            from openai import OpenAI
            client = OpenAI(base_url="http://localhost:11434/v1", api_key="not-needed")

            history = await get_agent_session(current_user['user_id'], session_id)
            history.append({'role': 'user', 'content': request.message})

            messages = [{"role": "system", "content": system_prompt}]
            for msg in history[-20:]:
                messages.append(msg)

            stream = client.chat.completions.create(
                model=LLM_MODEL_NAME,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                stream=True
            )

            full_response = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"

            history.append({'role': 'assistant', 'content': full_response})
            await save_agent_session(current_user['user_id'], session_id, history, agent_type)

            yield f"data: {json.dumps({'content': '', 'done': True, 'session_id': session_id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.delete('/api/agents/sessions/{session_id}')
async def api_clear_agent_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """清除指定会话的历史 (用户绑定版)"""
    user_id = current_user["user_id"]
    if await delete_agent_session(user_id, session_id):
        return {'success': True, 'message': f'Session {session_id} cleared'}
    return {'success': False, 'message': 'Session not found or not owned by user'}


@app.get('/api/agents/sessions')
async def api_list_agent_sessions(agent_type: str = None, current_user: dict = Depends(get_current_user)):
    """列出用户的Agent会话"""
    user_id = current_user["user_id"]
    sessions = await list_user_sessions(user_id, agent_type)
    return {"sessions": sessions, "count": len(sessions)}


if __name__ == '__main__':
    import uvicorn
    
    print('='*60)
    print('🚀 Vulcan Brain API Server Starting...')
    print('='*60)
    print(f'📡 Endpoint: http://0.0.0.0:8001')
    print(f'📚 Docs: http://0.0.0.0:8001/docs')
    print(f'🔧 Model: {LLM_MODEL_NAME}')
    print(f'🎮 GPU Monitor: {"Enabled" if GPU_AVAILABLE else "Disabled (Mock Data)"}')
    print('='*60)
    
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=8001,
        log_level='info'
    )


# ==================== 用户认证系统 ====================
# 导入认证路由
from auth_api import router as auth_router
app.include_router(auth_router, prefix="/api")

# ==================== 对话历史系统 ====================
from chat_api import router as chat_router
app.include_router(chat_router, prefix="/api")

# ==================== Acontext 上下文记忆系统 ====================
from acontext_integration import router as acontext_router
app.include_router(acontext_router, prefix="/api")


# ==================== LOD Agent Endpoint (新增) ====================

@app.post("/api/agents/{agent_type}/chat/lod")
async def api_agent_chat_lod(agent_type: str, request: AgentChatRequest, current_user: dict = Depends(get_current_user)):
    """
    使用 LOD Kernel 的 Agent 对话端点
    特点：动态工具加载、CodeAct 执行、三层记忆
    """
    if agent_type not in AGENT_PROMPTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_type} not found")

    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        # 获取 Agent 专属 prompt 和 Kernel
        agent_prompt = get_agent_prompt(agent_type)
        kernel = get_kernel()
        
        # 构建增强的查询（注入 Agent 角色）
        enhanced_query = f"""【当前角色】{AGENT_METADATA[agent_type]["name"]}
{agent_prompt}

【用户问题】
{request.message}"""
        
        # 使用 Kernel 执行（非流式，收集完整响应）
        full_response = ""
        async for event in kernel.run_stream(enhanced_query):
            if event.get("type") == "token":
                full_response += event.get("content", "")
            elif event.get("type") == "tool_output":
                # 工具输出可以选择是否附加
                pass
        
        return AgentChatResponse(
            reply=full_response,
            agent=agent_type,
            agent_name=AGENT_METADATA[agent_type]["name"],
            session_id=session_id
        )
        
    except Exception as e:
        print(f"[ERROR] LOD Agent chat error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_type}/chat/lod/stream")
async def api_agent_chat_lod_stream(agent_type: str, request: AgentChatRequest, current_user: dict = Depends(get_current_user)):
    """
    使用 LOD Kernel 的 Agent 流式对话端点
    """
    if agent_type not in AGENT_PROMPTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_type} not found")

    async def generate():
        try:
            agent_prompt = get_agent_prompt(agent_type)
            kernel = get_kernel()
            
            enhanced_query = f"""【当前角色】{AGENT_METADATA[agent_type]["name"]}
{agent_prompt}

【用户问题】
{request.message}"""
            
            async for event in kernel.run_stream(enhanced_query):
                evt_type = event.get("type")
                content = event.get("content", "")

                if evt_type == "token":
                    yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                elif evt_type == "code":
                    # 发送代码执行事件（让前端显示正在执行什么）
                    yield f"data: {json.dumps({'type': 'code', 'content': content})}\n\n"
                elif evt_type == "tool_output":
                    # 发送工具执行结果
                    yield f"data: {json.dumps({'type': 'tool_output', 'content': content})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({"type": "error", "content": str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

# ==================== MCP Protocol Support (新增) ====================
from mcp_server import router as mcp_router
app.include_router(mcp_router, prefix="/api")


# ==================== Soul 模块集成 ====================

try:
    from soul_api import router as soul_router
    app.include_router(soul_router, prefix="/api", tags=["Soul"])
    print("[INFO] Soul API 模块已加载")
except ImportError as e:
    print(f"[WARNING] Soul API 模块加载失败: {e}")


# ==================== 飞书机器人模块 ====================

try:
    from feishu_api import router as feishu_router
    app.include_router(feishu_router, prefix="/api", tags=["Feishu"])
    print("[INFO] 飞书 API 模块已加载")
except ImportError as e:
    print(f"[WARNING] 飞书 API 模块加载失败: {e}")


# ==================== 项目管理模块 ====================

try:
    from pm_api import router as pm_router
    app.include_router(pm_router, tags=["Project Management"])
    print("[INFO] 项目管理 API 模块已加载")
except ImportError as e:
    print(f"[WARNING] 项目管理 API 模块加载失败: {e}")

# ==================== 消息收集模块 (五纬度-维度1) ====================

try:
    from message_api import router as message_router
    app.include_router(message_router, prefix="/api", tags=["Messages"])
    print("[INFO] 消息收集 API 模块已加载")
except ImportError as e:
    print(f"[WARNING] 消息收集 API 模块加载失败: {e}")


# ==================== 信息中心模块 (五纬度日报) ====================

try:
    from info_hub_api import router as info_hub_router
    app.include_router(info_hub_router, prefix="/api", tags=["InfoHub"])
    print("[INFO] 信息中心 API 模块已加载")
except ImportError as e:
    print(f"[WARNING] 信息中心 API 模块加载失败: {e}")

# Email API
try:
    from email_api import router as email_router
    app.include_router(email_router, prefix="/api", tags=["Email"])
    print("[INFO] Email API 模块已加载")
except ImportError as e:
    print(f"[WARNING] Email API 加载失败: {e}")
