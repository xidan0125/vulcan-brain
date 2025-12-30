"""
Vulcan Brain API - 记忆系统路由
P2 记忆系统 API (VulcanStore)
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vulcan_libs.store import store
from api.routers.auth_router import get_current_user

router = APIRouter(tags=["Memory"])


# === Pydantic Models ===
class MemoryCreateRequest(BaseModel):
    content: str
    category: str = "general"


# === API Endpoints ===
@router.get("/api/memory/profile")
async def get_memory_profile(current_user: dict = Depends(get_current_user)):
    """
    P2 - 获取用户画像 (VulcanStore)
    """
    user_id = current_user["user_id"]
    try:
        # 1. 使用 VulcanStore 获取用户记忆
        memories = await store.get_memories(user_id, limit=50)
        memories_list = [
            {
                "id": str(mem.get("_id", "")),
                "content": mem.get("content", ""),
                "category": mem.get("category", "general"),
                "created_at": mem.get("created_at", "").isoformat() if mem.get("created_at") else ""
            }
            for mem in memories
        ]
        
        # 2. 获取对话统计
        chat_stats = None
        try:
            sessions = await store.list_sessions(user_id, limit=100)
            chat_stats = {
                "total_sessions": len(sessions),
                "recent_sessions": [
                    {"id": str(s.get("_id", "")), "title": s.get("title", "")}
                    for s in sessions[:5]
                ]
            }
        except Exception as e:
            print(f"[WARNING] Chat stats unavailable: {e}")
        
        return {
            "user_id": user_id,
            "memories": memories_list,
            "memory_count": len(memories_list),
            "chat_stats": chat_stats,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory/timeline")
async def get_memory_timeline(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """
    P2 - 获取对话历史时间线 (VulcanStore Sessions)
    """
    user_id = current_user["user_id"]
    try:
        # 使用 VulcanStore 获取会话列表
        sessions = await store.list_sessions(user_id, limit=limit)
        
        conversations = []
        for session in sessions:
            conversations.append({
                "id": str(session.get("_id", "")),
                "timestamp": session.get("created_at", "").isoformat() if session.get("created_at") else "",
                "preview": session.get("title", "")[:50] if session.get("title") else "Untitled",
                "updated_at": session.get("updated_at", "").isoformat() if session.get("updated_at") else ""
            })
        
        return {
            "conversations": conversations,
            "total_count": len(conversations)
        }
    except Exception as e:
        print(f"[WARNING] Timeline unavailable: {e}")
        return {
            "conversations": [],
            "total_count": 0,
            "error": str(e)
        }


@router.post("/api/memory")
async def add_memory(request: MemoryCreateRequest, current_user: dict = Depends(get_current_user)):
    """添加记忆"""
    user_id = current_user["user_id"]
    try:
        memory_id = await store.add_memory(
            user_id=user_id,
            content=request.content,
            category=request.category
        )
        return {"success": True, "memory_id": str(memory_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: str, current_user: dict = Depends(get_current_user)):
    """删除记忆"""
    try:
        await store.delete_memory(memory_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory/search")
async def search_memory(
    query: str,
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """搜索记忆"""
    user_id = current_user["user_id"]
    try:
        results = await store.search_memories(user_id, query, limit=limit)
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
