"""
聊天 API 模块
/api/info-hub/chat/*
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from services.message_store import get_message_store
from services.chat_summary_store import get_chat_summary_store
from services.realtime_analyzer import trigger_chat_analysis

router = APIRouter(prefix="/chat", tags=["Chat"])


class AnalyzeChatRequest(BaseModel):
    date: Optional[str] = None


def _format_sender(s: dict) -> dict:
    """格式化发送者信息"""
    return {
        "open_id": s.get("id"),
        "name": s.get("name"),
        "sender_type": s.get("sender_type"),
    }


@router.get("/list")
async def list_chats():
    """获取群聊列表"""
    summary_store = get_chat_summary_store()
    msg_store = get_message_store()
    stats = await msg_store.get_stats()
    
    chats = []
    for stat in stats:
        chat_id = stat.get("_id")
        if not chat_id:
            continue
        metadata = await summary_store.get_chat_metadata(chat_id)
        chats.append({
            "chat_id": chat_id,
            "chat_name": metadata.get("chat_name", f"群聊_{chat_id[-8:]}") if metadata else f"群聊_{chat_id[-8:]}",
            "total_messages": stat.get("total", 0),
        })
    
    return {"chats": chats, "count": len(chats)}


@router.get("/{chat_id}")
async def get_chat_detail(chat_id: str, days: int = Query(7, ge=1, le=30)):
    """获取群聊详情"""
    summary_store = get_chat_summary_store()
    msg_store = get_message_store()
    
    metadata = await summary_store.get_chat_metadata(chat_id)
    stats_list = await msg_store.get_stats(chat_id)
    stats = stats_list[0] if stats_list else {}
    summaries = await summary_store.get_chat_history_summaries(chat_id, days)
    
    history = []
    for s in summaries:
        analysis = s.get("analysis", {})
        history.append({
            "date": s["date"],
            "messages_analyzed": s.get("messages_analyzed", 0),
            "summary": analysis.get("summary", ""),
            "decisions": analysis.get("decisions", []),
            "action_items": analysis.get("action_items", []),
            "risks": analysis.get("risks", []),
            "topics": analysis.get("topics", []),
        })
    
    return {
        "chat_id": chat_id,
        "chat_name": metadata.get("chat_name", f"群聊_{chat_id[-8:]}") if metadata else f"群聊_{chat_id[-8:]}",
        "total_messages": stats.get("total", 0),
        "history": history
    }


@router.get("/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str,
    date: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """获取群聊消息"""
    msg_store = get_message_store()
    
    since, until = None, None
    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            since = date_obj.replace(hour=0, minute=0, second=0)
            until = date_obj.replace(hour=23, minute=59, second=59)
        except:
            pass
    
    messages = await msg_store.get_chat_history(
        chat_id=chat_id,
        limit=limit + offset,
        since=since,
        until=until
    )
    messages = messages[offset:offset+limit]
    
    formatted = []
    for m in messages:
        formatted.append({
            "message_id": m.get("message_id"),
            "sender": _format_sender(m.get("sender", {})),
            "content": m.get("content", ""),
            "timestamp": m.get("timestamp").isoformat() if isinstance(m.get("timestamp"), datetime) else m.get("timestamp")
        })
    
    return {"messages": formatted, "count": len(formatted)}


@router.post("/{chat_id}/analyze")
async def analyze_chat(chat_id: str, req: AnalyzeChatRequest):
    """触发群聊分析"""
    date = req.date or datetime.now().strftime("%Y-%m-%d")
    try:
        result = await trigger_chat_analysis(chat_id, date)
        return {"success": bool(result), "analysis": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
