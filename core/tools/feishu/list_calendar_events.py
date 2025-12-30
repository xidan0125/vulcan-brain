"""
Vulcan Brain - Feishu List Calendar Events Tool
获取日历事件列表
"""

from typing import Optional
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuListCalendarEventsInput(BaseModel):
    """获取日历事件列表参数"""
    start_time: Optional[str] = Field(
        default=None,
        description="开始时间过滤，Unix 时间戳(秒)，可选"
    )
    end_time: Optional[str] = Field(
        default=None,
        description="结束时间过滤，Unix 时间戳(秒)，可选"
    )


@register_tool
class FeishuListCalendarEventsTool(BaseTool):
    """
    获取飞书日历事件列表
    
    获取主日历上的事件列表，可按时间范围过滤。
    """
    
    name = "feishu_list_calendar_events"
    description = "获取飞书日历事件列表。可选按时间范围过滤。"
    args_schema = FeishuListCalendarEventsInput
    domain = ToolDomain.FEISHU
    is_destructive = False
    is_idempotent = True
    
    def run(self, params: FeishuListCalendarEventsInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuListCalendarEventsInput, context: ToolContext) -> ToolResult:
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
            
            result = await client.list_calendar_events(
                calendar_id=calendar_id,
                start_time=params.start_time,
                end_time=params.end_time
            )
            
            if result.get("code") == 0:
                items = result.get("data", {}).get("items", [])
                events = [
                    {
                        "event_id": e.get("event_id"),
                        "summary": e.get("summary", "无标题"),
                        "description": e.get("description", ""),
                        "start_time": e.get("start_time", {}),
                        "end_time": e.get("end_time", {}),
                        "status": e.get("status", "")
                    }
                    for e in items
                ]
                return ToolResult.ok({
                    "calendar_id": calendar_id,
                    "event_count": len(events),
                    "events": events
                })
            else:
                return ToolResult.fail(
                    f"获取日历事件失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"获取日历事件异常: {str(e)}")
