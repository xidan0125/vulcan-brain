"""
Vulcan Brain - Recall Tool
记忆检索工具

v2: 重写为新架构
"""

import asyncio
from typing import Optional
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool


class RecallInput(BaseModel):
    """记忆检索参数"""
    key: Optional[str] = Field(
        default=None,
        description="要回忆的记忆键，不指定则返回所有记忆"
    )


@register_tool
class RecallTool(BaseTool):
    """
    回忆之前记住的信息
    
    当用户问你还记得xxx吗、我之前说过什么等需要查询记忆时使用。
    只返回已确认的记忆，待确认的不会返回。
    
    示例:
    - {"key": "user_name"} - 回忆特定记忆
    - {} - 回忆所有记忆
    """
    
    name = "recall"
    description = "回忆之前记住的信息。当用户问'你还记得xxx吗'、'我之前说过什么'时使用。"
    args_schema = RecallInput
    domain = ToolDomain.MEMORY
    is_destructive = False
    is_idempotent = True
    
    def run(self, params: RecallInput, context: ToolContext) -> ToolResult:
        """同步执行"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.arun(params, context))
    
    async def arun(self, params: RecallInput, context: ToolContext) -> ToolResult:
        """异步执行"""
        from services.memory_service import get_memory_service
        
        user_id = context.user_id
        
        try:
            svc = get_memory_service()
            memories = await svc.recall(user_id, params.key)
            
            if not memories:
                if params.key:
                    return ToolResult.ok({
                        "found": False,
                        "message": f"没有找到关于 '{params.key}' 的记忆"
                    })
                return ToolResult.ok({
                    "found": False,
                    "message": "暂无任何记忆"
                })
            
            # 格式化记忆列表
            memory_list = []
            for m in memories:
                memory_list.append({
                    "key": m.get("key"),
                    "value": m.get("value"),
                    "category": m.get("category", "fact")
                })
            
            # 生成可读文本
            if params.key and memory_list:
                text = f"{params.key}: {memory_list[0]['value']}"
            else:
                lines = ["已记住的信息:"]
                for m in memory_list:
                    lines.append(f"  - {m['key']}: {m['value']}")
                text = "\n".join(lines)
            
            return ToolResult.ok({
                "found": True,
                "count": len(memory_list),
                "memories": memory_list,
                "text": text
            })
            
        except Exception as e:
            return ToolResult.fail(f"回忆失败: {e}")
