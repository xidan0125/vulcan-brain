"""
Vulcan Brain - Feishu Search User Tool
原子工具：按名字搜索飞书用户

P1.2 - 产品导向设计
"""

from typing import List, Dict
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuSearchUserInput(BaseModel):
    """飞书用户搜索 - 按名字"""
    name: str = Field(..., description="用户姓名，如 '张三'、'小明'")


@register_tool
class FeishuSearchUserTool(BaseTool):
    """
    按名字搜索飞书用户
    
    输入用户姓名，返回匹配的用户信息（包含 open_id 用于发消息）。
    如果有多个同名用户，会列出所有匹配项供确认。
    
    示例: {"name": "张三"}
    """
    
    name = "feishu_search_user"
    description = "按名字搜索飞书用户，返回 open_id 用于发消息。如有多个同名会列出供确认。"
    args_schema = FeishuSearchUserInput
    domain = ToolDomain.FEISHU
    is_destructive = False
    is_idempotent = True
    
    def run(self, params: FeishuSearchUserInput, context: ToolContext) -> ToolResult:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.arun(params, context))
    
    async def arun(self, params: FeishuSearchUserInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            all_users = await client.get_all_visible_users()
            
            if not all_users:
                return ToolResult.fail("无法获取用户列表，请检查机器人权限")
            
            # 按名字模糊匹配
            query = params.name.lower()
            matches = [
                u for u in all_users 
                if query in u.get("name", "").lower()
            ]
            
            if not matches:
                return ToolResult.fail(f"找不到叫 '{params.name}' 的用户")
            
            # 单个匹配 - 直接返回
            if len(matches) == 1:
                u = matches[0]
                return ToolResult.ok({
                    "found": 1,
                    "user": {
                        "open_id": u["open_id"],
                        "name": u["name"],
                        "department": u.get("department_ids", [])
                    }
                })
            
            # 多个匹配 - 列出供确认
            users_list = [
                {
                    "open_id": u["open_id"],
                    "name": u["name"],
                    "email": u.get("email", ""),
                    "department": u.get("department_ids", [])
                }
                for u in matches
            ]
            
            return ToolResult.ok({
                "found": len(matches),
                "message": f"找到 {len(matches)} 个叫 '{params.name}' 的用户，请确认:",
                "users": users_list
            })
            
        except Exception as e:
            return ToolResult.fail(f"搜索失败: {str(e)}")
