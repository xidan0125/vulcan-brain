"""
信息中心 - 聊天 API
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from ._common import get_db, AnalyzeChatRequest
from services.chat_summary_store import get_chat_summary_store
from services.message_store import get_message_store

router = APIRouter(tags=["InfoHub-Chat"])


@router.get("/chats")
async def list_chats():
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

@router.get("/chat/{chat_id}")
async def get_chat_detail(chat_id: str, days: int = Query(7, ge=1, le=30)):
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


def _format_sender(s):
    """Map sender.id to sender.open_id for frontend compatibility"""
    return {
        "open_id": s.get("id"),
        "name": s.get("name"),
        "sender_type": s.get("sender_type"),
    }

@router.get("/chat/{chat_id}/messages")
async def get_chat_messages(chat_id: str, date: str = Query(None), limit: int = Query(50), offset: int = Query(0)):
    msg_store = get_message_store()
    since, until = None, None
    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            since = date_obj.replace(hour=0, minute=0, second=0)
            until = date_obj.replace(hour=23, minute=59, second=59)
        except:
            pass
    messages = await msg_store.get_chat_history(chat_id=chat_id, limit=limit + offset, since=since, until=until)
    messages = messages[offset:offset+limit]
    formatted = [{"message_id": m.get("message_id"), "sender": _format_sender(m.get("sender", {})), "content": m.get("content", ""), "timestamp": m.get("timestamp").isoformat() if isinstance(m.get("timestamp"), datetime) else m.get("timestamp")} for m in messages]
    return {"messages": formatted, "count": len(formatted)}

@router.post("/chat/{chat_id}/analyze")
async def analyze_chat(chat_id: str, req: AnalyzeChatRequest):
    date = req.date or datetime.now().strftime("%Y-%m-%d")
    try:
        result = await trigger_chat_analysis(chat_id, date)
        return {"success": bool(result), "analysis": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ===== 人员管理 API V2 =====
from services.people_store import get_people_store

class UpdatePersonRequest(BaseModel):
    department: Optional[str] = None
    function: Optional[str] = None
    projects: Optional[List[str]] = None


