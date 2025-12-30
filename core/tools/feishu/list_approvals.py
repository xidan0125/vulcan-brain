"""
Vulcan Brain - Feishu List Approvals Tool
获取待审批列表
"""

from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuListApprovalsInput(BaseModel):
    """获取审批列表参数"""
    approval_code: str = Field(
        ...,
        description="审批定义 code，可通过 feishu_list_approval_definitions 获取"
    )


@register_tool
class FeishuListApprovalsTool(BaseTool):
    """
    获取飞书审批实例列表
    
    根据审批定义 code 获取审批实例列表。
    
    示例: {"approval_code": "xxx"}
    """
    
    name = "feishu_list_approvals"
    description = "获取飞书审批实例列表。需要提供审批定义 code。"
    args_schema = FeishuListApprovalsInput
    domain = ToolDomain.FEISHU
    is_destructive = False
    is_idempotent = True
    
    def run(self, params: FeishuListApprovalsInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuListApprovalsInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.list_approval_instances(
                approval_code=params.approval_code
            )
            
            if result.get("code") == 0:
                instances = result.get("data", {}).get("instance_code_list", [])
                return ToolResult.ok({
                    "approval_code": params.approval_code,
                    "instance_count": len(instances),
                    "instances": instances
                })
            else:
                return ToolResult.fail(
                    f"获取审批列表失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"获取审批列表异常: {str(e)}")
