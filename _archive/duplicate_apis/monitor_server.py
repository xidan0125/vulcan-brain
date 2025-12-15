# monitor_server.py
"""
Vulcan Brain v2.0 - Tower A: Hardware Monitor Service
独立监控服务，专注于 GPU 实时数据采集
"""

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from vulcan_libs.monitor import get_system_status

app = FastAPI(
    title="Vulcan Monitor Service",
    description="Dual RTX 5090 Real-time Monitoring API",
    version="1.0.0"
)

# --- 关键配置：允许跨域 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议改为 ["http://localhost:8000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/monitor")
async def get_monitor_data():
    """
    实时 GPU 监控数据端点
    
    返回格式:
    {
        "gpu_0": {"load": 45, "mem": 12.3},
        "gpu_1": {"load": 38, "mem": 8.7},
        "active": true
    }
    """
    return JSONResponse(content=get_system_status())

@app.get("/api/health")
async def health_check():
    """监控服务健康检查"""
    return {"status": "online", "tower": "A - Monitor Service"}

if __name__ == "__main__":
    print("=" * 60)
    print("⚡ Vulcan Monitor Service (Tower A)")
    print("=" * 60)
    print("端口: 8001")
    print("功能: Dual RTX 5090 实时监控")
    print("CORS: 已启用（允许跨域）")
    print("-" * 60)
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8001,
        log_level="info"
    )
