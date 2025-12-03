"""
消息收集+分析 API - 五纬度信息收集系统 (维度1: 聊天记录)

重构: 采集和分析原子化 - 一次调用完成两步

端点:
- POST /messages/collect - 采集+分析 (原子操作)
- GET /messages/history - 获取历史消息
- GET /messages/search - 搜索消息
- GET /messages/stats - 消息统计
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
import logging

from services.message_store import (
    get_message_store,
    get_message_collector,
    scheduled_collect_job
)
from services.realtime_analyzer import trigger_chat_analysis

logger = logging.getLogger("MessageAPI")

router = APIRouter(prefix="/messages", tags=["Messages"])


class CollectRequest(BaseModel):
    """收集请求"""
    chat_ids: List[str]  # 要收集的群聊ID列表
    since_hours: int = 24  # 收集多少小时内的消息 (默认24小时)
    send_notice: bool = True  # 是否发送收集通知
    skip_analysis: bool = False  # 是否跳过分析 (默认False=执行分析)


class CollectResponse(BaseModel):
    """收集响应"""
    success: bool
    results: dict
    message: str


# ===== API 端点 =====

@router.post("/collect", response_model=CollectResponse)
async def collect_messages(req: CollectRequest):
    """
    采集+分析 (原子操作)
    
    - chat_ids: 要收集的群聊ID列表
    - since_hours: 收集多少小时内的消息
    - send_notice: 收集完成后是否发送群通知
    - skip_analysis: 是否跳过AI分析 (默认执行分析)
    """
    collector = get_message_collector()
    results = {}
    
    since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if req.since_hours < 24:
        from datetime import timedelta
        since = datetime.now() - timedelta(hours=req.since_hours)
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    for chat_id in req.chat_ids:
        try:
            # 1. 采集消息
            collect_result = await collector.collect_chat_messages(chat_id, since=since)
            
            # 2. 发送通知 (可选)
            if req.send_notice:
                await collector.send_collection_notice(chat_id, collect_result)
            
            # 3. 触发AI分析 (原子化关键步骤)
            analysis_result = None
            if not req.skip_analysis:
                try:
                    logger.info(f"[MessageAPI] 触发分析: {chat_id}")
                    analysis_result = await trigger_chat_analysis(chat_id, today)
                    logger.info(f"[MessageAPI] 分析完成: {chat_id}")
                except Exception as e:
                    logger.error(f"[MessageAPI] 分析失败: {chat_id} - {e}")
                    analysis_result = {"error": str(e)}
            
            results[chat_id] = {
                "collection": collect_result,
                "analysis": analysis_result
            }
            
        except Exception as e:
            logger.error(f"[MessageAPI] 采集失败: {chat_id} - {e}")
            results[chat_id] = {"error": str(e)}
    
    total_inserted = sum(
        r.get("collection", {}).get("inserted", 0) 
        for r in results.values() 
        if isinstance(r, dict) and "error" not in r
    )
    total_analyzed = sum(
        1 for r in results.values() 
        if isinstance(r, dict) and r.get("analysis") and "error" not in r.get("analysis", {})
    )
    
    return CollectResponse(
        success=True,
        results=results,
        message=f"完成: 新增 {total_inserted} 条消息, 分析 {total_analyzed} 个群聊"
    )


@router.get("/history")
async def get_history(
    chat_id: str = Query(..., description="群聊ID"),
    limit: int = Query(50, ge=1, le=500, description="返回条数"),
    since: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    until: Optional[str] = Query(None, description="结束时间 (ISO格式)")
):
    """
    获取群聊历史消息
    """
    store = get_message_store()
    
    since_dt = datetime.fromisoformat(since) if since else None
    until_dt = datetime.fromisoformat(until) if until else None
    
    messages = await store.get_chat_history(
        chat_id=chat_id,
        limit=limit,
        since=since_dt,
        until=until_dt
    )
    
    # 转换为可序列化格式
    for msg in messages:
        if "_id" in msg:
            msg["_id"] = str(msg["_id"])
        if "timestamp" in msg and isinstance(msg["timestamp"], datetime):
            msg["timestamp"] = msg["timestamp"].isoformat()
        if "created_at" in msg and isinstance(msg["created_at"], datetime):
            msg["created_at"] = msg["created_at"].isoformat()
    
    return {
        "chat_id": chat_id,
        "count": len(messages),
        "messages": messages
    }


@router.get("/today")
async def get_today_messages(
    chat_id: str = Query(..., description="群聊ID")
):
    """
    获取今日消息
    """
    store = get_message_store()
    messages = await store.get_today_messages(chat_id)
    
    # 转换格式
    for msg in messages:
        if "_id" in msg:
            msg["_id"] = str(msg["_id"])
        if "timestamp" in msg and isinstance(msg["timestamp"], datetime):
            msg["timestamp"] = msg["timestamp"].isoformat()
        if "created_at" in msg and isinstance(msg["created_at"], datetime):
            msg["created_at"] = msg["created_at"].isoformat()
    
    return {
        "chat_id": chat_id,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "count": len(messages),
        "messages": messages
    }


@router.get("/search")
async def search_messages(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    chat_id: Optional[str] = Query(None, description="限定群聊ID"),
    limit: int = Query(20, ge=1, le=100, description="返回条数")
):
    """
    搜索消息内容
    """
    store = get_message_store()
    messages = await store.search_messages(
        keyword=keyword,
        chat_id=chat_id,
        limit=limit
    )
    
    # 转换格式
    for msg in messages:
        if "_id" in msg:
            msg["_id"] = str(msg["_id"])
        if "timestamp" in msg and isinstance(msg["timestamp"], datetime):
            msg["timestamp"] = msg["timestamp"].isoformat()
        if "created_at" in msg and isinstance(msg["created_at"], datetime):
            msg["created_at"] = msg["created_at"].isoformat()
    
    return {
        "keyword": keyword,
        "chat_id": chat_id,
        "count": len(messages),
        "messages": messages
    }


@router.get("/stats")
async def get_stats(
    chat_id: Optional[str] = Query(None, description="群聊ID (不填则返回所有群统计)")
):
    """
    获取消息统计
    """
    store = get_message_store()
    stats = await store.get_stats(chat_id)
    
    # 转换日期格式
    for item in stats:
        if "first_msg" in item and isinstance(item["first_msg"], datetime):
            item["first_msg"] = item["first_msg"].isoformat()
        if "last_msg" in item and isinstance(item["last_msg"], datetime):
            item["last_msg"] = item["last_msg"].isoformat()
    
    return {
        "chat_id": chat_id,
        "stats": stats
    }


# ===== 定时任务端点 =====

@router.post("/scheduled-collect")
async def run_scheduled_collect(
    chat_ids: List[str] = Query(..., description="要收集的群聊ID列表")
):
    """
    执行定时收集+分析任务 (供 cron 调用)
    
    与 /collect 相同逻辑，采集后立即分析
    """
    # 复用 collect 逻辑
    req = CollectRequest(
        chat_ids=chat_ids,
        since_hours=24,
        send_notice=False,
        skip_analysis=False
    )
    return await collect_messages(req)
