"""
Vulcan Brain - Feishu List Approval Definitions Tool
获取审批定义列表
"""

from pydantic import BaseModel

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuListApprovalDefinitionsInput(BaseModel):
    """获取审批定义列表参数"""
    pass  # 无必填参数


@register_tool
class FeishuListApprovalDefinitionsTool(BaseTool):
    """
    获取飞书审批定义列表
    
    获取企业中配置的所有审批流程定义，包含 approval_code 和名称。
    """
    
    name = "feishu_list_approval_definitions"
    description = "获取飞书审批定义列表。返回所有可用的审批流程及其 approval_code。"
    args_schema = FeishuListApprovalDefinitionsInput
    domain = ToolDomain.FEISHU
    is_destructive = False
    is_idempotent = True
    
    def run(self, params: FeishuListApprovalDefinitionsInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuListApprovalDefinitionsInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.list_approval_definitions()
            
            if result.get("code") == 0:
                items = result.get("data", {}).get("approval_list", [])
                definitions = [
                    {
                        "approval_code": d.get("approval_code"),
                        "approval_name": d.get("approval_name", ""),
                        "is_external": d.get("is_external", False)
                    }
                    for d in items
                ]
                return ToolResult.ok({
                    "definition_count": len(definitions),
                    "definitions": definitions
                })
            else:
                return ToolResult.fail(
                    f"获取审批定义失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"获取审批定义异常: {str(e)}")
