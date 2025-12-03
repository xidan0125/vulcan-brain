"""
实时分析处理器 - 采集时自动触发AI分析

功能:
1. 监听消息保存事件
2. 达到阈值时触发分析
3. 将结果保存到chat_summaries

重构: 使用统一AI服务层 (ai_service.py)
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Optional

from services.message_store import get_message_store
from services.chat_summary_store import get_chat_summary_store
from vulcan_libs.ai_service import get_ai_service

logger = logging.getLogger("RealtimeAnalyzer")

# 分析触发阈值
ANALYSIS_THRESHOLD = 20  # 累积20条新消息触发分析
ANALYSIS_COOLDOWN = 300  # 同一群聊分析冷却时间(秒)


class RealtimeAnalyzer:
    """实时分析处理器"""

    def __init__(self):
        self.msg_store = get_message_store()
        self.summary_store = get_chat_summary_store()
        self.ai = get_ai_service()
        self._last_analysis: Dict[str, datetime] = {}  # chat_id -> 上次分析时间
        self._pending_counts: Dict[str, int] = {}  # chat_id -> 待分析消息数

    async def on_message_saved(self, chat_id: str, date: str = None):
        """
        消息保存后的回调 - 判断是否需要触发分析

        Args:
            chat_id: 群聊ID
            date: 日期
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # 累计计数
        key = f"{chat_id}:{date}"
        self._pending_counts[key] = self._pending_counts.get(key, 0) + 1

        # 检查是否达到阈值
        if self._pending_counts[key] >= ANALYSIS_THRESHOLD:
            # 检查冷却时间
            last = self._last_analysis.get(key)
            if last and (datetime.now() - last).seconds < ANALYSIS_COOLDOWN:
                logger.debug(f"[RealtimeAnalyzer] {chat_id} in cooldown, skip")
                return

            # 触发分析
            logger.info(f"[RealtimeAnalyzer] Triggering analysis for {chat_id}")
            asyncio.create_task(self.analyze_chat(chat_id, date))

            # 重置计数和记录时间
            self._pending_counts[key] = 0
            self._last_analysis[key] = datetime.now()

    async def analyze_chat(self, chat_id: str, date: str = None) -> Optional[Dict]:
        """
        分析指定群聊

        Args:
            chat_id: 群聊ID
            date: 日期 (YYYY-MM-DD)

        Returns:
            分析结果
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"[RealtimeAnalyzer] Analyzing chat {chat_id} for {date}")

        try:
            # 1. 获取当天消息
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            start = date_obj.replace(hour=0, minute=0, second=0)
            end = date_obj.replace(hour=23, minute=59, second=59)

            messages = await self.msg_store.get_chat_history(
                chat_id=chat_id,
                limit=500,
                since=start,
                until=end
            )

            if not messages:
                logger.info(f"[RealtimeAnalyzer] No messages for {chat_id} on {date}")
                return None

            # 2. 获取群聊元数据
            metadata = await self.summary_store.get_chat_metadata(chat_id)
            chat_name = metadata.get("chat_name", f"群聊_{chat_id[-8:]}") if metadata else f"群聊_{chat_id[-8:]}"

            # 3. 调用AI分析（使用统一服务）
            analysis = await self.ai.analyze_chat(
                messages=messages,
                chat_name=chat_name,
                date=date
            )

            if not analysis:
                logger.warning(f"[RealtimeAnalyzer] AI analysis returned empty for {chat_id}")
                return None

            # 4. 保存分析结果
            summary = {
                "chat_id": chat_id,
                "chat_name": chat_name,
                "date": date,
                "message_count": len(messages),
                **analysis,
                "analyzed_at": datetime.now().isoformat()
            }

            await self.summary_store.save_summary(chat_id, date, summary, len(messages))
            logger.info(f"[RealtimeAnalyzer] Analysis saved for {chat_id}: {analysis.get('summary', '')[:50]}...")

            # 5. 更新元数据
            await self.summary_store.upsert_chat_metadata(
                chat_id=chat_id,
                data={
                    'chat_name': chat_name,
                    'last_analyzed': datetime.now()
                }
            )

            return summary

        except Exception as e:
            logger.error(f"[RealtimeAnalyzer] Analysis failed for {chat_id}: {e}")
            import traceback
            traceback.print_exc()
            return None


# ===== 全局实例 =====
_analyzer = None

def get_realtime_analyzer() -> RealtimeAnalyzer:
    """获取分析器实例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = RealtimeAnalyzer()
    return _analyzer


async def trigger_chat_analysis(chat_id: str, date: str = None):
    """手动触发分析（便捷函数）"""
    analyzer = get_realtime_analyzer()
    return await analyzer.analyze_chat(chat_id, date)
