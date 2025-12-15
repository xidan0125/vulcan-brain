"""
Vulcan Brain - Legacy Tool Adapter
桥接旧工具到新架构

这个模块提供:
1. 将旧的函数式工具包装成 BaseTool
2. 兼容旧的 TOOL_DEFINITIONS 格式
3. 平滑迁移路径
"""

import json
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, create_model
from .base import BaseTool, ToolContext, ToolResult, ToolDomain
from .registry import ToolRegistry
import logging

logger = logging.getLogger(__name__)


class LegacyToolWrapper(BaseTool):
    """
    包装旧的函数式工具

    将简单的 lambda/function 包装成符合新架构的 BaseTool
    """

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters_schema: Dict[str, Any],
        domain: ToolDomain = ToolDomain.SYSTEM,
        is_destructive: bool = False,
    ):
        self.name = name
        self.description = description
        self._func = func
        self.domain = domain
        self.is_destructive = is_destructive
        self.is_idempotent = True
        self.tags = []

        # 从 JSON Schema 动态创建 Pydantic Model
        self.args_schema = self._create_args_model(name, parameters_schema)

    def _create_args_model(self, name: str, schema: Dict[str, Any]) -> type:
        """从 JSON Schema 创建 Pydantic Model"""
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        fields = {}
        for prop_name, prop_schema in properties.items():
            # 简单类型映射
            type_map = {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            prop_type = type_map.get(prop_schema.get("type", "string"), str)

            if prop_name in required:
                fields[prop_name] = (prop_type, ...)
            else:
                fields[prop_name] = (Optional[prop_type], None)

        return create_model(f"{name}_Args", **fields)

    def run(self, params: BaseModel, context: ToolContext) -> ToolResult:
        """执行旧工具"""
        try:
            args = params.model_dump(exclude_none=True)
            result = self._func(args)
            return ToolResult.ok(result)
        except Exception as e:
            return ToolResult.fail(str(e))


def register_legacy_tools(
    tool_definitions: List[Dict],
    tool_executors: Dict[str, Callable],
    destructive_tools: List[str] = None
) -> None:
    """
    批量注册旧格式的工具

    Args:
        tool_definitions: OpenAI 格式的工具定义列表
        tool_executors: 工具名 -> 执行函数的映射
        destructive_tools: 破坏性工具名列表
    """
    destructive = set(destructive_tools or [])

    for tool_def in tool_definitions:
        func_def = tool_def.get("function", {})
        name = func_def.get("name")

        if not name or name not in tool_executors:
            logger.warning(f"Skipping tool '{name}': no executor found")
            continue

        wrapper = LegacyToolWrapper(
            name=name,
            description=func_def.get("description", ""),
            func=tool_executors[name],
            parameters_schema=func_def.get("parameters", {}),
            is_destructive=name in destructive,
        )

        ToolRegistry.register(wrapper)
        logger.info(f"Registered legacy tool: {name}")


def get_legacy_tool_definitions() -> List[Dict]:
    """
    获取兼容旧格式的工具定义

    用于渐进式迁移，让新旧系统可以共存
    """
    return ToolRegistry.list_schemas()


def init_from_old_definitions():
    """
    从旧的 tool_definitions.py 初始化

    这个函数在启动时调用，将旧工具导入新系统
    """
    try:
        # 动态导入旧的定义
        import sys
        import os
        sys.path.insert(0, os.path.expanduser('~/vulcan-brain'))

        from tool_definitions import TOOL_DEFINITIONS, TOOL_EXECUTORS

        # 记忆相关工具标记为破坏性
        destructive = ["remember", "forget"]

        register_legacy_tools(
            tool_definitions=TOOL_DEFINITIONS,
            tool_executors=TOOL_EXECUTORS,
            destructive_tools=destructive
        )

        logger.info(f"Initialized {ToolRegistry.count()} tools from legacy definitions")

    except ImportError as e:
        logger.warning(f"Could not import legacy tool_definitions: {e}")
    except Exception as e:
        logger.error(f"Error initializing legacy tools: {e}")
