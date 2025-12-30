"""
Vulcan Brain - Feishu Add Chat Members Tool
添加群成员
"""

from typing import List
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuAddChatMembersInput(BaseModel):
    """添加群成员参数"""
    chat_id: str = Field(..., description="群聊 ID (oc_xxx)")
    user_ids: List[str] = Field(..., description="要添加的成员 open_id 列表")


@register_tool
class FeishuAddChatMembersTool(BaseTool):
    """
    添加飞书群成员
    
    向指定群聊添加成员。需要有群管理权限。
    
    示例: {"chat_id": "oc_xxx", "user_ids": ["ou_aaa", "ou_bbb"]}
    """
    
    name = "feishu_add_chat_members"
    description = "向飞书群聊添加成员。需要 chat_id 和 user_ids(open_id列表)。"
    args_schema = FeishuAddChatMembersInput
    domain = ToolDomain.FEISHU
    is_destructive = True
    is_idempotent = False
    
    def run(self, params: FeishuAddChatMembersInput, context: ToolContext) -> ToolResult:
        import asyncio
        import concurrent.futures
        
        try:
            loop = asyncio.get_running_loop()
            # 已在事件循环中，使用线程池执行
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.arun(params, context))
                return future.result(timeout=30)
        except RuntimeError:
            # 没有运行中的事件循环，直接运行
            return asyncio.run(self.arun(params, context))
    
    async def arun(self, params: FeishuAddChatMembersInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.add_chat_members(
                chat_id=params.chat_id,
                user_ids=params.user_ids
            )
            
            if result.get("code") == 0:
                return ToolResult.ok({
                    "success": True,
                    "chat_id": params.chat_id,
                    "added_count": len(params.user_ids)
                })
            else:
                return ToolResult.fail(
                    f"添加群成员失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"添加群成员异常: {str(e)}")
