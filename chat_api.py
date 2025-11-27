"""
Vulcan Brain - 对话历史 API (VulcanStore 重构版)
支持多 AI 提供商 (gemini, vulcan, agent等)

重构说明：
- 移除直接的 pymongo 调用
- 使用 VulcanStore 单例进行数据操作
- 保持 API 接口完全兼容
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

# 使用 VulcanStore 统一数据层
from vulcan_libs.store import store

router = APIRouter()

# ==================== Pydantic Models ====================

class Message(BaseModel):
    role: str  # user | assistant | system
    content: str
    timestamp: Optional[int] = None

class CreateSessionRequest(BaseModel):
    provider: str = "gemini"  # gemini | vulcan | agent
    title: Optional[str] = None

class SaveMessagesRequest(BaseModel):
    messages: List[Message]

class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    provider: str
    title: str
    message_count: int
    created_at: str
    updated_at: str

# ==================== Auth Helper ====================

from auth_api import get_current_user

# ==================== Chat APIs ====================

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
        "title": title,
        "message": "会话已创建"
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
                "session_id": s.get("_id", ""),
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
    
    # 验证会话属于当前用户
    if session.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    return {
        "session_id": session.get("_id", session_id),
        "user_id": session.get("user_id", ""),
        "provider": session.get("provider", "unknown"),
        "title": session.get("title", ""),
        "messages": session.get("messages", []),
        "message_count": len(session.get("messages", [])),
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
    # 先验证会话存在且属于当前用户
    session = await store.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    # 准备消息
    messages_to_save = [
        {
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp or int(datetime.now().timestamp() * 1000)
        }
        for msg in req.messages
    ]

    # 使用 VulcanStore 批量追加消息
    await store.add_messages_batch(session_id, messages_to_save)

    return {
        "success": True,
        "saved_count": len(messages_to_save),
        "session_id": session_id
    }

@router.put("/chat/sessions/{session_id}/messages")
async def replace_messages(
    session_id: str,
    req: SaveMessagesRequest,
    current_user: dict = Depends(get_current_user)
):
    """替换会话的所有消息（用于同步完整对话）"""
    # 验证会话
    session = await store.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    # 准备消息
    messages = [
        {
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp or int(datetime.now().timestamp() * 1000)
        }
        for msg in req.messages
    ]

    # 自动生成标题
    first_user_msg = next((m for m in messages if m["role"] == "user"), None)
    title = session.get("title", "")
    if first_user_msg and (title.endswith(" 对话") or not title):
        content = first_user_msg["content"]
        title = content[:30] + ("..." if len(content) > 30 else "")

    # 直接更新 (使用底层 db 访问)
    from bson import ObjectId
    await store.db.chat_sessions.update_one(
        {"_id": ObjectId(session_id)},
        {
            "$set": {
                "messages": messages,
                "message_count": len(messages),
                "title": title,
                "updated_at": datetime.now()
            }
        }
    )

    return {
        "success": True,
        "message_count": len(messages),
        "session_id": session_id
    }

@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """删除会话"""
    success = await store.delete_session(session_id, current_user["user_id"])
    
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {"success": True, "message": "会话已删除"}

@router.patch("/chat/sessions/{session_id}")
async def update_session_title(
    session_id: str,
    title: str,
    current_user: dict = Depends(get_current_user)
):
    """更新会话标题"""
    # 验证会话存在且属于当前用户
    session = await store.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    # 更新标题
    from bson import ObjectId
    await store.db.chat_sessions.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"title": title, "updated_at": datetime.now()}}
    )

    return {"success": True, "title": title}
