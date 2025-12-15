"""
Vulcan Brain - 对话历史 API (VulcanStore 版)
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from vulcan_libs.store import store
from auth_api import get_current_user

router = APIRouter()

# ==================== Pydantic Models ====================

class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[int] = None

class CreateSessionRequest(BaseModel):
    provider: str = "gemini"
    title: Optional[str] = None

class SaveMessagesRequest(BaseModel):
    messages: List[Message]

# ==================== Chat APIs (VulcanStore) ====================

@router.post("/chat/sessions")
async def create_session(req: CreateSessionRequest, current_user: dict = Depends(get_current_user)):
    """创建新对话会话"""
    title = req.title or f"{req.provider.capitalize()} 对话"
    
    session_id = await store.create_session(
        user_id=current_user["user_id"],
        provider=req.provider,
        title=title
    )

    return {
        "session_id": session_id,
        "provider": req.provider,
        "title": title
    }


@router.get("/chat/sessions")
async def list_sessions(
    provider: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """列出用户的所有会话"""
    sessions = await store.list_sessions(
        user_id=current_user["user_id"],
        provider=provider,
        limit=limit
    )

    return {
        "sessions": [
            {
                "session_id": str(s.get("_id", "")),
                "provider": s.get("provider", "unknown"),
                "title": s.get("title", "未命名对话"),
                "message_count": s.get("message_count", 0),
                "created_at": s.get("created_at", "").isoformat() if s.get("created_at") else "",
                "updated_at": s.get("updated_at", "").isoformat() if s.get("updated_at") else ""
            }
            for s in sessions
        ],
        "total": len(sessions)
    }


@router.get("/chat/sessions/{session_id}")
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """获取单个会话详情（含消息）"""
    session = await store.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 验证所有权
    if session.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    messages = session.get("messages", [])
    
    return {
        "session_id": str(session.get("_id", "")),
        "user_id": session.get("user_id", ""),
        "provider": session.get("provider", "unknown"),
        "title": session.get("title", ""),
        "messages": messages,
        "message_count": len(messages),
        "created_at": session.get("created_at", "").isoformat() if session.get("created_at") else "",
        "updated_at": session.get("updated_at", "").isoformat() if session.get("updated_at") else ""
    }


@router.post("/chat/sessions/{session_id}/messages")
async def save_messages(
    session_id: str,
    req: SaveMessagesRequest,
    current_user: dict = Depends(get_current_user)
):
    """保存消息到会话"""
    # 验证会话存在且属于当前用户
    session = await store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="无权访问此会话")
    
    # 批量保存消息
    messages_to_save = [
        {"role": msg.role, "content": msg.content}
        for msg in req.messages
    ]
    
    await store.add_messages_batch(session_id, messages_to_save)

    return {
        "success": True,
        "saved_count": len(messages_to_save),
        "session_id": session_id
    }


@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """删除会话"""
    success = await store.delete_session(session_id, current_user["user_id"])
    
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在或无权删除")
    
    return {"success": True}
