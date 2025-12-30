"""
Vulcan Brain - Feishu Reject Tool
拒绝审批
"""

from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuRejectInput(BaseModel):
    """拒绝审批参数"""
    approval_code: str = Field(..., description="审批定义 code")
    instance_code: str = Field(..., description="审批实例 code")
    user_id: str = Field(..., description="审批人的 open_id")
    task_id: str = Field(..., description="任务 ID")
    comment: str = Field(default="", description="拒绝原因，建议填写")


@register_tool
class FeishuRejectTool(BaseTool):
    """
    拒绝飞书审批
    
    对指定的审批实例执行拒绝操作。
    需要审批人有审批权限。
    """
    
    name = "feishu_reject"
    description = "拒绝飞书审批。需要 approval_code, instance_code, user_id, task_id。"
    args_schema = FeishuRejectInput
    domain = ToolDomain.FEISHU
    is_destructive = True
    is_idempotent = False
    
    def run(self, params: FeishuRejectInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuRejectInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.reject_task(
                approval_code=params.approval_code,
                instance_code=params.instance_code,
                user_id=params.user_id,
                task_id=params.task_id,
                comment=params.comment
            )
            
            if result.get("code") == 0:
                return ToolResult.ok({
                    "success": True,
                    "instance_code": params.instance_code,
                    "action": "rejected",
                    "comment": params.comment
                })
            else:
                return ToolResult.fail(
                    f"审批拒绝失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"审批拒绝异常: {str(e)}")
