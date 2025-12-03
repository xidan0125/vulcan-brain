"""
聊天 AI 汇总服务 - 五纬度信息收集系统 (维度1)

功能:
1. 按群聊分析消息内容
2. 提取关键信息: 决策、待办、风险、话题
3. 生成日报摘要 + 详情数据

重构: 使用统一AI服务层 (ai_service.py)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from services.message_store import get_message_store
from vulcan_libs.ai_service import get_ai_service, analyze_chat

logger = logging.getLogger("ChatSummarizer")


class ChatSummarizer:
    """聊天消息 AI 汇总器"""

    def __init__(self):
        self.store = get_message_store()
        self.ai = get_ai_service()

    async def summarize_chat(
        self,
        chat_id: str,
        chat_name: str,
        date: datetime,
        messages: List[Dict]
    ) -> Dict[str, Any]:
        """
        分析单个群聊的消息

        Args:
            chat_id: 群聊ID
            chat_name: 群聊名称
            date: 日期
            messages: 消息列表

        Returns:
            汇总结果
        """
        if not messages:
            return self._empty_summary(chat_id, chat_name, date)

        try:
            # 使用统一AI服务的聊天分析
            analysis = await self.ai.analyze_chat(
                messages=messages,
                chat_name=chat_name,
                date=date.strftime("%Y-%m-%d")
            )

            return {
                "chat_id": chat_id,
                "chat_name": chat_name,
                "date": date.strftime("%Y-%m-%d"),
                "msg_count": len(messages),
                "analysis": analysis,
                "generated_at": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"AI 分析失败: {e}")
            return self._empty_summary(chat_id, chat_name, date, error=str(e))

    async def summarize_all_chats(self, date: datetime = None) -> Dict[str, Any]:
        """
        汇总所有群聊的消息

        Args:
            date: 日期 (默认昨天)

        Returns:
            所有群聊的汇总
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)

        # 设置时间范围 (当天 00:00 - 23:59)
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = date.replace(hour=23, minute=59, second=59, microsecond=999999)

        # 获取所有群聊统计
        stats = await self.store.get_stats()

        results = {
            "date": date.strftime("%Y-%m-%d"),
            "generated_at": datetime.now().isoformat(),
            "chats": [],
            "totals": {
                "total_messages": 0,
                "total_decisions": 0,
                "total_action_items": 0,
                "total_risks": 0
            }
        }

        # 遍历每个群聊
        for stat in stats:
            chat_id = stat.get("_id")
            if not chat_id:
                continue

            # 获取该群当天的消息
            messages = await self.store.get_chat_history(
                chat_id=chat_id,
                limit=500,
                since=start,
                until=end
            )

            if not messages:
                continue

            # 获取群名 (从消息中提取或使用 ID)
            chat_name = self._get_chat_name(chat_id, messages)

            # 分析该群聊
            summary = await self.summarize_chat(chat_id, chat_name, date, messages)
            results["chats"].append(summary)

            # 累加统计
            analysis = summary.get("analysis", {})
            results["totals"]["total_messages"] += summary.get("msg_count", 0)
            results["totals"]["total_decisions"] += len(analysis.get("decisions", []))
            results["totals"]["total_action_items"] += len(analysis.get("action_items", []))
            results["totals"]["total_risks"] += len(analysis.get("risks", []))

        return results

    def _empty_summary(
        self,
        chat_id: str,
        chat_name: str,
        date: datetime,
        error: str = None
    ) -> Dict:
        """返回空的汇总结果"""
        return {
            "chat_id": chat_id,
            "chat_name": chat_name,
            "date": date.strftime("%Y-%m-%d"),
            "msg_count": 0,
            "analysis": {
                "decisions": [],
                "action_items": [],
                "risks": [],
                "topics": [],
                "summary": "今日无消息" if not error else f"分析失败: {error}",
                "activity_level": "low",
                "sentiment": "neutral"
            },
            "generated_at": datetime.now().isoformat()
        }

    def _get_chat_name(self, chat_id: str, messages: List[Dict]) -> str:
        """获取群聊名称 (TODO: 从飞书 API 获取)"""
        # 暂时使用 chat_id 后8位
        return f"群聊_{chat_id[-8:]}"


# ===== 便捷函数 =====

_summarizer = None

def get_chat_summarizer() -> ChatSummarizer:
    """获取汇总器实例"""
    global _summarizer
    if _summarizer is None:
        _summarizer = ChatSummarizer()
    return _summarizer


async def generate_chat_summary(date: datetime = None) -> Dict:
    """生成聊天汇总 (便捷函数)"""
    summarizer = get_chat_summarizer()
    return await summarizer.summarize_all_chats(date)
