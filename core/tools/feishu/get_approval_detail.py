"""
Vulcan Brain - Feishu Get Approval Detail Tool
获取审批详情
"""

from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuGetApprovalDetailInput(BaseModel):
    """获取审批详情参数"""
    instance_id: str = Field(..., description="审批实例 ID")


@register_tool
class FeishuGetApprovalDetailTool(BaseTool):
    """
    获取飞书审批实例详情
    
    获取指定审批实例的详细信息，包括申请人、表单内容、审批状态等。
    
    示例: {"instance_id": "xxx"}
    """
    
    name = "feishu_get_approval_detail"
    description = "获取飞书审批实例的详细信息。返回申请人、表单内容、状态等。"
    args_schema = FeishuGetApprovalDetailInput
    domain = ToolDomain.FEISHU
    is_destructive = False
    is_idempotent = True
    
    def run(self, params: FeishuGetApprovalDetailInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuGetApprovalDetailInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.get_approval_instance(instance_id=params.instance_id)
            
            if result.get("code") == 0:
                data = result.get("data", {})
                return ToolResult.ok({
                    "instance_id": params.instance_id,
                    "approval_name": data.get("approval_name", ""),
                    "status": data.get("status", ""),
                    "start_time": data.get("start_time", ""),
                    "end_time": data.get("end_time", ""),
                    "user_id": data.get("user_id", ""),
                    "form": data.get("form", ""),
                    "timeline": data.get("timeline", [])
                })
            else:
                return ToolResult.fail(
                    f"获取审批详情失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"获取审批详情异常: {str(e)}")
