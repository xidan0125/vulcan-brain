# ==================== P2 - 记忆系统 API (AContext 集成) ====================

@app.get("/api/memory/profile")
async def get_memory_profile():
    """
    P2 - 获取用户画像 (AContext + Vulcan Memory)
    
    整合 AContext 用户洞察 + Vulcan Memory 记忆
    """
    try:
        # 1. 获取 Vulcan Memory 数据
        from vulcan_libs.memory import get_all_memories
        memories_text = get_all_memories()
        memories_list = []
        if memories_text:
            for line in memories_text.strip().split("\n"):
                if line.strip() and line.startswith("-"):
                    memories_list.append(line[1:].strip())
        
        # 2. 尝试获取 AContext 用户洞察
        acontext_insights = None
        try:
            manager = get_acontext_manager()
            acontext_insights = await manager.get_user_insights("default_user")
        except Exception as e:
            print(f"[WARNING] AContext insights unavailable: {e}")
        
        return {
            "user_id": "default_user",
            "memories": memories_list,
            "memory_count": len(memories_list),
            "acontext_insights": acontext_insights,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memory/timeline")
async def get_memory_timeline(limit: int = 20):
    """
    P2 - 获取对话历史时间线 (AContext Sessions)
    
    从 AContext 获取真实会话历史
    """
    try:
        manager = get_acontext_manager()
        
        # 从 AContext 获取会话列表
        sessions = await manager.client.list_sessions(
            user_id="default_user",
            limit=limit
        )
        
        # 格式化为前端期望的格式
        conversations = []
        for session in sessions:
            conversations.append({
                "id": session.get("id", ""),
                "timestamp": session.get("created_at", session.get("updated_at", "")),
                "preview": session.get("title", session.get("context", {}).get("topic", "对话")),
                "message_count": session.get("message_count", 0),
                "metadata": session.get("metadata", {})
            })
        
        return {
            "conversations": conversations,
            "total_count": len(conversations)
        }
    except Exception as e:
        # 如果 AContext 不可用，返回空列表而非假数据
        print(f"[WARNING] AContext timeline unavailable: {e}")
        return {
            "conversations": [],
            "total_count": 0,
            "error": "AContext service unavailable"
        }
