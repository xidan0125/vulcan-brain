"""
消息处理器
处理飞书消息事件，包括AI对话
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger("FeishuMessageHandler")

# 对话历史缓存 (chat_id -> messages list)
_chat_history: Dict[str, List[Dict]] = defaultdict(list)
MAX_HISTORY = 10  # 保留最近10轮对话

# 消息去重缓存
_seen_msg_ids: Dict[str, datetime] = {}
MSG_DEDUP_SECONDS = 60


def is_dup(msg_id: str) -> bool:
    """检查消息是否重复"""
    now = datetime.now()

    # 清理过期缓存
    expired = [k for k, v in _seen_msg_ids.items()
               if (now - v).total_seconds() > MSG_DEDUP_SECONDS]
    for k in expired:
        del _seen_msg_ids[k]

    if msg_id in _seen_msg_ids:
        return True

    _seen_msg_ids[msg_id] = now
    return False


class MessageHandler:
    """消息处理器"""

    def __init__(self):
        self._sdk = None
        self._ai = None

    @property
    def sdk(self):
        if self._sdk is None:
            from feishu.sdk import get_feishu_sdk
            self._sdk = get_feishu_sdk()
        return self._sdk

    @property
    def ai(self):
        if self._ai is None:
            from vulcan_libs.ai_service import get_ai_service
            self._ai = get_ai_service()
        return self._ai

    async def handle_text_message(self, event: Dict, bot: str = "brain") -> Dict:
        """
        处理文本消息 - AI对话

        Args:
            event: 事件数据
            bot: 机器人类型
        """
        msg = event.get("message", {})
        msg_id = msg.get("message_id", "")
        chat_id = msg.get("chat_id", "")
        chat_type = msg.get("chat_type", "")  # p2p私聊 / group群聊

        # 去重
        if is_dup(msg_id):
            return {"code": 0}

        # 解析消息内容
        msg_content = msg.get("content", "{}")
        try:
            text = json.loads(msg_content).get("text", "")
        except:
            text = msg_content

        sender = event.get("sender", {})
        open_id = sender.get("sender_id", {}).get("open_id", "")

        logger.info(f"[Message] 用户消息: {text[:50]}..., chat_id={chat_id}, from={open_id}")

        # ===== 审批命令拦截 =====
        if text in ["发起审批", "/审批", "审批", "/approval"]:
            return await self._handle_approval_command(chat_id, bot)

        # ===== 群聊@检测: 只有被@才回复 =====
        if chat_type == "group":
            if not self._is_mentioned(msg):
                logger.info(f"[Message] 群聊消息未@机器人，跳过")
                return {"code": 0}

        # ===== AI 对话 =====
        reply_text = await self._chat_with_ai(chat_id, text)

        # ===== 发送回复 =====
        if chat_type == "group":
            await self.sdk.reply_message(msg_id, reply_text, bot=bot)
        else:
            await self.sdk.send_text(open_id, reply_text, bot=bot)

        return {"code": 0}

    def _is_mentioned(self, msg: Dict) -> bool:
        """检查消息是否@了机器人"""
        mentions = msg.get("mentions", [])
        for m in mentions:
            if m.get("key") == "@_all":
                return True
            m_id = m.get("id", {})
            if isinstance(m_id, dict) and m_id.get("open_id"):
                return True
            if m.get("key", "").startswith("@_user_"):
                return True
        return False

    async def _handle_approval_command(self, chat_id: str, bot: str) -> Dict:
        """处理审批命令"""
        logger.info("[Message] 识别到审批命令，发送审批表单卡片")

        try:
            from feishu.cards.approval_cards import build_approval_form_card
            card = build_approval_form_card()
            await self.sdk.send_card_to_chat(chat_id, card, bot=bot)
        except Exception as e:
            logger.error(f"[Message] 发送审批卡片失败: {e}")

        return {"code": 0}

    async def _chat_with_ai(self, chat_id: str, text: str) -> str:
        """
        AI 对话 (支持多轮上下文)

        Args:
            chat_id: 会话ID
            text: 用户输入

        Returns:
            AI 回复
        """
        # 获取对话历史
        history = _chat_history[chat_id]

        # 添加当前用户消息
        history.append({"role": "user", "content": text})

        # 只保留最近的历史
        if len(history) > MAX_HISTORY * 2:
            _chat_history[chat_id] = history[-MAX_HISTORY:]
            history = _chat_history[chat_id]

        # 构建消息列表
        messages = [{"role": h["role"], "content": h["content"]}
                    for h in history[-MAX_HISTORY:]]

        # 调用 AI 服务
        try:
            reply_text = await self.ai.chat(messages)

            if len(reply_text) > 4000:
                reply_text = reply_text[:4000] + "...(截断)"

            # 保存 AI 回复到历史
            history.append({"role": "assistant", "content": reply_text})

            return reply_text

        except Exception as e:
            logger.error(f"[Message] AI调用失败: {e}")
            return f"AI处理出错: {str(e)[:100]}"

    async def clear_history(self, chat_id: str) -> None:
        """清除对话历史"""
        if chat_id in _chat_history:
            del _chat_history[chat_id]
            logger.info(f"[Message] 已清除对话历史: {chat_id}")


# ==================== 单例 ====================

_handler_instance = None


def get_message_handler() -> MessageHandler:
    """获取消息处理器单例"""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = MessageHandler()
    return _handler_instance
