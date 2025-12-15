# server.py - V4 (LOD Architecture with GPU Monitor)
"""
Vulcan Brain V4 - Unified Server Entry Point

架构：
- FastAPI (主控) + Chainlit (挂载)
- GPU Monitor API (/api/monitor)
- LOD 内核（在 app.py 中初始化）
"""

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from chainlit.utils import mount_chainlit
from vulcan_libs.monitor import get_gpu_stats_json
import json

# 1. 初始化标准的 FastAPI 应用
app = FastAPI(
    title="Vulcan Brain V4",
    description="Executive Dashboard with LOD Architecture",
    version="4.0.0"
)

# 2. 挂载 GPU 监控 API (核心路由)
@app.get("/api/monitor")
async def get_monitor_data():
    """
    实时 GPU 监控数据端点
    
    返回格式:
    {
        "timestamp": 1763644786.497,
        "gpu_count": 2,
        "gpus": [
            {
                "gpu_id": 0,
                "name": "RTX 5090",
                "utilization": 45,
                "memory_used": 24576,
                "memory_total": 49152,
                "memory_percent": 50.0,
                "temperature": 65,
                "power_draw": 350,
                "power_limit": 450
            },
            ...
        ]
    }
    """
    gpu_data_json = get_gpu_stats_json()
    gpu_data = json.loads(gpu_data_json)
    return JSONResponse(content=gpu_data)

# 3. 健康检查端点
@app.get("/api/health")
async def health_check():
    """系统健康检查"""
    return {
        "status": "online",
        "service": "Vulcan Brain V4",
        "architecture": "LOD (Level-of-Detail)",
        "kernel": "CodeAct V4"
    }

# 4. 将 Chainlit 应用挂载到根路径 "/"
# target="app.py" 指向 Chainlit 主逻辑文件
mount_chainlit(app=app, target="app.py", path="/")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Vulcan Brain V4 - Executive Dashboard")
    print("=" * 60)
    print("")
    print("架构模式: FastAPI + Chainlit (Mount Pattern)")
    print("内核版本: CodeAct V4 with LOD")
    print("硬件配置: Dual RTX 5090 (48GB VRAM × 2)")
    print("")
    print("服务端点:")
    print("   - GPU 监控: http://0.0.0.0:8000/api/monitor")
    print("   - 健康检查: http://0.0.0.0:8000/api/health")
    print("   - Chat UI : http://0.0.0.0:8000/")
    print("")
    print("按 Ctrl+C 停止服务")
    print("-" * 60)
    print("")
    
    # 启动服务
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
