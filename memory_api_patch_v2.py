# ==================== P2 - 记忆系统 API (AContext SDK 集成) ====================

@app.get("/api/memory/profile")
async def get_memory_profile():
    """
    P2 - 获取用户画像 (AContext + Vulcan Memory)
    """
    try:
        # 1. Vulcan Memory 数据
        from vulcan_libs.memory import get_all_memories
        memories_text = get_all_memories()
        memories_list = []
        if memories_text:
            for line in memories_text.strip().split("\n"):
                if line.strip() and line.startswith("-"):
                    memories_list.append(line[1:].strip())
        
        # 2. AContext 会话统计
        acontext_stats = None
        try:
            from acontext_sdk_helper import list_sessions
            sessions = list_sessions(limit=100)
            acontext_stats = {
                "total_sessions": len(sessions),
                "recent_sessions": [
                    {"id": s.id, "created_at": s.created_at}
                    for s in sessions[:5]
                ]
            }
        except Exception as e:
            print(f"[WARNING] AContext stats unavailable: {e}")
        
        return {
            "user_id": "default_user",
            "memories": memories_list,
            "memory_count": len(memories_list),
            "acontext_stats": acontext_stats,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memory/timeline")
async def get_memory_timeline(limit: int = 20):
    """
    P2 - 获取对话历史时间线 (AContext Sessions)
    """
    try:
        from acontext_sdk_helper import list_sessions
        sessions = list_sessions(limit=limit)
        
        conversations = []
        for session in sessions:
            conversations.append({
                "id": session.id,
                "timestamp": session.created_at,
                "preview": f"Session {session.id[:8]}...",
                "space_id": session.space_id,
                "updated_at": session.updated_at
            })
        
        return {
            "conversations": conversations,
            "total_count": len(conversations)
        }
    except Exception as e:
        print(f"[WARNING] AContext timeline unavailable: {e}")
        return {
            "conversations": [],
            "total_count": 0,
            "error": str(e)
        }
