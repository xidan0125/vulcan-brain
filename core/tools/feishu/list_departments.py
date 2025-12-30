"""
Vulcan Brain - Feishu List Departments Tool
获取部门列表
"""

from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolContext, ToolResult, ToolDomain
from core.tools.registry import register_tool
from .client import get_feishu_client


class FeishuListDepartmentsInput(BaseModel):
    """获取部门列表参数"""
    parent_department_id: str = Field(
        default="0",
        description="父部门 ID，默认 '0' 表示根部门"
    )


@register_tool
class FeishuListDepartmentsTool(BaseTool):
    """
    获取飞书部门列表
    
    获取组织架构中的部门列表，可以按层级查询。
    """
    
    name = "feishu_list_departments"
    description = "获取飞书部门列表。默认获取顶层部门，可指定 parent_department_id 查子部门。"
    args_schema = FeishuListDepartmentsInput
    domain = ToolDomain.FEISHU
    is_destructive = False
    is_idempotent = True
    
    def run(self, params: FeishuListDepartmentsInput, context: ToolContext) -> ToolResult:
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
    
    async def arun(self, params: FeishuListDepartmentsInput, context: ToolContext) -> ToolResult:
        client = get_feishu_client()
        
        try:
            result = await client.list_departments(
                parent_department_id=params.parent_department_id
            )
            
            if result.get("code") == 0:
                items = result.get("data", {}).get("items", [])
                departments = [
                    {
                        "department_id": d.get("department_id"),
                        "open_department_id": d.get("open_department_id"),
                        "name": d.get("name", "未命名"),
                        "parent_department_id": d.get("parent_department_id"),
                        "member_count": d.get("member_count", 0)
                    }
                    for d in items
                ]
                return ToolResult.ok({
                    "department_count": len(departments),
                    "departments": departments
                })
            else:
                return ToolResult.fail(
                    f"获取部门列表失败 (code={result.get('code')}): {result.get('msg')}"
                )
        except Exception as e:
            return ToolResult.fail(f"获取部门列表异常: {str(e)}")
