"""
Vulcan Brain API - 系统状态路由
P1 系统状态 + 健康检查
"""
from fastapi import APIRouter, Depends
from datetime import datetime
from typing import Dict, Any

from api.dependencies import (
    get_gpu_stats, 
    get_vram_stats, 
    performance_metrics, 
    thinking_logs,
    GPU_AVAILABLE
)
from auth_api import get_current_user

router = APIRouter(tags=["System"])


@router.get('/api/system/status')
async def system_status(current_user: dict = Depends(get_current_user)):
    """
    P1 - Inspector 面板数据
    
    返回实时系统状态（GPU、VRAM、性能指标、思考日志）
    建议前端每 1-2 秒轮询一次
    """
    return {
        'gpu': get_gpu_stats(),
        'vram': get_vram_stats(),
        'performance': {
            'tokens_per_second': round(performance_metrics['tokens_per_second'], 2),
            'ttft': round(performance_metrics['ttft'], 3),
            'latency': round(performance_metrics['latency'], 4),
            'last_query': performance_metrics['last_query_time']
        },
        'thinking_process': thinking_logs[-5:],
        'timestamp': datetime.now().isoformat()
    }


@router.get('/api/health')
async def health_check():
    """健康检查接口"""
    return {
        'status': 'healthy',
        'service': 'Vulcan Brain API',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'gpu_monitoring': GPU_AVAILABLE
    }
