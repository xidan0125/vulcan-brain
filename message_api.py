"""
消息收集+分析 API - (Acontext 重构版)

端点:
- POST /messages/collect - 采集+分析 (原子操作)
- GET /messages/history - 获取历史消息 (Acontext)
- GET /messages/search - 搜索消息 (Acontext)
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
import logging

# Acontext-powered collector
from services.feishu_collector import get_message_collector
# Acontext manager for queries
from acontext_integration import get_acontext_manager

logger = logging.getLogger("MessageAPI")

router = APIRouter(prefix="/messages", tags=["Messages"])


class CollectRequest(BaseModel):
    """收集请求"""
    chat_ids: List[str]
    since_hours: int = 24
    send_notice: bool = True


class CollectResponse(BaseModel):
    """收集响应"""
    success: bool
    results: dict
    message: str


# ===== API 端点 =====

@router.post("/collect", response_model=CollectResponse)
async def collect_messages(req: CollectRequest):
    """
    采集飞书群聊消息并存入 Acontext
    """
    collector = get_message_collector()
    results = {}
    
    since = datetime.now() - timedelta(hours=req.since_hours)
    
    for chat_id in req.chat_ids:
        try:
            collect_result = await collector.collect_chat_messages(chat_id, since=since)
            if req.send_notice:
                await collector.send_collection_notice(chat_id, collect_result)
            results[chat_id] = collect_result
        except Exception as e:
            logger.error(f"[MessageAPI] 采集失败: {chat_id} - {e}")
            results[chat_id] = {"error": str(e)}
    
    total_inserted = sum(
        r.get("inserted", 0) 
        for r in results.values() 
        if "error" not in r
    )
    
    return CollectResponse(
        success=True,
        results=results,
        message=f"完成: {len(req.chat_ids)} 个群聊被处理, {total_inserted} 条新消息存入 Acontext"
    )


@router.get("/history")
async def get_history(
    chat_id: str = Query(..., description="群聊ID (将作为 Acontext session_id)"),
    limit: int = Query(50, ge=1, le=500, description="返回条数")
):
    """
    获取群聊历史消息 (from Acontext)
    """
    manager = get_acontext_manager()
    user_id = f"feishu_chat_{chat_id}" # Synthetic user_id used during collection
    
    try:
        messages = await manager.get_conversation_history(
            user_id=user_id,
            session_id=chat_id,
            limit=limit
        )
        return {
            "chat_id": chat_id,
            "count": len(messages),
            "messages": messages
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history from Acontext: {e}")


@router.get("/search")
async def search_messages(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    chat_id: str = Query(..., description="限定群聊ID"),
    limit: int = Query(10, ge=1, le=100, description="返回条数")
):
    """
    在群聊知识库中进行语义搜索 (via Acontext)
    """
    manager = get_acontext_manager()
    space_id = f"feishu_chat_{chat_id}" # Derived from chat_id
    
    try:
        results = await manager.client.search_space(
            space_id=space_id,
            query=keyword,
            limit=limit
        )
        return {
            "keyword": keyword,
            "chat_id": chat_id,
            "count": len(results),
            "messages": results # Results are documents from the space
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search in Acontext space: {e}")

# NOTE: /stats and /today endpoints have been removed as they are not
# directly supported by the Acontext backend.
# The scheduled-collect endpoint is also removed as it duplicates /collect logic.
# Cron jobs should call the /collect endpoint directly.
