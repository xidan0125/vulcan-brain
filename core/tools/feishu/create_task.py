"""
Vulcan Brain - Feishu Create Task Tool
创建任务
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuCreateTaskInput(BaseModel):
    """创建任务参数"""
    summary: str = Field(..., description="任务标题")
    description: str = Field(default="", description="任务描述，可选")
    due_timestamp: Optional[str] = Field(
        default=None,
        description="截止时间，Unix 时间戳(毫秒)，可选"
    )
    assignee_ids: Optional[List[str]] = Field(
        default=None,
        description="负责人 open_id 列表，可选"
    )


@register_tool
class FeishuCreateTaskTool(BaseTool):
    """
    创建飞书任务
    
    创建一个新任务，可以指定标题、描述、截止时间和负责人。
    
    示例: {
        "summary": "完成项目方案",
        "due_timestamp": "1704153600000",
        "assignee_ids": ["ou_xxx"]
    }
    """
    
    name = "feishu_create_task"
    description = "创建飞书任务。指定标题，可选描述、截止时间、负责人。"
    args_schema = FeishuCreateTaskInput
    domain = ToolDomain.FEISHU
    is_destructive = True
    is_idempotent = False
    
    def run(self, params: FeishuCreateTaskInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuCreateTaskInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            # 构建截止时间
            due = None
            if params.due_timestamp:
                due = {"timestamp": params.due_timestamp, "is_all_day": False}
            
            # 构建成员列表
            members = None
            if params.assignee_ids:
                members = [
                    {"id": uid, "type": "user", "role": "assignee"}
                    for uid in params.assignee_ids
                ]
            
            result = await client.create_task(
                summary=params.summary,
                description=params.description,
                due=due,
                members=members
            )
            
            if result.get("code") == 0:
                task_data = result.get("data", {}).get("task", {})
                task_id = task_data.get("guid", "")
                return ToolResult.ok({
                    "success": True,
                    "task_id": task_id,
                    "summary": params.summary
                })
            else:
                return ToolResult.fail(
                    f"创建任务失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"创建任务异常: {str(e)}")
