"""
Vulcan Brain - Feishu Create Calendar Event Tool
创建日历事件
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuCreateCalendarEventInput(BaseModel):
    """创建日历事件参数"""
    summary: str = Field(..., description="事件标题")
    start_time: str = Field(
        ...,
        description="开始时间，Unix 时间戳(秒)，如 '1704067200'"
    )
    end_time: str = Field(
        ...,
        description="结束时间，Unix 时间戳(秒)"
    )
    description: str = Field(default="", description="事件描述，可选")
    attendee_ids: Optional[List[str]] = Field(
        default=None,
        description="参与者 open_id 列表，可选"
    )


@register_tool
class FeishuCreateCalendarEventTool(BaseTool):
    """
    创建飞书日历事件
    
    在主日历上创建一个新的事件/会议。
    
    示例: {
        "summary": "周会",
        "start_time": "1704067200",
        "end_time": "1704070800",
        "attendee_ids": ["ou_xxx", "ou_yyy"]
    }
    """
    
    name = "feishu_create_calendar_event"
    description = "创建飞书日历事件。指定标题、开始/结束时间(Unix时间戳)、可选参与者。"
    args_schema = FeishuCreateCalendarEventInput
    domain = ToolDomain.FEISHU
    is_destructive = True
    is_idempotent = False
    
    def run(self, params: FeishuCreateCalendarEventInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuCreateCalendarEventInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            # 先获取主日历 ID
            primary_result = await client.get_primary_calendar()
            if primary_result.get("code") != 0:
                return ToolResult.fail(
                    f"获取主日历失败: {primary_result.get('msg')}"
                )
            
            calendar_id = primary_result.get("data", {}).get("calendars", [{}])[0].get("calendar", {}).get("calendar_id")
            if not calendar_id:
                return ToolResult.fail("无法获取主日历 ID")
            
            # 构建参与者列表
            attendees = None
            if params.attendee_ids:
                attendees = [
                    {"type": "user", "user_id": uid}
                    for uid in params.attendee_ids
                ]
            
            result = await client.create_calendar_event(
                calendar_id=calendar_id,
                summary=params.summary,
                start_time={"timestamp": params.start_time},
                end_time={"timestamp": params.end_time},
                description=params.description,
                attendees=attendees
            )
            
            if result.get("code") == 0:
                event_id = result.get("data", {}).get("event", {}).get("event_id", "")
                return ToolResult.ok({
                    "success": True,
                    "event_id": event_id,
                    "summary": params.summary,
                    "calendar_id": calendar_id
                })
            else:
                return ToolResult.fail(
                    f"创建日历事件失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"创建日历事件异常: {str(e)}")
