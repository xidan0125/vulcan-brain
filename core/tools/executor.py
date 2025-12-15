"""
Vulcan Brain - Tool Executor
统一工具执行器 + 安全检查

v2: 增加异步支持 + JSON 清理
"""

import json
import logging
from typing import Optional
from .base import ToolContext, ToolResult, clean_json_string
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    工具执行器

    负责:
    1. 工具查找
    2. 权限检查
    3. 参数验证
    4. 执行并捕获异常
    5. 统一返回格式
    """

    # 破坏性操作需要的权限
    DESTRUCTIVE_PERMISSION = "execute_destructive"

    @classmethod
    def execute(
        cls,
        tool_name: str,
        arguments: str | dict,
        context: Optional[ToolContext] = None
    ) -> ToolResult:
        """
        同步执行工具

        Args:
            tool_name: 工具名称
            arguments: JSON 字符串或字典
            context: 运行时上下文 (可选，默认创建匿名上下文)

        Returns:
            ToolResult: 统一返回格式
        """
        # 1. 默认上下文
        if context is None:
            context = ToolContext()

        # 2. 查找工具
        tool = ToolRegistry.get(tool_name)
        if not tool:
            available = ", ".join(ToolRegistry.list_names())
            return ToolResult.fail(
                f"Tool '{tool_name}' not found. Available tools: {available}"
            )

        # 3. 破坏性操作权限检查
        if tool.is_destructive:
            if not context.has_permission(cls.DESTRUCTIVE_PERMISSION):
                logger.warning(
                    f"Permission denied for destructive tool '{tool_name}' "
                    f"(user={context.user_id})"
                )
                return ToolResult.fail(
                    f"Permission denied: '{tool_name}' is a destructive action "
                    f"that requires '{cls.DESTRUCTIVE_PERMISSION}' permission."
                )

        # 4. 解析参数 (支持 Markdown JSON 清理)
        if isinstance(arguments, str):
            try:
                cleaned = clean_json_string(arguments) if arguments else "{}"
                args = json.loads(cleaned) if cleaned else {}
            except json.JSONDecodeError as e:
                return ToolResult.fail(
                    f"Invalid JSON arguments: {e}. "
                    f"Please provide valid JSON format."
                )
        else:
            args = arguments or {}

        # 5. 参数验证
        try:
            validated_params = tool.validate_params(args)
        except Exception as e:
            return ToolResult.fail(
                f"Invalid arguments for '{tool_name}': {e}. "
                f"Please check the parameter types and required fields."
            )

        # 6. 执行工具
        try:
            result = tool.run(validated_params, context)
            logger.info(f"Tool '{tool_name}' executed successfully")
            return result
        except PermissionError as e:
            logger.warning(f"Permission error in tool '{tool_name}': {e}")
            return ToolResult.fail(f"Permission denied: {e}")
        except Exception as e:
            logger.exception(f"Tool '{tool_name}' execution failed")
            return ToolResult.fail(
                f"Tool execution failed: {e}. "
                f"Please check your inputs and try again."
            )

    @classmethod
    async def execute_async(
        cls,
        tool_name: str,
        arguments: str | dict,
        context: Optional[ToolContext] = None
    ) -> ToolResult:
        """
        异步执行工具

        Args:
            tool_name: 工具名称
            arguments: JSON 字符串或字典
            context: 运行时上下文

        Returns:
            ToolResult: 统一返回格式
        """
        # 1. 默认上下文
        if context is None:
            context = ToolContext()

        # 2. 查找工具
        tool = ToolRegistry.get(tool_name)
        if not tool:
            available = ", ".join(ToolRegistry.list_names())
            return ToolResult.fail(
                f"Tool '{tool_name}' not found. Available tools: {available}"
            )

        # 3. 破坏性操作权限检查
        if tool.is_destructive:
            if not context.has_permission(cls.DESTRUCTIVE_PERMISSION):
                logger.warning(
                    f"Permission denied for destructive tool '{tool_name}' "
                    f"(user={context.user_id})"
                )
                return ToolResult.fail(
                    f"Permission denied: '{tool_name}' is a destructive action "
                    f"that requires '{cls.DESTRUCTIVE_PERMISSION}' permission."
                )

        # 4. 解析参数
        if isinstance(arguments, str):
            try:
                cleaned = clean_json_string(arguments) if arguments else "{}"
                args = json.loads(cleaned) if cleaned else {}
            except json.JSONDecodeError as e:
                return ToolResult.fail(f"Invalid JSON arguments: {e}")
        else:
            args = arguments or {}

        # 5. 参数验证
        try:
            validated_params = tool.validate_params(args)
        except Exception as e:
            return ToolResult.fail(f"Invalid arguments for '{tool_name}': {e}")

        # 6. 异步执行工具
        try:
            result = await tool.arun(validated_params, context)
            logger.info(f"Tool '{tool_name}' executed successfully (async)")
            return result
        except PermissionError as e:
            logger.warning(f"Permission error in tool '{tool_name}': {e}")
            return ToolResult.fail(f"Permission denied: {e}")
        except Exception as e:
            logger.exception(f"Tool '{tool_name}' async execution failed")
            return ToolResult.fail(f"Tool execution failed: {e}")

    @classmethod
    def execute_str(
        cls,
        tool_name: str,
        arguments: str | dict,
        context: Optional[ToolContext] = None
    ) -> str:
        """
        执行工具并返回字符串 (兼容旧接口)

        Returns:
            str: 工具执行结果的字符串表示
        """
        result = cls.execute(tool_name, arguments, context)
        return result.to_llm_string()


# 便捷函数 (兼容旧代码)
def execute_tool(name: str, arguments: str, context: Optional[ToolContext] = None) -> str:
    """
    兼容旧接口的工具执行函数

    Args:
        name: 工具名称
        arguments: JSON 字符串参数

    Returns:
        str: 执行结果字符串
    """
    return ToolExecutor.execute_str(name, arguments, context)
