"""
Vulcan Nexus - Briefcase Protocol
Agent 间信息传递协议，防止上下文污染和 Sticky Tool
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ArtifactType(str, Enum):
    """工件类型"""
    MESSAGE_SENT = "message_sent"
    DATA_RESULT = "data_result"
    FILE = "file"
    ERROR = "error"
    QUERY_RESULT = "query_result"


@dataclass
class Artifact:
    """任务产出的工件"""
    type: ArtifactType
    content: Any
    metadata: Dict = field(default_factory=dict)
    
    def to_summary(self, max_length: int = 100) -> str:
        """生成工件摘要"""
        content_str = str(self.content)[:max_length]
        return f"[{self.type.value}] {content_str}"


@dataclass
class Briefcase:
    """
    Agent 间的信息传递协议
    
    原则:
    1. 任务型 Agent 不接收对话历史
    2. 只传递 {指令, 摘要, 工件}
    3. 防止 Sticky Tool 和上下文污染
    """
    
    # 输入 (from orchestrator)
    task_instruction: str           # 简洁的任务指令
    context_snapshot: str           # 压缩的上下文摘要 (会话背景)
    input_artifacts: List[Artifact] = field(default_factory=list)
    
    # 输出 (from agent)
    final_answer: Optional[str] = None
    output_artifacts: List[Artifact] = field(default_factory=list)
    execution_summary: Optional[str] = None
    
    # 元数据
    agent_id: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    token_usage: Dict = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None
    
    def to_handoff_context(self, max_length: int = 500) -> str:
        """生成交接给下一个 Agent 的上下文"""
        parts = []
        
        if self.execution_summary:
            parts.append(f"上一步: {self.execution_summary[:max_length]}")
        
        if self.output_artifacts:
            artifact_lines = []
            for art in self.output_artifacts[:3]:
                artifact_lines.append(f"  - {art.to_summary()}")
            parts.append("产出:\n" + "\n".join(artifact_lines))
        
        return "\n".join(parts)
    
    def build_agent_input(self) -> str:
        """构建发给 Agent 的输入消息"""
        parts = [f"任务: {self.task_instruction}"]
        
        if self.context_snapshot:
            parts.append(f"\n背景: {self.context_snapshot}")
        
        if self.input_artifacts:
            artifact_lines = []
            for art in self.input_artifacts:
                artifact_lines.append(f"  - {art.to_summary()}")
            parts.append("\n可用数据:\n" + "\n".join(artifact_lines))
        
        return "\n".join(parts)


class BriefcaseManager:
    """管理 Briefcase 的创建和传递"""
    
    def __init__(self, summary_max_tokens: int = 200):
        self.summary_max_tokens = summary_max_tokens
        self.history: List[Briefcase] = []
    
    def create(
        self,
        task: str,
        session_summary: str,
        previous_briefcase: Optional[Briefcase] = None
    ) -> Briefcase:
        """为任务型 Agent 创建 Briefcase"""
        
        context_parts = []
        
        if session_summary:
            context_parts.append(f"会话背景: {session_summary}")
        
        if previous_briefcase:
            context_parts.append(previous_briefcase.to_handoff_context())
        
        return Briefcase(
            task_instruction=task,
            context_snapshot="\n".join(context_parts),
            input_artifacts=previous_briefcase.output_artifacts if previous_briefcase else []
        )
    
    def finalize(
        self,
        briefcase: Briefcase,
        final_answer: str,
        artifacts: List[Artifact],
        agent_id: str = ""
    ) -> Briefcase:
        """Agent 完成后封装 Briefcase"""
        
        summary = self._generate_summary(final_answer, artifacts)
        
        briefcase.final_answer = final_answer
        briefcase.output_artifacts = artifacts
        briefcase.execution_summary = summary
        briefcase.completed_at = datetime.now()
        briefcase.agent_id = agent_id
        
        self.history.append(briefcase)
        return briefcase
    
    def _generate_summary(self, answer: str, artifacts: List[Artifact]) -> str:
        """生成执行摘要 (规则方式，无 LLM 调用)"""
        
        actions = []
        for art in artifacts:
            if art.type == ArtifactType.MESSAGE_SENT:
                target = art.metadata.get("target", "未知")
                actions.append(f"已发送消息到 {target}")
            elif art.type == ArtifactType.DATA_RESULT:
                rows = art.metadata.get("rows", "?")
                actions.append(f"获取了 {rows} 条数据")
            elif art.type == ArtifactType.FILE:
                filename = art.metadata.get("filename", "文件")
                actions.append(f"生成了 {filename}")
            elif art.type == ArtifactType.ERROR:
                actions.append(f"执行出错")
        
        if actions:
            return "; ".join(actions)
        else:
            # 截取回答开头
            return answer[:100] + ("..." if len(answer) > 100 else "")
    
    def get_recent_summaries(self, n: int = 5) -> str:
        """获取最近 n 个任务的摘要"""
        recent = self.history[-n:]
        lines = []
        for b in recent:
            if b.execution_summary:
                lines.append(f"- [{b.agent_id}] {b.execution_summary}")
        return "\n".join(lines)
