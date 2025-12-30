"""
AgentContext - 请求级上下文 DTO
所有状态通过此对象传递给 Orchestrator，实现请求隔离
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class AgentContext(BaseModel):
    """Agent 执行上下文 - 请求级数据传输对象"""
    
    # 会话信息
    session_id: str
    user_id: str
    
    # 消息历史 (从数据库加载)
    history: List[Dict[str, Any]]
    
    # 用户记忆 (注入的上下文)
    user_memory: Optional[str] = None
    
    # 当前用户输入
    user_input: str
    
    # 可用工具列表
    available_tools: List[str] = []
    
    # 模型配置
    temperature: float = 0.7
    max_tokens: int = 4096
    
    class Config:
        """Pydantic 配置"""
        extra = "allow"  # 允许额外字段
