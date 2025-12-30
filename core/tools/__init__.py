"""
Vulcan Brain - Core Tools Package
工具层核心模块

v2: 添加工具初始化器
"""

from .base import (
    BaseTool,
    ToolContext,
    ToolResult,
    ToolDomain,
    EmptyInput,
)
from .registry import (
    ToolRegistry,
    register_tool,
    tool,
)
from .executor import (
    ToolExecutor,
    execute_tool,
)
from .init import (
    init_tools,
    get_tool_schemas,
    get_tool_names,
)

__all__ = [
    # Base
    "BaseTool",
    "ToolContext",
    "ToolResult",
    "ToolDomain",
    "EmptyInput",
    # Registry
    "ToolRegistry",
    "register_tool",
    "tool",
    # Executor
    "ToolExecutor",
    "execute_tool",
    # Initializer
    "init_tools",
    "get_tool_schemas",
    "get_tool_names",
]
