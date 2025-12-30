"""
Vulcan Brain - Feishu Complete Task Tool
完成任务
"""

from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuCompleteTaskInput(BaseModel):
    """完成任务参数"""
    task_id: str = Field(..., description="任务 ID (guid)")


@register_tool
class FeishuCompleteTaskTool(BaseTool):
    """
    完成飞书任务
    
    将指定任务标记为已完成。
    """
    
    name = "feishu_complete_task"
    description = "将飞书任务标记为已完成。"
    args_schema = FeishuCompleteTaskInput
    domain = ToolDomain.FEISHU
    is_destructive = True
    is_idempotent = True
    
    def run(self, params: FeishuCompleteTaskInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuCompleteTaskInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.complete_task(task_id=params.task_id)
            
            if result.get("code") == 0:
                return ToolResult.ok({
                    "success": True,
                    "task_id": params.task_id,
                    "action": "completed"
                })
            else:
                return ToolResult.fail(
                    f"完成任务失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"完成任务异常: {str(e)}")
