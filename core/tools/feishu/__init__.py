"""
Vulcan Brain - Feishu Tools Package
飞书工具集 - 完整版

包含:
- 消息: send_message, get_chat_history
- 群聊: create_chat, add_chat_members, list_chat_members, list_chats
- 用户: search_user, list_departments
- 审批: list_approval_definitions, list_approvals, get_approval_detail, approve, reject
- 日历: create_calendar_event, list_calendar_events
- 任务: create_task, list_tasks, complete_task
"""

from .client import FeishuClient, get_feishu_client

# 消息工具
from .send_message import FeishuSendMessageTool
from .get_chat_history import FeishuGetChatHistoryTool

# 群聊工具
from .create_chat import FeishuCreateChatTool
from .add_chat_members import FeishuAddChatMembersTool
from .list_chat_members import FeishuListChatMembersTool
from .list_chats import FeishuListChatsTool

# 用户工具
from .search_user import FeishuSearchUserTool
from .list_departments import FeishuListDepartmentsTool

# 审批工具
from .list_approval_definitions import FeishuListApprovalDefinitionsTool
from .list_approvals import FeishuListApprovalsTool
from .get_approval_detail import FeishuGetApprovalDetailTool
from .approve import FeishuApproveTool
from .reject import FeishuRejectTool

# 日历工具
from .create_calendar_event import FeishuCreateCalendarEventTool
from .list_calendar_events import FeishuListCalendarEventsTool

# 任务工具
from .create_task import FeishuCreateTaskTool
from .list_tasks import FeishuListTasksTool
from .complete_task import FeishuCompleteTaskTool


__all__ = [
    # Client
    "FeishuClient",
    "get_feishu_client",
    
    # 消息
    "FeishuSendMessageTool",
    "FeishuGetChatHistoryTool",
    
    # 群聊
    "FeishuCreateChatTool",
    "FeishuAddChatMembersTool",
    "FeishuListChatMembersTool",
    "FeishuListChatsTool",
    
    # 用户
    "FeishuSearchUserTool",
    "FeishuListDepartmentsTool",
    
    # 审批
    "FeishuListApprovalDefinitionsTool",
    "FeishuListApprovalsTool",
    "FeishuGetApprovalDetailTool",
    "FeishuApproveTool",
    "FeishuRejectTool",
    
    # 日历
    "FeishuCreateCalendarEventTool",
    "FeishuListCalendarEventsTool",
    
    # 任务
    "FeishuCreateTaskTool",
    "FeishuListTasksTool",
    "FeishuCompleteTaskTool",
]
