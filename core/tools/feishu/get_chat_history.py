"""
Vulcan Brain - Feishu Get Chat History Tool
获取聊天历史记录
"""

from typing import Optional
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuGetChatHistoryInput(BaseModel):
    """获取聊天历史参数"""
    chat_id: str = Field(..., description="群聊 ID (oc_xxx)")
    page_size: int = Field(default=20, description="返回消息数量，默认20条")


@register_tool
class FeishuGetChatHistoryTool(BaseTool):
    """
    获取飞书群聊历史消息
    
    获取指定群聊的最近消息记录。
    
    示例: {"chat_id": "oc_xxx", "page_size": 10}
    """
    
    name = "feishu_get_chat_history"
    description = "获取飞书群聊的历史消息记录。返回最近的消息列表。"
    args_schema = FeishuGetChatHistoryInput
    domain = ToolDomain.FEISHU
    is_destructive = False
    is_idempotent = True
    
    def run(self, params: FeishuGetChatHistoryInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuGetChatHistoryInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.get_chat_history(
                container_id=params.chat_id,
                page_size=params.page_size
            )
            
            if result.get("code") == 0:
                items = result.get("data", {}).get("items", [])
                messages = []
                for m in items:
                    msg = {
                        "message_id": m.get("message_id"),
                        "sender_id": m.get("sender", {}).get("id"),
                        "sender_type": m.get("sender", {}).get("sender_type"),
                        "msg_type": m.get("msg_type"),
                        "create_time": m.get("create_time"),
                    }
                    # 尝试解析文本内容
                    if m.get("msg_type") == "text":
                        try:
                            import json
                            content = json.loads(m.get("body", {}).get("content", "{}"))
                            msg["text"] = content.get("text", "")
                        except:
                            msg["text"] = "[解析失败]"
                    messages.append(msg)
                
                return ToolResult.ok({
                    "chat_id": params.chat_id,
                    "message_count": len(messages),
                    "messages": messages
                })
            else:
                return ToolResult.fail(
                    f"获取聊天记录失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"获取聊天记录异常: {str(e)}")
