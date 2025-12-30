"""
Vulcan Brain - 认知上下文服务 v4.0
分层记忆注入：Core (总是) / Contextual (相关时) / Background (不注入)

架构:
- L0 宪法层: 核心价值观 (YAML 配置)
- L1 灵魂层: 人格参数 (MongoDB user_souls)
- L2 记忆层: 用户记忆 - 分层注入 (MongoDB user_memories)
- L3 知识层: 企业知识 (按需查询，不在此服务)
- L4 工作层: 当前对话 (由 chat_router 管理)
"""

import logging
import os
import yaml
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger("CognitiveContext")


class CognitiveContextService:
    """认知上下文服务 - 构建 AI 的完整认知背景"""

    def __init__(self, db, constitution_path: str = None):
        self.db = db
        self.user_memories = db.user_memories
        self.user_souls = db.user_souls
        self.digests = db.conversation_digests

        self.constitution_path = constitution_path or os.path.join(
            os.path.dirname(__file__),
            "../core/soul/prompts/boss_constitution.yaml"
        )
        self._constitution_cache = None

    # ==================== L0: 宪法层 ====================

    def get_constitution(self) -> Dict[str, Any]:
        """获取宪法配置 (L0层, 只读)"""
        if self._constitution_cache:
            return self._constitution_cache

        try:
            if os.path.exists(self.constitution_path):
                with open(self.constitution_path, "r", encoding="utf-8") as f:
                    self._constitution_cache = yaml.safe_load(f)
                    return self._constitution_cache
        except Exception as e:
            logger.warning(f"Failed to load constitution: {e}")

        return {
            "core_values": ["诚实", "专业", "高效"],
            "red_lines": ["不泄露敏感信息", "不做出承诺"],
            "tone": "专业但友好"
        }

    def format_constitution(self) -> str:
        """格式化宪法为 Prompt 块"""
        const = self.get_constitution()

        lines = ["【核心价值观 - 不可违背】"]

        core_values = const.get("core_values", [])
        if core_values:
            if isinstance(core_values[0], dict):
                names = [v.get("name", "") for v in core_values if isinstance(v, dict)]
                lines.append("核心价值: " + ", ".join(names))
            else:
                lines.append("核心价值: " + ", ".join(str(v) for v in core_values))

        red_lines = const.get("red_lines") or const.get("prohibited_actions", [])
        if red_lines:
            if isinstance(red_lines[0], dict):
                items = [r.get("name", str(r)) for r in red_lines if r]
            else:
                items = [str(r) for r in red_lines]
            lines.append("红线: " + "; ".join(items[:5]))

        tone = const.get("tone") or const.get("communication_style", {}).get("tone", "")
        if tone:
            lines.append(f"语气: {tone}")

        return "\n".join(lines)

    # ==================== L1: 灵魂层 ====================

    async def get_soul(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户灵魂配置 (L1层)"""
        soul = await self.user_souls.find_one({"user_id": user_id})
        if soul:
            soul["_id"] = str(soul["_id"])
        return soul

    async def format_soul(self, user_id: str) -> str:
        """格式化灵魂为 Prompt 块"""
        soul = await self.get_soul(user_id)

        if not soul:
            return ""

        lines = ["【人格特质】"]

        genome = soul.get("genome", {})
        if genome:
            dims = [
                ("risk_tolerance", "风险偏好"),
                ("time_horizon", "时间视野"),
                ("strategic_driver", "战略驱动"),
                ("interpersonal_style", "人际风格"),
                ("decision_style", "决策风格"),
                ("information_preference", "信息偏好")
            ]
            for key, label in dims:
                if key in genome:
                    lines.append(f"- {label}: {genome[key]}")

        return "\n".join(lines) if len(lines) > 1 else ""

    # ==================== L2: 记忆层 (分层) ====================

    async def get_memories(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户记忆 (L2层)"""
        cursor = self.user_memories.find({"user_id": user_id})
        results = await cursor.to_list(length=100)

        for r in results:
            r["_id"] = str(r["_id"])

        return results

    def _check_relevance(self, message: str, tags: List[str]) -> bool:
        """检查消息是否与标签相关"""
        if not tags or not message:
            return False

        message_lower = message.lower()
        for tag in tags:
            if tag.lower() in message_lower:
                return True
        return False

    async def format_memories(self, user_id: str, current_message: str = "") -> str:
        """
        格式化记忆为 Prompt 块 (分层注入)

        Args:
            user_id: 用户ID
            current_message: 当前用户消息，用于判断 contextual 记忆是否相关
        """
        memories = await self.get_memories(user_id)

        if not memories:
            return ""

        # 分层筛选
        core_memories = []
        contextual_memories = []

        for m in memories:
            tier = m.get("tier", "contextual")  # 兼容旧数据，默认为 contextual

            if tier == "core":
                # 核心记忆：总是注入
                core_memories.append(m)
            elif tier == "contextual":
                # 情境记忆：只有当前消息与 relevance_tags 匹配时才注入
                tags = m.get("relevance_tags", [])
                if current_message and self._check_relevance(current_message, tags):
                    contextual_memories.append(m)
                elif not current_message:
                    # 如果没有提供当前消息，回退到旧逻辑（注入所有）
                    contextual_memories.append(m)
            # background 记忆不注入

        lines = []

        # 核心记忆
        if core_memories:
            lines.append("【用户核心信息】")
            for m in core_memories:
                lines.append(f"- {m['key']}: {m['value']}")

        # 相关的情境记忆
        if contextual_memories:
            lines.append("\n【相关背景】" if core_memories else "【相关背景】")
            for m in contextual_memories:
                lines.append(f"- {m['key']}: {m['value']}")

        return "\n".join(lines) if lines else ""

    # ==================== 对话摘要 ====================

    async def get_recent_digests(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近对话摘要"""
        cursor = self.digests.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit)

        results = await cursor.to_list(length=limit)

        for r in results:
            r["_id"] = str(r["_id"])

        return results

    async def format_digests(self, user_id: str) -> str:
        """格式化对话摘要为 Prompt 块"""
        digests = await self.get_recent_digests(user_id, limit=5)  # 减少到5条

        if not digests:
            return ""

        lines = ["【最近话题】"]

        for d in digests:
            title = d.get("title", "对话")
            lines.append(f"- {title}")

        return "\n".join(lines)

    # ==================== 完整上下文 ====================

    async def build_full_context(self, user_id: str, current_message: str = "") -> str:
        """
        构建完整的认知上下文 (L0 + L1 + L2)

        Args:
            user_id: 用户ID
            current_message: 当前用户消息，用于分层记忆注入

        Returns:
            格式化的上下文文本
        """
        sections = []

        # L0: 宪法 (所有用户相同)
        constitution = self.format_constitution()
        if constitution:
            sections.append(constitution)

        # L1: 灵魂 (用户个性化)
        soul = await self.format_soul(user_id)
        if soul:
            sections.append(soul)

        # L2: 记忆 (分层注入)
        memories = await self.format_memories(user_id, current_message)
        if memories:
            sections.append(memories)

        # 对话摘要 (精简版)
        digests = await self.format_digests(user_id)
        if digests:
            sections.append(digests)

        if not sections:
            return ""

        return "\n\n".join(sections)

    async def get_context_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户认知上下文统计"""
        memories = await self.get_memories(user_id)
        digests = await self.get_recent_digests(user_id)
        soul = await self.get_soul(user_id)

        # 统计分层信息
        tier_stats = {"core": 0, "contextual": 0, "background": 0}
        for m in memories:
            tier = m.get("tier", "contextual")
            tier_stats[tier] = tier_stats.get(tier, 0) + 1

        return {
            "user_id": user_id,
            "has_constitution": True,
            "has_soul": soul is not None,
            "memory_count": len(memories),
            "memory_by_tier": tier_stats,
            "memory_by_category": {
                "identity": len([m for m in memories if m.get("category") == "identity"]),
                "preference": len([m for m in memories if m.get("category") == "preference"]),
                "fact": len([m for m in memories if m.get("category") == "fact"])
            },
            "digest_count": len(digests)
        }


# ==================== 单例访问 ====================

_cognitive_service: Optional[CognitiveContextService] = None


def get_cognitive_context_service(db=None) -> CognitiveContextService:
    """获取 CognitiveContextService 单例"""
    global _cognitive_service
    if _cognitive_service is None:
        if db is None:
            from vulcan_libs.store import store
            db = store.db
        _cognitive_service = CognitiveContextService(db)
    return _cognitive_service


# ==================== 函数式接口 (兼容现有代码) ====================

async def build_cognitive_context(
    user_id: str,
    task_type: str = "chat",
    current_message: str = ""
) -> str:
    """
    构建认知上下文 (函数式接口)

    Args:
        user_id: 用户ID
        task_type: 任务类型 (暂未使用)
        current_message: 当前用户消息，用于分层记忆注入

    Returns:
        格式化的上下文文本
    """
    service = get_cognitive_context_service()
    return await service.build_full_context(user_id, current_message)
