"""
Vulcan Brain - Core Tools Package
工具层核心模块
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
from .legacy_adapter import (
    LegacyToolWrapper,
    register_legacy_tools,
    get_legacy_tool_definitions,
    init_from_old_definitions,
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
    # Legacy Adapter
    "LegacyToolWrapper",
    "register_legacy_tools",
    "get_legacy_tool_definitions",
    "init_from_old_definitions",
]
