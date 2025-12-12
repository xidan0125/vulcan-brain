"""
聊天维度数据模型
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from .common import AIAnalysis


class ChatAIAnalysis(AIAnalysis):
    """聊天 AI 分析"""
    decisions: List[str] = []
    topics: List[str] = []
    activity_level: str = "medium"  # low/medium/high


class ChatSummary(BaseModel):
    """单个群聊汇总"""
    chat_id: str
    chat_name: str
    message_count: int = 0
    analysis: ChatAIAnalysis = ChatAIAnalysis()


class ChatDimensionData(BaseModel):
    """聊天维度数据"""
    total_chats: int = 0
    total_messages: int = 0
    total_decisions: int = 0
    total_action_items: int = 0
    total_risks: int = 0
    summaries: List[ChatSummary] = []


class ChatMessage(BaseModel):
    """聊天消息"""
    message_id: str
    content: str
    sender: dict  # {open_id, name, sender_type}
    timestamp: str


class ChatDetail(BaseModel):
    """群聊详情"""
    chat_id: str
    chat_name: str
    total_messages: int = 0
    history: List[dict] = []  # 历史汇总
