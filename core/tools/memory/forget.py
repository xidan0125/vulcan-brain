"""
Vulcan Brain - Forget Tool
记忆删除工具

v2: 重写为新架构
"""

import asyncio
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool


class ForgetInput(BaseModel):
    """记忆删除参数"""
    key: str = Field(
        ...,
        description="要删除的记忆键"
    )


@register_tool
class ForgetTool(BaseTool):
    """
    忘记某条记忆
    
    当用户说忘了xxx、删除xxx等需要删除记忆时使用。
    仅删除已确认的记忆。
    
    示例:
    - {"key": "user_name"}
    """
    
    name = "forget"
    description = "忘记某条记忆。当用户说'忘了xxx'、'删除xxx'时使用。"
    args_schema = ForgetInput
    domain = ToolDomain.MEMORY
    is_destructive = True  # 删除是破坏性操作
    is_idempotent = True   # 重复删除无副作用
    
    def run(self, params: ForgetInput, context: ToolContext) -> ToolResult:
        """同步执行"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.arun(params, context))
    
    async def arun(self, params: ForgetInput, context: ToolContext) -> ToolResult:
        """异步执行"""
        from services.memory_service import get_memory_service
        
        user_id = context.user_id
        
        try:
            svc = get_memory_service()
            success = await svc.forget(user_id, params.key)
            
            if success:
                return ToolResult.ok({
                    "deleted": True,
                    "key": params.key,
                    "message": f"已删除记忆: {params.key}"
                })
            else:
                return ToolResult.ok({
                    "deleted": False,
                    "key": params.key,
                    "message": f"没有找到记忆: {params.key}"
                })
            
        except Exception as e:
            return ToolResult.fail(f"删除失败: {e}")
