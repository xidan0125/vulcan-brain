"""
Vulcan Brain - Tool System Initializer
工具系统初始化器

在应用启动时调用一次，注册所有工具到 ToolRegistry
"""

import logging
from .registry import ToolRegistry

logger = logging.getLogger(__name__)

_initialized = False


def init_tools() -> int:
    """
    初始化所有工具
    
    Returns:
        int: 注册的工具数量
    """
    global _initialized
    if _initialized:
        logger.debug("Tool system already initialized")
        return ToolRegistry.count()
    
    logger.info("Initializing tool system...")
    
    # 1. Core Tools (搜索等)
    try:
        from core.tools.core import WebSearchTool
        logger.info("  ✓ Loaded core tools (web_search)")
    except ImportError as e:
        logger.warning(f"  ✗ Could not load core tools: {e}")
    
    # 2. Memory Tools (记忆系统)
    try:
        from core.tools.memory import RememberTool, RecallTool, ForgetTool
        logger.info("  ✓ Loaded memory tools (remember, recall, forget)")
    except ImportError as e:
        logger.warning(f"  ✗ Could not load memory tools: {e}")
    
    # 3. Feishu Tools (飞书集成 - 完整版)
    try:
        from core.tools.feishu import (
            # 消息
            FeishuSendMessageTool,
            FeishuGetChatHistoryTool,
            # 群聊
            FeishuCreateChatTool,
            FeishuAddChatMembersTool,
            FeishuListChatMembersTool,
            FeishuListChatsTool,
            # 用户
            FeishuSearchUserTool,
            FeishuListDepartmentsTool,
            # 审批
            FeishuListApprovalDefinitionsTool,
            FeishuListApprovalsTool,
            FeishuGetApprovalDetailTool,
            FeishuApproveTool,
            FeishuRejectTool,
            # 日历
            FeishuCreateCalendarEventTool,
            FeishuListCalendarEventsTool,
            # 任务
            FeishuCreateTaskTool,
            FeishuListTasksTool,
            FeishuCompleteTaskTool,
        )
        logger.info("  ✓ Loaded Feishu tools (18 tools: message, chat, user, approval, calendar, task)")
    except ImportError as e:
        logger.warning(f"  ✗ Could not load Feishu tools: {e}")
    
    _initialized = True
    tool_count = ToolRegistry.count()
    tool_names = ToolRegistry.list_names()
    
    logger.info(f"Tool system initialized: {tool_count} tools registered")
    logger.info(f"Available tools: {tool_names}")
    
    return tool_count


def get_tool_schemas():
    """
    获取所有工具的 Schema (用于 LLM)
    
    自动初始化工具系统（如果尚未初始化）
    """
    if not _initialized:
        init_tools()
    return ToolRegistry.list_schemas()


def get_tool_names():
    """
    获取所有工具名称
    
    自动初始化工具系统（如果尚未初始化）
    """
    if not _initialized:
        init_tools()
    return ToolRegistry.list_names()
