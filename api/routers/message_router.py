"""
消息收集+分析 API - (VulcanStore 版)

端点:
- POST /messages/collect - 采集消息 (简化版)
- GET /messages/history - 获取历史消息
- GET /messages/search - 搜索消息
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
import logging

from vulcan_libs.store import store

logger = logging.getLogger("MessageAPI")

router = APIRouter(prefix="/messages", tags=["Messages"])


class CollectRequest(BaseModel):
    """收集请求"""
    chat_ids: List[str]
    since_hours: int = 24


class CollectResponse(BaseModel):
    """收集响应"""
    success: bool
    results: dict
    message: str


# ===== API 端点 =====

@router.post("/collect", response_model=CollectResponse)
async def collect_messages(req: CollectRequest):
    """
    采集飞书群聊消息 (简化版 - 直接存 MongoDB)
    
    NOTE: 完整的飞书消息采集功能需要单独的 collector 模块
    """
    # TODO: 实现简化版的消息采集
    return CollectResponse(
        success=True,
        results={chat_id: {"status": "pending"} for chat_id in req.chat_ids},
        message=f"消息采集功能待实现 (VulcanStore 版)"
    )


@router.get("/history")
async def get_history(
    chat_id: str = Query(..., description="群聊ID"),
    limit: int = Query(50, ge=1, le=500, description="返回条数")
):
    """
    获取群聊历史消息
    """
    try:
        # 使用 chat_id 作为 session_id 查询
        session = await store.get_session(chat_id)
        
        if not session:
            return {
                "chat_id": chat_id,
                "count": 0,
                "messages": []
            }
        
        messages = session.get("messages", [])[-limit:]
        
        return {
            "chat_id": chat_id,
            "count": len(messages),
            "messages": messages
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史失败: {e}")


@router.get("/search")
async def search_messages(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    chat_id: str = Query(None, description="限定群聊ID (可选)"),
    limit: int = Query(10, ge=1, le=100, description="返回条数")
):
    """
    搜索消息 (简单文本匹配)
    
    NOTE: 语义搜索功能需要集成 RAG 模块
    """
    try:
        # 简单实现：从 MongoDB 搜索
        # TODO: 集成 RAG 实现语义搜索
        results = await store.search_messages(
            keyword=keyword,
            chat_id=chat_id,
            limit=limit
        )
        
        return {
            "keyword": keyword,
            "chat_id": chat_id,
            "count": len(results),
            "messages": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")
