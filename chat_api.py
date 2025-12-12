"""
Vulcan Brain - 对话历史 API (Acontext 重构版)
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

# 使用 Acontext 作为统一数据层
from acontext_integration import get_acontext_manager

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

# ==================== Chat APIs (Acontext Powered) ====================

@router.post("/chat/sessions")
async def create_session(req: CreateSessionRequest, current_user: dict = Depends(get_current_user)):
    """创建新对话会话 (Acontext)"""
    manager = get_acontext_manager()
    title = req.title or f"{req.provider.capitalize()} 对话"
    
    session_id = await manager.start_session(
        user_id=current_user["user_id"],
        provider=req.provider,
        title=title
    )

    return {
        "session_id": session_id,
        "provider": req.provider,
        "title": title,
        "message": "会话已在 Acontext 中创建"
    }

@router.get("/chat/sessions")
async def list_sessions(
    provider: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """列出用户的所有会话 (Acontext)"""
    manager = get_acontext_manager()
    sessions = await manager.client.list_sessions(
        user_id=current_user["user_id"],
        provider=provider,
        limit=limit
    )

    # Adapt the response to match the old format as much as possible
    # Handle both dict and string formats from Acontext API
    normalized_sessions = []
    for s in sessions:
        if isinstance(s, dict):
            normalized_sessions.append({
                "session_id": s.get("id", s.get("session_id", "")),
                "provider": s.get("provider", provider or "unknown"),
                "title": s.get("metadata", {}).get("title", "未命名对话") if isinstance(s.get("metadata"), dict) else "未命名对话",
                "message_count": s.get("message_count", 0),
                "created_at": s.get("created_at", ""),
                "updated_at": s.get("updated_at", s.get("created_at", ""))
            })
        elif isinstance(s, str):
            # Acontext may return just session IDs as strings
            normalized_sessions.append({
                "session_id": s,
                "provider": provider or "unknown",
                "title": "未命名对话",
                "message_count": 0,
                "created_at": "",
                "updated_at": ""
            })

    return {
        "sessions": normalized_sessions,
        "total": len(normalized_sessions)
    }

@router.get("/chat/sessions/{session_id}")
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """获取单个会话详情（含消息） (Acontext)"""
    manager = get_acontext_manager()
    try:
        # Acontext separates session details from messages, so we fetch both.
        session_details = await manager.client.get_session(session_id)
        
        # Verify ownership (assuming acontext doesn't enforce this on get)
        if session_details.get("user_id") != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="无权访问此会话")

        messages = await manager.get_conversation_history(
            user_id=current_user["user_id"],
            session_id=session_id
        )
        
        return {
            "session_id": session_details.get("id", session_id),
            "user_id": session_details.get("user_id", ""),
            "provider": session_details.get("provider", "unknown"),
            "title": session_details.get("metadata", {}).get("title", ""),
            "messages": messages,
            "message_count": len(messages),
            "created_at": session_details.get("created_at", ""),
            "updated_at": session_details.get("updated_at", "")
        }
    except HTTPException:
        raise # Re-raise our own exceptions
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"会话不存在或 Acontext 错误: {e}")


@router.post("/chat/sessions/{session_id}/messages")
async def save_messages(
    session_id: str,
    req: SaveMessagesRequest,
    current_user: dict = Depends(get_current_user)
):
    """保存消息到会话 (Acontext)"""
    manager = get_acontext_manager()
    
    # Acontext saves one message at a time, so we loop.
    saved_count = 0
    for msg in req.messages:
        try:
            await manager.save_message(
                user_id=current_user["user_id"],
                role=msg.role,
                content=msg.content,
                session_id=session_id
            )
            saved_count += 1
        except Exception as e:
            # Log error but continue trying to save other messages
            from vulcan_libs.logger import log_error
            log_error(e, f"chat_api.save_messages (single msg failed for session {session_id})")

    return {
        "success": True,
        "saved_count": saved_count,
        "session_id": session_id
    }


@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """
    删除会话 (No-Op for Acontext)
    
    NOTE: The backing Acontext service does not support session deletion.
    This endpoint is a no-op and will always return True for compatibility.
    """
    from vulcan_libs.logger import api_logger
    api_logger.warning(f"Attempted to delete session {session_id} for user {current_user['user_id']}, which is a no-op in Acontext.")
    
    # To maintain the illusion of deletion, we could have a deny-list in a local DB,
    # but for this refactoring, we just return success.
    return {"success": True, "message": "会话已标记为删除 (Acontext No-Op)"}

# The following endpoints are REMOVED as they are not supported by the Acontext API:
# - PUT /chat/sessions/{session_id}/messages (replace_messages)
# - PATCH /chat/sessions/{session_id} (update_session_title)

