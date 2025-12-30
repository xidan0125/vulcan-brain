"""
Vulcan Brain - Feishu List Chats Tool
获取机器人所在的群聊列表
"""

from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuListChatsInput(BaseModel):
    """获取群聊列表参数"""
    pass  # 无必填参数


@register_tool
class FeishuListChatsTool(BaseTool):
    """
    获取机器人所在的群聊列表
    
    返回机器人加入的所有群聊信息，包含群名称和 chat_id。
    """
    
    name = "feishu_list_chats"
    description = "获取机器人所在的所有飞书群聊列表。返回群名和 chat_id。"
    args_schema = FeishuListChatsInput
    domain = ToolDomain.FEISHU
    is_destructive = False
    is_idempotent = True
    
    def run(self, params: FeishuListChatsInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuListChatsInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.list_chats()
            
            if result.get("code") == 0:
                items = result.get("data", {}).get("items", [])
                chats = [
                    {
                        "chat_id": c.get("chat_id"),
                        "name": c.get("name", "未命名群"),
                        "description": c.get("description", ""),
                        "owner_id": c.get("owner_id"),
                        "chat_mode": c.get("chat_mode", "group")
                    }
                    for c in items
                ]
                return ToolResult.ok({
                    "chat_count": len(chats),
                    "chats": chats
                })
            else:
                return ToolResult.fail(
                    f"获取群聊列表失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"获取群聊列表异常: {str(e)}")
