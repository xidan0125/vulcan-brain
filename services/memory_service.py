"""
Vulcan Brain - 统一记忆服务 v3.0
基于 2025 最佳实践：简单 > 复杂，显式 > 隐式，用户控制
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from bson import ObjectId

logger = logging.getLogger("MemoryService")


class MemoryService:
    """统一记忆服务 - 单一入口"""

    def __init__(self, db):
        """
        Args:
            db: MongoDB 数据库实例 (AsyncIOMotorDatabase)
        """
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
        source: str = "user_confirmed"
    ) -> Dict[str, Any]:
        """
        存储或更新一条记忆

        Args:
            user_id: 用户ID
            key: 记忆键 (如 name, role, pref_style)
            value: 记忆值
            category: 分类 (identity | preference | fact)
            source: 来源 (user_confirmed | ai_extracted | manual)

        Returns:
            保存结果
        """
        now = datetime.now(timezone.utc)

        result = await self.memories.update_one(
            {"user_id": user_id, "key": key},
            {
                "$set": {
                    "value": value,
                    "category": category,
                    "source": source,
                    "updated_at": now
                },
                "$setOnInsert": {"created_at": now}
            },
            upsert=True
        )

        logger.info(f"Memory saved: user={user_id}, key={key}")
        return {"key": key, "value": value, "category": category, "status": "saved"}

    async def recall(
        self,
        user_id: str,
        key: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        查询记忆

        Args:
            user_id: 用户ID
            key: 可选，模糊匹配键名
            category: 可选，按分类筛选
            limit: 最大返回数量

        Returns:
            记忆列表
        """
        query = {"user_id": user_id}

        if key:
            query["key"] = {"$regex": key, "$options": "i"}
        if category:
            query["category"] = category

        cursor = self.memories.find(query).limit(limit)
        results = await cursor.to_list(length=limit)

        # 转换 ObjectId
        for r in results:
            r["_id"] = str(r["_id"])

        return results

    async def forget(self, user_id: str, key: str) -> bool:
        """
        删除一条记忆

        Args:
            user_id: 用户ID
            key: 记忆键

        Returns:
            是否删除成功
        """
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
        context: str
    ) -> Dict[str, Any]:
        """
        添加待确认记忆

        Args:
            user_id: 用户ID
            session_id: 来源会话ID
            key: 提取的键
            value: 提取的值
            category: 建议分类
            confidence: 置信度 0-1
            context: 提取时的用户消息

        Returns:
            待确认记忆文档
        """
        now = datetime.now(timezone.utc)

        doc = {
            "user_id": user_id,
            "session_id": session_id,
            "key": key,
            "value": value,
            "category": category,
            "confidence": confidence,
            "context": context[:500] if context else "",
            "status": "pending",
            "created_at": now,
            "expires_at": now + timedelta(days=7)  # 7天过期
        }

        result = await self.pending.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        doc["_id"] = doc["id"]

        logger.info(f"Pending memory added: user={user_id}, key={key}, confidence={confidence}")
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
        """
        确认一条待确认记忆

        Args:
            pending_id: 待确认记忆ID

        Returns:
            确认后的正式记忆，失败返回 None
        """
        try:
            pending = await self.pending.find_one({"_id": ObjectId(pending_id)})
        except Exception:
            return None

        if not pending:
            return None

        # 存入正式记忆
        memory = await self.remember(
            user_id=pending["user_id"],
            key=pending["key"],
            value=pending["value"],
            category=pending["category"],
            source="ai_extracted"
        )

        # 更新待确认状态
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
        """
        编辑待确认记忆的值，然后确认

        Args:
            pending_id: 待确认记忆ID
            new_value: 新的值

        Returns:
            确认后的正式记忆
        """
        try:
            # 更新值
            await self.pending.update_one(
                {"_id": ObjectId(pending_id)},
                {"$set": {"value": new_value}}
            )
            # 然后确认
            return await self.confirm_pending(pending_id)
        except Exception:
            return None

    # ==================== 对话摘要 ====================


    async def generate_digest(
        self,
        user_id: str,
        session_id: str,
        messages: List[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """
        自动生成对话摘要（调用 LLM）
        
        Args:
            user_id: 用户ID
            session_id: 会话ID  
            messages: 对话消息列表 [{role, content}, ...]
            
        Returns:
            摘要文档 {title, key_points, user_intent}
        """
        if not messages or len(messages) < 2:
            return None
            
        # 构建对话文本
        conv_text = "\n".join([
            f"{m.get('role', 'user')}: {m.get('content', '')[:200]}"
            for m in messages[-20:]  # 最多取最后20轮
        ])
        
        prompt = f"""为以下对话生成简洁摘要。

对话内容:
{conv_text}

输出 JSON（无其他文字）:
{{"title": "10字以内的标题", "key_points": ["关键点1", "关键点2"], "user_intent": "用户的主要目的"}}

注意：
- title 必须在10字以内
- key_points 最多3条，每条20字以内
- 如果对话太短或无实质内容，返回 {{"skip": true}}
"""
        
        try:
            import httpx
            import json
            import os
            
            qwen_url = os.getenv("QWEN3_BASE_URL", "http://localhost:8000/v1")
            
            async with httpx.AsyncClient(timeout=30) as client:
                # 获取模型名
                models_resp = await client.get(f"{qwen_url}/models")
                model_name = "default"
                if models_resp.status_code == 200:
                    models = models_resp.json().get("data", [])
                    if models:
                        model_name = models[0]["id"]
                
                resp = await client.post(
                    f"{qwen_url}/chat/completions",
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 300
                    }
                )
                
                if resp.status_code != 200:
                    logger.error(f"Digest generation failed: {resp.status_code}")
                    return None
                    
                content = resp.json()["choices"][0]["message"]["content"]
                
                # 解析 JSON
                if "```" in content:
                    import re
                    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
                    if match:
                        content = match.group(1)
                
                content = content.strip()
                if not content.startswith("{"):
                    start = content.find("{")
                    if start >= 0:
                        content = content[start:]
                
                data = json.loads(content)
                
                if data.get("skip"):
                    return None
                    
                # 保存摘要
                return await self.save_digest(
                    user_id=user_id,
                    session_id=session_id,
                    title=data.get("title", "对话")[:10],
                    key_points=data.get("key_points", [])[:3]
                )
                
        except Exception as e:
            logger.error(f"Digest generation error: {e}")
            return None

    async def save_digest(
        self,
        user_id: str,
        session_id: str,
        title: str,
        key_points: List[str]
    ) -> Dict[str, Any]:
        """
        保存对话摘要

        Args:
            user_id: 用户ID
            session_id: 会话ID
            title: 标题 (10字以内)
            key_points: 关键点 (最多3条)

        Returns:
            摘要文档
        """
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

    # ==================== 上下文构建 ====================

    async def build_context(self, user_id: str) -> str:
        """
        构建记忆上下文块（用于 System Prompt 注入）

        Args:
            user_id: 用户ID

        Returns:
            格式化的上下文文本
        """
        # 获取显式记忆
        memories = await self.get_all(user_id)

        # 获取最近摘要
        digests = await self.get_recent_digests(user_id, limit=10)

        lines = []

        # 用户记忆
        if memories:
            lines.append("【用户记忆】")
            for m in memories:
                lines.append(f"- {m['key']}: {m['value']}")

        # 最近对话
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
