"""
Vulcan Brain - Feishu List Tasks Tool
获取任务列表
"""

from typing import Optional
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuListTasksInput(BaseModel):
    """获取任务列表参数"""
    completed: Optional[bool] = Field(
        default=None,
        description="过滤条件: True=已完成, False=未完成, None=全部"
    )


@register_tool
class FeishuListTasksTool(BaseTool):
    """
    获取飞书任务列表
    
    获取任务列表，可以按完成状态过滤。
    """
    
    name = "feishu_list_tasks"
    description = "获取飞书任务列表。可选按完成状态过滤。"
    args_schema = FeishuListTasksInput
    domain = ToolDomain.FEISHU
    is_destructive = False
    is_idempotent = True
    
    def run(self, params: FeishuListTasksInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuListTasksInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.list_tasks(completed=params.completed)
            
            if result.get("code") == 0:
                items = result.get("data", {}).get("items", [])
                tasks = [
                    {
                        "task_id": t.get("guid", ""),
                        "summary": t.get("summary", "无标题"),
                        "description": t.get("description", ""),
                        "due": t.get("due", {}),
                        "completed_at": t.get("completed_at", ""),
                        "creator_id": t.get("creator", {}).get("id", "")
                    }
                    for t in items
                ]
                return ToolResult.ok({
                    "task_count": len(tasks),
                    "tasks": tasks
                })
            else:
                return ToolResult.fail(
                    f"获取任务列表失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"获取任务列表异常: {str(e)}")
