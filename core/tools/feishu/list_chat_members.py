"""
Vulcan Brain - Feishu List Chat Members Tool
获取群成员列表
"""

from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuListChatMembersInput(BaseModel):
    """获取群成员列表参数"""
    chat_id: str = Field(..., description="群聊 ID (oc_xxx)")


@register_tool
class FeishuListChatMembersTool(BaseTool):
    """
    获取飞书群成员列表
    
    获取指定群聊的所有成员信息。
    
    示例: {"chat_id": "oc_xxx"}
    """
    
    name = "feishu_list_chat_members"
    description = "获取飞书群聊的成员列表。返回成员的 open_id 和名称。"
    args_schema = FeishuListChatMembersInput
    domain = ToolDomain.FEISHU
    is_destructive = False
    is_idempotent = True
    
    def run(self, params: FeishuListChatMembersInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuListChatMembersInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.list_chat_members(chat_id=params.chat_id)
            
            if result.get("code") == 0:
                items = result.get("data", {}).get("items", [])
                members = [
                    {
                        "member_id": m.get("member_id"),
                        "name": m.get("name", "未知"),
                        "member_type": m.get("member_type", "user")
                    }
                    for m in items
                ]
                return ToolResult.ok({
                    "chat_id": params.chat_id,
                    "member_count": len(members),
                    "members": members
                })
            else:
                return ToolResult.fail(
                    f"获取群成员失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"获取群成员异常: {str(e)}")
