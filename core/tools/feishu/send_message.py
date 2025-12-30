"""
Vulcan Brain - Feishu Send Message Tool
原子工具：发送飞书消息

P1.1 实现
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuSendMessageInput(BaseModel):
    """飞书发送消息参数"""
    
    receive_id: str = Field(
        ...,
        description="接收者ID，可以是 open_id、user_id、union_id、email 或 chat_id"
    )
    receive_id_type: str = Field(
        default="open_id",
        description="ID类型: open_id | user_id | union_id | email | chat_id"
    )
    content: str = Field(
        ...,
        description="消息内容（纯文本）"
    )


@register_tool
class FeishuSendMessageTool(BaseTool):
    """
    发送飞书消息
    
    向指定用户或群聊发送文本消息。
    支持多种 ID 类型：open_id、user_id、email、chat_id 等。
    
    示例:
    - 发送给用户: {"receive_id": "ou_xxx", "content": "你好"}
    - 发送给群聊: {"receive_id": "oc_xxx", "receive_id_type": "chat_id", "content": "通知"}
    """
    
    name = "feishu_send_message"
    description = "发送飞书消息给指定用户或群聊。支持 open_id/user_id/email/chat_id 等多种 ID 类型。"
    args_schema = FeishuSendMessageInput
    domain = ToolDomain.FEISHU
    is_destructive = False  # 发消息不是破坏性操作
    is_idempotent = False   # 发消息不幂等（会发多条）
    
    def run(self, params: FeishuSendMessageInput, context: ToolContext) -> ToolResult:
        """同步执行（内部使用 asyncio）"""
        import asyncio
        import concurrent.futures
        
        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.arun(params, context))
                return future.result(timeout=30)
        except RuntimeError:
            return asyncio.run(self.arun(params, context))
    
    async def arun(self, params: FeishuSendMessageInput, context: ToolContext) -> ToolResult:
        """异步执行"""
        client = get_feishu_client()
        
        result = await client.send_message(
            receive_id=params.receive_id,
            receive_id_type=params.receive_id_type,
            msg_type="text",
            content=params.content
        )
        
        if result.get("code") == 0:
            message_id = result.get("data", {}).get("message_id", "")
            return ToolResult.ok({
                "success": True,
                "message_id": message_id,
                "receive_id": params.receive_id
            })
        else:
            error_msg = result.get("msg", "Unknown error")
            error_code = result.get("code", -1)
            return ToolResult.fail(
                f"飞书消息发送失败 (code={error_code}): {error_msg}"
            )
