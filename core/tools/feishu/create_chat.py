"""
Vulcan Brain - Feishu Create Chat Tool
创建飞书群聊
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuCreateChatInput(BaseModel):
    """创建群聊参数"""
    name: str = Field(..., description="群聊名称")
    description: str = Field(default="", description="群聊描述")
    user_ids: Optional[List[str]] = Field(
        default=None,
        description="要添加的成员 open_id 列表，可选"
    )


@register_tool
class FeishuCreateChatTool(BaseTool):
    """
    创建飞书群聊
    
    创建一个新的群聊，可以指定群名称、描述，以及初始成员。
    如果不指定成员，会创建一个只有机器人的群。
    
    示例: {"name": "项目讨论组", "user_ids": ["ou_xxx", "ou_yyy"]}
    """
    
    name = "feishu_create_chat"
    description = "创建飞书群聊。指定群名称和初始成员(open_id列表)，返回 chat_id。"
    args_schema = FeishuCreateChatInput
    domain = ToolDomain.FEISHU
    is_destructive = True
    is_idempotent = False
    
    def run(self, params: FeishuCreateChatInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuCreateChatInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.create_chat(
                name=params.name,
                description=params.description,
                user_ids=params.user_ids
            )
            
            if result.get("code") == 0:
                chat_id = result.get("data", {}).get("chat_id", "")
                return ToolResult.ok({
                    "success": True,
                    "chat_id": chat_id,
                    "name": params.name,
                    "member_count": len(params.user_ids) + 1 if params.user_ids else 1
                })
            else:
                return ToolResult.fail(
                    f"创建群聊失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"创建群聊异常: {str(e)}")
