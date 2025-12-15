"""
Vulcan Brain - Tool Registry
工具注册中心 + 装饰器
"""

from typing import Dict, List, Optional, Any, Type
from .base import BaseTool, ToolDomain, ToolContext, ToolResult
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册中心

    所有工具在启动时自动注册到这里，提供统一的发现和管理接口
    """

    _tools: Dict[str, BaseTool] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        """注册工具实例"""
        if tool.name in cls._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")
        cls._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (domain={tool.domain.value})")

    @classmethod
    def get(cls, name: str) -> Optional[BaseTool]:
        """获取工具实例"""
        return cls._tools.get(name)

    @classmethod
    def list_all(cls) -> List[BaseTool]:
        """列出所有工具"""
        return list(cls._tools.values())

    @classmethod
    def list_schemas(cls) -> List[Dict[str, Any]]:
        """获取所有工具的 Schema (用于 LLM)"""
        return [tool.get_schema() for tool in cls._tools.values()]

    @classmethod
    def list_by_domain(cls, domain: ToolDomain) -> List[BaseTool]:
        """按域筛选工具"""
        return [t for t in cls._tools.values() if t.domain == domain]

    @classmethod
    def list_schemas_by_domain(cls, domain: ToolDomain) -> List[Dict[str, Any]]:
        """获取指定域的工具 Schema"""
        return [t.get_schema() for t in cls._tools.values() if t.domain == domain]

    @classmethod
    def list_names(cls) -> List[str]:
        """获取所有工具名称"""
        return list(cls._tools.keys())

    @classmethod
    def clear(cls) -> None:
        """清空注册表 (测试用)"""
        cls._tools.clear()
        cls._initialized = False

    @classmethod
    def count(cls) -> int:
        """工具数量"""
        return len(cls._tools)


def register_tool(cls: Type[BaseTool]) -> Type[BaseTool]:
    """
    装饰器: 自动实例化并注册工具

    Usage:
        @register_tool
        class MyTool(BaseTool):
            name = "my_tool"
            ...
    """
    instance = cls()
    ToolRegistry.register(instance)
    return cls


def tool(
    name: str,
    description: str,
    domain: ToolDomain = ToolDomain.SYSTEM,
    is_destructive: bool = False,
    is_idempotent: bool = True,
    tags: List[str] = None
):
    """
    函数式工具装饰器 (简化版)

    Usage:
        @tool(name="my_tool", description="Do something")
        def my_tool(query: str, context: ToolContext) -> ToolResult:
            return ToolResult.ok(f"Result: {query}")
    """
    from pydantic import create_model
    import inspect

    def decorator(func):
        # 从函数签名生成参数 Schema
        sig = inspect.signature(func)
        fields = {}
        for param_name, param in sig.parameters.items():
            if param_name == "context":
                continue
            annotation = param.annotation if param.annotation != inspect.Parameter.empty else str
            default = param.default if param.default != inspect.Parameter.empty else ...
            fields[param_name] = (annotation, default)

        # 动态创建 Pydantic Model
        ArgsModel = create_model(f"{name}_Args", **fields)

        # 创建工具类
        class FuncTool(BaseTool):
            pass

        FuncTool.name = name
        FuncTool.description = description
        FuncTool.args_schema = ArgsModel
        FuncTool.domain = domain
        FuncTool.is_destructive = is_destructive
        FuncTool.is_idempotent = is_idempotent
        FuncTool.tags = tags or []

        def run(self, params, context: ToolContext) -> ToolResult:
            kwargs = params.model_dump()
            kwargs["context"] = context
            return func(**kwargs)

        FuncTool.run = run

        # 注册
        instance = FuncTool()
        ToolRegistry.register(instance)

        return func

    return decorator
