"""
Vulcan Brain - Remember Tool
记忆存储工具

v2: 重写为新架构，支持待确认记忆
"""

import json
import asyncio
from typing import Optional
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool


class RememberInput(BaseModel):
    """记忆存储参数"""
    key: str = Field(
        ...,
        description="记忆键，如 user_name, favorite_color, project_name"
    )
    value: str = Field(
        ...,
        description="要记住的内容"
    )
    category: str = Field(
        default="fact",
        description="分类: identity(身份) / preference(偏好) / fact(事实)"
    )


@register_tool
class RememberTool(BaseTool):
    """
    记住重要信息
    
    当用户说记住xxx、我叫xxx、我喜欢xxx等需要保存信息时使用。
    信息会先存入待确认队列，用户确认后才正式保存。
    
    示例:
    - {"key": "user_name", "value": "张三", "category": "identity"}
    - {"key": "favorite_color", "value": "蓝色", "category": "preference"}
    """
    
    name = "remember"
    description = "记住重要信息到长期记忆。当用户说'记住xxx'、'我叫xxx'、'我喜欢xxx'时使用。"
    args_schema = RememberInput
    domain = ToolDomain.MEMORY
    is_destructive = False
    is_idempotent = False  # 每次调用会创建新的 pending 记忆
    
    def run(self, params: RememberInput, context: ToolContext) -> ToolResult:
        """同步执行"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.arun(params, context))
    
    async def arun(self, params: RememberInput, context: ToolContext) -> ToolResult:
        """异步执行"""
        from services.memory_service import get_memory_service
        
        user_id = context.user_id
        session_id = context.session_id or "default_session"
        
        try:
            svc = get_memory_service()
            pending = await svc.add_pending(
                user_id=user_id,
                session_id=session_id,
                key=params.key,
                value=params.value,
                category=params.category,
                confidence=0.95,  # 工具调用置信度高
                context=f"Tool call: remember({params.key}, {params.value})"
            )
            
            # 返回 JSON 结构，前端可据此显示确认卡片
            return ToolResult.ok({
                "type": "pending_memory",
                "pending_id": str(pending.get("id") or pending.get("_id", "")),
                "key": params.key,
                "value": params.value,
                "category": params.category,
                "message": f"已添加待确认记忆: {params.key} = {params.value}"
            })
            
        except Exception as e:
            return ToolResult.fail(f"记忆保存失败: {e}")
