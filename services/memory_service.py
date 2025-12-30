"""
Vulcan Brain - 统一记忆服务 v4.0
分层记忆注入：Core (总是) / Contextual (相关时) / Background (仅检索)
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from bson import ObjectId

logger = logging.getLogger("MemoryService")

# 摘要生成 Prompt
DIGEST_PROMPT = """请为以下对话生成一个简洁的摘要。

对话内容:
{conversation}

请输出JSON格式:
{{"title": "简短标题(10字以内)", "key_points": ["要点1", "要点2", "要点3"]}}

只输出JSON，无其他文字。"""


class MemoryService:
    """统一记忆服务 - 分层注入"""

    def __init__(self, db):
        self.db = db
        self.memories = db.user_memories
        self.pending = db.pending_memories
        self.digests = db.conversation_digests

    # ==================== 显式记忆 CRUD ====================

    async def remember(
        self,
        user_id: str,
        key: str,
        value: str,
        category: str = "fact",
        source: str = "user_confirmed",
        tier: str = "contextual",
        relevance_tags: List[str] = None
    ) -> Dict[str, Any]:
        """
        存储或更新一条记忆

        Args:
            user_id: 用户ID
            key: 记忆键
            value: 记忆值
            category: 分类 (identity | preference | fact)
            source: 来源 (user_confirmed | ai_extracted | manual)
            tier: 层级 (core | contextual | background)
            relevance_tags: 相关性标签列表
        """
        now = datetime.now(timezone.utc)

        update_doc = {
            "$set": {
                "value": value,
                "category": category,
                "source": source,
                "tier": tier,
                "relevance_tags": relevance_tags or [],
                "updated_at": now
            },
            "$setOnInsert": {"created_at": now}
        }

        result = await self.memories.update_one(
            {"user_id": user_id, "key": key},
            update_doc,
            upsert=True
        )

        logger.info(f"Memory saved: user={user_id}, key={key}, tier={tier}")
        return {"key": key, "value": value, "category": category, "tier": tier, "status": "saved"}

    async def recall(
        self,
        user_id: str,
        key: Optional[str] = None,
        category: Optional[str] = None,
        tier: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """查询记忆"""
        query = {"user_id": user_id}

        if key:
            query["key"] = {"$regex": key, "$options": "i"}
        if category:
            query["category"] = category
        if tier:
            query["tier"] = tier

        cursor = self.memories.find(query).limit(limit)
        results = await cursor.to_list(length=limit)

        for r in results:
            r["_id"] = str(r["_id"])

        return results

    async def forget(self, user_id: str, key: str) -> bool:
        """删除一条记忆"""
        result = await self.memories.delete_one({
            "user_id": user_id,
            "key": key
        })

        if result.deleted_count > 0:
            logger.info(f"Memory deleted: user={user_id}, key={key}")
            return True
        return False

    async def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户所有记忆"""
        cursor = self.memories.find({"user_id": user_id})
        results = await cursor.to_list(length=100)

        for r in results:
            r["_id"] = str(r["_id"])

        return results

    # ==================== 待确认记忆 ====================

    async def add_pending(
        self,
        user_id: str,
        session_id: str,
        key: str,
        value: str,
        category: str,
        confidence: float,
        context: str,
        tier: str = "contextual",
        relevance_tags: List[str] = None
    ) -> Dict[str, Any]:
        """添加待确认记忆 (带分层)"""
        now = datetime.now(timezone.utc)

        doc = {
            "user_id": user_id,
            "session_id": session_id,
            "key": key,
            "value": value,
            "category": category,
            "tier": tier,
            "relevance_tags": relevance_tags or [],
            "confidence": confidence,
            "context": context[:500] if context else "",
            "status": "pending",
            "created_at": now,
            "expires_at": now + timedelta(days=7)
        }

        result = await self.pending.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        doc["_id"] = doc["id"]

        logger.info(f"Pending memory added: user={user_id}, key={key}, tier={tier}")
        return doc

    async def get_pending(self, user_id: str) -> List[Dict[str, Any]]:
        """获取待确认记忆列表"""
        cursor = self.pending.find({
            "user_id": user_id,
            "status": "pending"
        }).sort("created_at", -1)

        results = await cursor.to_list(length=20)

        for r in results:
            r["_id"] = str(r["_id"])

        return results

    async def confirm_pending(self, pending_id: str) -> Optional[Dict[str, Any]]:
        """确认一条待确认记忆"""
        try:
            pending = await self.pending.find_one({"_id": ObjectId(pending_id)})
        except Exception:
            return None

        if not pending:
            return None

        # 存入正式记忆 (保留分层信息)
        memory = await self.remember(
            user_id=pending["user_id"],
            key=pending["key"],
            value=pending["value"],
            category=pending["category"],
            source="ai_extracted",
            tier=pending.get("tier", "contextual"),
            relevance_tags=pending.get("relevance_tags", [])
        )

        await self.pending.update_one(
            {"_id": ObjectId(pending_id)},
            {"$set": {"status": "confirmed"}}
        )

        logger.info(f"Memory confirmed: id={pending_id}")
        return memory

    async def reject_pending(self, pending_id: str) -> bool:
        """拒绝一条待确认记忆"""
        try:
            result = await self.pending.update_one(
                {"_id": ObjectId(pending_id)},
                {"$set": {"status": "rejected"}}
            )
            if result.modified_count > 0:
                logger.info(f"Memory rejected: id={pending_id}")
                return True
            return False
        except Exception:
            return False

    async def update_pending(
        self,
        pending_id: str,
        new_value: str
    ) -> Optional[Dict[str, Any]]:
        """编辑待确认记忆的值，然后确认"""
        try:
            await self.pending.update_one(
                {"_id": ObjectId(pending_id)},
                {"$set": {"value": new_value}}
            )
            return await self.confirm_pending(pending_id)
        except Exception:
            return None

    # ==================== 对话摘要 ====================

    async def save_digest(
        self,
        user_id: str,
        session_id: str,
        title: str,
        key_points: List[str]
    ) -> Dict[str, Any]:
        """保存对话摘要"""
        doc = {
            "user_id": user_id,
            "session_id": session_id,
            "title": title[:20],
            "key_points": key_points[:3],
            "created_at": datetime.now(timezone.utc)
        }

        result = await self.digests.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        doc["_id"] = doc["id"]

        logger.info(f"Digest saved: user={user_id}, title={title[:20]}")
        return doc

    async def get_recent_digests(
        self,
        user_id: str,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """获取最近的对话摘要"""
        cursor = self.digests.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit)

        results = await cursor.to_list(length=limit)

        for r in results:
            r["_id"] = str(r["_id"])

        return results

    async def generate_digest(
        self,
        user_id: str,
        session_id: str,
        messages: List[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """
        使用 LLM 生成对话摘要

        Args:
            user_id: 用户ID
            session_id: 会话ID
            messages: 对话消息列表 [{"role": "user/assistant", "content": "..."}]

        Returns:
            保存的摘要文档，失败返回 None
        """
        if not messages or len(messages) < 2:
            logger.warning("Not enough messages to generate digest")
            return None

        # 格式化对话
        conversation_lines = []
        for msg in messages[-20:]:  # 最多取最后20条
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")[:200]  # 截断长消息
            conversation_lines.append(f"{role}: {content}")

        conversation_text = "\n".join(conversation_lines)
        prompt = DIGEST_PROMPT.format(conversation=conversation_text)

        try:
            from vulcan_libs.llm_client import get_llm_client, ChatMessage, ModelType

            client = get_llm_client()
            llm_messages = [ChatMessage(role="user", content=prompt + " /no_think")]

            response = await client.chat(
                messages=llm_messages,
                model=ModelType.CPU,
                temperature=0.3,
                max_tokens=300,
                enable_thinking=False
            )

            content = response.content

            # 解析 JSON
            if "```" in content:
                match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
                if match:
                    content = match.group(1)

            content = content.strip()
            if not content.startswith("{"):
                start = content.find("{")
                if start >= 0:
                    content = content[start:]

            data = json.loads(content)
            title = data.get("title", "对话")[:20]
            key_points = data.get("key_points", [])[:3]

            # 保存摘要
            digest = await self.save_digest(
                user_id=user_id,
                session_id=session_id,
                title=title,
                key_points=key_points
            )

            logger.info(f"Digest generated: user={user_id}, title={title}")
            return digest

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse digest JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to generate digest: {e}")
            return None

    # ==================== 分层上下文构建 ====================

    def _check_relevance(self, message: str, tags: List[str]) -> bool:
        """检查消息是否与标签相关"""
        if not tags:
            return False

        message_lower = message.lower()
        for tag in tags:
            if tag.lower() in message_lower:
                return True
        return False

    async def build_context(
        self,
        user_id: str,
        current_message: str = ""
    ) -> str:
        """
        构建分层记忆上下文（用于 System Prompt 注入）

        Args:
            user_id: 用户ID
            current_message: 当前用户消息（用于判断 contextual 记忆是否相关）

        Returns:
            格式化的上下文文本
        """
        memories = await self.get_all(user_id)
        digests = await self.get_recent_digests(user_id, limit=5)

        # 分层筛选
        core_memories = []
        contextual_memories = []

        for m in memories:
            tier = m.get("tier", "contextual")  # 兼容旧数据

            if tier == "core":
                core_memories.append(m)
            elif tier == "contextual":
                # 检查是否与当前消息相关
                tags = m.get("relevance_tags", [])
                if current_message and self._check_relevance(current_message, tags):
                    contextual_memories.append(m)
            # background 记忆不主动注入

        lines = []

        # 核心记忆 (总是注入)
        if core_memories:
            lines.append("【用户核心信息】")
            for m in core_memories:
                lines.append(f"- {m['key']}: {m['value']}")

        # 相关的情境记忆
        if contextual_memories:
            lines.append("\n【相关背景】")
            for m in contextual_memories:
                lines.append(f"- {m['key']}: {m['value']}")

        # 最近对话 (只保留标题，不过多干扰)
        if digests:
            lines.append("\n【最近话题】")
            for d in digests[:3]:
                lines.append(f"- {d['title']}")

        return "\n".join(lines) if lines else ""

    async def build_context_legacy(self, user_id: str) -> str:
        """
        旧版上下文构建（兼容）- 注入所有记忆
        """
        memories = await self.get_all(user_id)
        digests = await self.get_recent_digests(user_id, limit=10)

        lines = []

        if memories:
            lines.append("【用户记忆】")
            for m in memories:
                lines.append(f"- {m['key']}: {m['value']}")

        if digests:
            lines.append("\n【最近对话】")
            for d in digests:
                date_str = d["created_at"].strftime("%m/%d") if d.get("created_at") else ""
                lines.append(f"- {date_str}: {d['title']}")

        return "\n".join(lines) if lines else ""


# ==================== 单例访问 ====================

_memory_service: Optional[MemoryService] = None


def get_memory_service(db=None) -> MemoryService:
    """获取 MemoryService 单例"""
    global _memory_service
    if _memory_service is None:
        if db is None:
            from vulcan_libs.store import store
            db = store.db
        _memory_service = MemoryService(db)
    return _memory_service
