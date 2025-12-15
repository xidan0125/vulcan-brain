#!/usr/bin/env python3
"""
Vulcan Brain API Server - FastAPI Backend
模块化架构版本
"""
import time as time_module
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vulcan_libs.logger import api_logger, log_request
from config import CORS_ORIGINS

# ==================== FastAPI 应用初始化 ====================
app = FastAPI(
    title='Vulcan Brain API',
    description='AI Agent Backend with LOD Architecture',
    version='2.0.0'
)

# ==================== CORS 配置 ====================
ALLOWED_ORIGINS = CORS_ORIGINS + ["http://127.0.0.1:3000", "https://api.vsg-brain.com"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allow_headers=['*'],
)

# ==================== 异常处理器 ====================
from vulcan_libs.exceptions import register_exception_handlers
register_exception_handlers(app)

# ==================== 请求日志中间件 ====================
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time_module.time()
    response = await call_next(request)
    duration = (time_module.time() - start_time) * 1000
    
    user = "anonymous"
    if hasattr(request.state, 'user'):
        user = request.state.user.get('username', 'authenticated')
    
    log_request(
        method=request.method,
        path=str(request.url.path),
        user=user,
        status=response.status_code,
        duration_ms=duration
    )
    return response

# ==================== 启动事件 ====================
@app.on_event("startup")
async def initialize_app():
    """应用启动时的初始化"""
    from vulcan_libs.store import store
    await store.initialize_indexes()
    api_logger.info("[Startup] MongoDB indexes initialized")
    
    # 启动飞书定时任务
    try:
        from feishu import start_scheduler
        await start_scheduler()
        api_logger.info("[Startup] Feishu scheduler started")
    except Exception as e:
        api_logger.warning(f"[Startup] Feishu scheduler failed: {e}")

# ==================== 新模块化 Routers ====================
from api.routers.system_router import router as system_router
from api.routers.code_execution_router import router as code_execution_router
from api.routers.core_router import router as core_router
from api.routers.memory_router import router as memory_router
from api.routers.agent_router import router as agent_router
from api.routers.knowledge_router import router as knowledge_router
from api.routers.soul_router import router as soul_router_new

app.include_router(system_router)
app.include_router(code_execution_router)
app.include_router(core_router)
app.include_router(memory_router)
app.include_router(agent_router)
app.include_router(knowledge_router)
app.include_router(soul_router_new)

# ==================== 已有独立模块 ====================

# [Refactored] Consolidated Routers
from api.routers.auth_router import router as auth_router
from api.routers.chat_router import router as chat_router
from api.routers.legacy_chat_router import router as legacy_chat_router
from api.routers.mcp_router import router as mcp_router
# soul_router is already imported above as soul_router_new
from api.routers.project_router import router as pm_router
from api.routers.message_router import router as message_router
from api.routers.info_hub_router import router as info_hub_router
from api.routers.email_router import router as email_router
from api.routers.email_intel_router import router as email_intel_router
from api.routers.approval_router import router as approval_router
from api.routers.memory_v3_router import router as memory_v3_router
from api.routers.monitor_router import router as monitor_router

# Mounts
app.include_router(auth_router, prefix='/api')
app.include_router(chat_router, prefix='/api', tags=['Unified Chat'])
app.include_router(legacy_chat_router, prefix='/api', tags=['Legacy Chat'])
app.include_router(mcp_router, prefix='/api')
app.include_router(pm_router, tags=['Project Management'])
app.include_router(message_router, prefix='/api', tags=['Messages'])
app.include_router(info_hub_router, prefix='/api', tags=['InfoHub'])
app.include_router(email_router, prefix='/api', tags=['Email'])
app.include_router(email_intel_router, prefix='/api', tags=['Email Intel'])
app.include_router(approval_router, prefix='/api', tags=['Approval'])
app.include_router(memory_v3_router, prefix='/api', tags=['Memory v3'])
app.include_router(monitor_router, prefix='/api', tags=['V3 Monitor'])

# ==================== 启动入口 ====================
if __name__ == '__main__':
    import uvicorn
    from config import LLM_MODEL_NAME
    
    print('='*60)
    print('🚀 Vulcan Brain API Server v2.0 Starting...')
    print('='*60)
    print(f'📡 Endpoint: http://0.0.0.0:8001')
    print(f'📚 Docs: http://0.0.0.0:8001/docs')
    print(f'🔧 Model: {LLM_MODEL_NAME}')
    print('='*60)
    
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=8001,
        log_level='info'
    )

# ==================== V3 提取监控 API ====================
try:
    from v3_monitor_api import router as v3_monitor_router
    app.include_router(v3_monitor_router, prefix="/api", tags=["V3 Monitor"])
    print("[INFO] V3 提取监控 API 已加载")
except ImportError as e:
    print(f"[WARNING] V3 提取监控 API 未加载: {e}")
from api.routers.soul_extended_router import router as soul_extended_router
app.include_router(soul_extended_router, prefix='/api', tags=['Soul Extended'])
