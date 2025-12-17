"""
Vulcan Nexus - Session Context Manager
会话上下文管理，支持滑动窗口和自动压缩
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum


class AgentType(str, Enum):
    """Agent 类型"""
    CONVERSATIONAL = "conversational"  # 对话型: 共享历史
    TASK = "task"                       # 任务型: Briefcase 隔离


@dataclass
class Message:
    """会话消息"""
    role: str           # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    token_count: int = 0
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {"role": self.role, "content": self.content}


class SessionContext:
    """
    会话上下文管理
    
    策略:
    - 对话型 Agent: 共享完整历史，滑动窗口
    - 任务型 Agent: 只提供 Briefcase 上下文
    """
    
    def __init__(
        self,
        max_tokens: int = 8000,
        summary_threshold: int = 6000,
        max_messages: int = 40
    ):
        self.max_tokens = max_tokens
        self.summary_threshold = summary_threshold
        self.max_messages = max_messages
        
        self.messages: List[Message] = []
        self.session_summary: str = ""
        self.total_tokens: int = 0
        
        # 最近的 Agent 执行记录
        self.recent_agents: List[str] = []
        
    def add_message(
        self, 
        role: str, 
        content: str, 
        token_count: int = 0,
        **metadata
    ) -> None:
        """添加消息"""
        if token_count == 0:
            # 简单估算: 中文约 2 token/字, 英文约 1 token/4字符
            token_count = len(content) // 2 + len(content.encode('ascii', errors='ignore')) // 4
        
        msg = Message(
            role=role,
            content=content,
            token_count=token_count,
            metadata=metadata
        )
        
        self.messages.append(msg)
        self.total_tokens += token_count
        
        # 检查是否需要压缩
        if self.total_tokens > self.summary_threshold or len(self.messages) > self.max_messages:
            self._compress_history()
    
    def _compress_history(self) -> None:
        """压缩历史记录"""
        keep_recent = 6  # 保留最近 3 轮 (6 条消息)
        
        if len(self.messages) <= keep_recent:
            return
        
        # 要压缩的消息
        to_compress = self.messages[:-keep_recent]
        
        # 生成摘要 (规则方式)
        summary_parts = []
        for msg in to_compress:
            if msg.role == "user":
                # 截取用户消息关键词
                keywords = self._extract_keywords(msg.content)
                if keywords:
                    summary_parts.append(f"用户询问: {keywords}")
            elif msg.role == "assistant":
                # 检测是否是任务完成
                if msg.metadata.get("is_task_result"):
                    agent = msg.metadata.get("agent_type", "")
                    summary_parts.append(f"[{agent}] {msg.content[:50]}")
                elif "完成" in msg.content or "已" in msg.content:
                    summary_parts.append("助手完成了任务")
        
        # 更新摘要
        new_summary = " | ".join(summary_parts[-5:])
        if self.session_summary:
            self.session_summary = f"{self.session_summary} | {new_summary}"
        else:
            self.session_summary = new_summary
        
        # 截断摘要
        if len(self.session_summary) > 500:
            self.session_summary = "..." + self.session_summary[-500:]
        
        # 保留最近消息
        self.messages = self.messages[-keep_recent:]
        self.total_tokens = sum(m.token_count for m in self.messages)
    
    def _extract_keywords(self, text: str, max_length: int = 50) -> str:
        """提取关键词"""
        # 简单截取，去掉常见词
        text = text.strip()
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
    
    def get_messages_for_llm(self, include_summary: bool = True) -> List[Dict]:
        """获取发送给 LLM 的消息列表 (对话型 Agent 用)"""
        result = []
        
        # 添加摘要到 system message
        if include_summary and self.session_summary:
            result.append({
                "role": "system",
                "content": f"[对话历史摘要]\n{self.session_summary}\n[/对话历史摘要]"
            })
        
        # 添加最近消息
        for msg in self.messages:
            result.append(msg.to_dict())
        
        return result
    
    def get_briefcase_context(self) -> str:
        """获取用于 Briefcase 的上下文快照 (任务型 Agent 用)"""
        parts = []
        
        if self.session_summary:
            parts.append(f"历史摘要: {self.session_summary}")
        
        # 最近 2 轮对话
        recent_turns = []
        for msg in self.messages[-4:]:
            if msg.role == "user":
                recent_turns.append(f"用户: {msg.content[:100]}")
            elif msg.role == "assistant":
                recent_turns.append(f"助手: {msg.content[:100]}")
        
        if recent_turns:
            parts.append("最近对话:\n" + "\n".join(recent_turns))
        
        return "\n\n".join(parts)
    
    def record_agent_execution(self, agent_id: str) -> None:
        """记录 Agent 执行"""
        self.recent_agents.append(agent_id)
        if len(self.recent_agents) > 10:
            self.recent_agents = self.recent_agents[-10:]
    
    def clear(self) -> None:
        """清空会话"""
        self.messages = []
        self.session_summary = ""
        self.total_tokens = 0
        self.recent_agents = []
