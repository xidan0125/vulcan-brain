"""
Vulcan Brain - Session 管理器
实现会话持久化，支持上下文工程

基于 Google/Kaggle 白皮书:
- Session 是会话容器，包含 history[] 和 state{}
- 支持 truncation (保留最后N轮) 和 compaction (摘要压缩)
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

logger = logging.getLogger("SessionManager")


class SessionManager:
    """会话管理器 - MongoDB 持久化"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, mongo_uri: str = None):
        if hasattr(self, "_initialized"):
            return

        self.uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client.vulcan_brain
        self.collection = self.db.chat_sessions
        self._initialized = True
        logger.info("✅ SessionManager initialized")

    async def ensure_indexes(self):
        """创建索引"""
        await self.collection.create_index([("user_id", ASCENDING)])
        await self.collection.create_index([("updated_at", DESCENDING)])
        await self.collection.create_index(
            [("updated_at", ASCENDING)],
            expireAfterSeconds=30 * 24 * 3600  # 30天过期
        )
        logger.info("✅ Session indexes created")

    # ==================== 核心 CRUD ====================

    async def create_session(
        self,
        user_id: str,
        agent_id: str = "general",
        metadata: Dict = None
    ) -> str:
        """
        创建新会话

        Returns:
            session_id (str)
        """
        session = {
            "user_id": user_id,
            "agent_id": agent_id,
            "history": [],  # 对话历史 [{role, content, timestamp}]
            "state": {},    # 工作状态 (可存临时变量)
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "message_count": 0,
            "is_compacted": False,  # 是否已压缩
            "summary": None,  # 压缩后的摘要
        }
        result = await self.collection.insert_one(session)
        session_id = str(result.inserted_id)
        logger.info(f"✅ Created session {session_id} for user {user_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话"""
        try:
            session = await self.collection.find_one({"_id": ObjectId(session_id)})
            if session:
                session["_id"] = str(session["_id"])
            return session
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return None

    async def get_or_create_session(
        self,
        user_id: str,
        session_id: str = None,
        agent_id: str = "general"
    ) -> Dict:
        """
        获取现有会话或创建新会话

        如果提供 session_id 且存在，返回该会话
        否则创建新会话
        """
        if session_id:
            session = await self.get_session(session_id)
            if session:
                return session

        # 创建新会话
        new_session_id = await self.create_session(user_id, agent_id)
        return await self.get_session(new_session_id)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict = None
    ) -> bool:
        """
        添加消息到会话历史

        Args:
            session_id: 会话ID
            role: 'user' | 'assistant' | 'system' | 'tool'
            content: 消息内容
            metadata: 附加信息 (如 tool_calls)
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc),
            "metadata": metadata or {}
        }

        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$push": {"history": message},
                    "$inc": {"message_count": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error adding message to session {session_id}: {e}")
            return False

    async def get_history(
        self,
        session_id: str,
        max_turns: int = None,
        include_summary: bool = True
    ) -> List[Dict]:
        """
        获取会话历史 (用于构建 LLM 上下文)

        Args:
            session_id: 会话ID
            max_turns: 最大轮数 (None = 全部)
            include_summary: 是否在开头包含摘要

        Returns:
            消息列表 [{role, content}]
        """
        session = await self.get_session(session_id)
        if not session:
            return []

        history = session.get("history", [])

        # 如果有摘要且需要包含
        result = []
        if include_summary and session.get("summary"):
            result.append({
                "role": "system",
                "content": f"[对话摘要] {session['summary']}"
            })

        # 截断到最后 N 轮
        if max_turns and len(history) > max_turns:
            history = history[-max_turns:]

        # 转换格式 (去掉 timestamp 等)
        for msg in history:
            result.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        return result

    async def update_state(self, session_id: str, state: Dict) -> bool:
        """更新会话状态"""
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$set": {
                        "state": state,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating state for session {session_id}: {e}")
            return False

    async def set_summary(self, session_id: str, summary: str) -> bool:
        """设置会话摘要 (compaction 后调用)"""
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$set": {
                        "summary": summary,
                        "is_compacted": True,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error setting summary for session {session_id}: {e}")
            return False

    async def clear_old_history(
        self,
        session_id: str,
        keep_last: int = 10
    ) -> bool:
        """
        清理旧历史，只保留最后 N 条
        (compaction 后调用，配合 summary 使用)
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        history = session.get("history", [])
        if len(history) <= keep_last:
            return True

        # 只保留最后 N 条
        new_history = history[-keep_last:]

        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$set": {
                        "history": new_history,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            logger.info(f"Cleared history for session {session_id}: {len(history)} -> {len(new_history)}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error clearing history for session {session_id}: {e}")
            return False

    # ==================== 查询方法 ====================

    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """获取用户最近的会话列表"""
        cursor = self.collection.find(
            {"user_id": user_id}
        ).sort("updated_at", DESCENDING).limit(limit)

        sessions = []
        async for session in cursor:
            sessions.append({
                "session_id": str(session["_id"]),
                "agent_id": session.get("agent_id", "general"),
                "message_count": session.get("message_count", 0),
                "created_at": session.get("created_at"),
                "updated_at": session.get("updated_at"),
                "summary": session.get("summary")
            })
        return sessions

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        try:
            result = await self.collection.delete_one({"_id": ObjectId(session_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False


# ==================== 单例访问 ====================

_session_manager: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    """获取 SessionManager 单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


# ==================== 测试 ====================

if __name__ == "__main__":
    import asyncio

    async def test():
        manager = get_session_manager()
        await manager.ensure_indexes()

        # 创建会话
        session_id = await manager.create_session("test_user", "general")
        print(f"Created session: {session_id}")

        # 添加消息
        await manager.add_message(session_id, "user", "你好")
        await manager.add_message(session_id, "assistant", "你好！有什么可以帮助你的？")
        await manager.add_message(session_id, "user", "今天天气怎么样？")

        # 获取历史
        history = await manager.get_history(session_id)
        print(f"History: {history}")

        # 获取会话
        session = await manager.get_session(session_id)
        print(f"Session: {session}")

        # 清理
        await manager.delete_session(session_id)
        print("Session deleted")

    asyncio.run(test())
