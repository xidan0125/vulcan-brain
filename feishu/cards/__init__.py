"""
飞书卡片模板模块
"""

from .base import (
    BaseCard,
    markdown_text,
    plain_text,
    button,
    button_primary,
    button_danger,
    button_link,
    select_static,
    input_field,
    divider,
    note,
)

from .task_cards import (
    TaskAssignmentCard,
    TaskProgressCard,
    TaskOverdueCard,
    MyTasksCard,
    TaskUpdateFormCard,
    TaskCompletedCard,
    build_task_assignment_card,
    build_task_progress_card,
    build_task_overdue_card,
    build_my_tasks_card,
    build_task_update_form_card,
    build_task_completed_card,
)

from .approval_cards import (
    APPROVAL_TYPES,
    ApprovalRequestCard,
    ApprovalResultCard,
    ApprovalFormCard,
    MyApprovalsCard,
    ApprovalSubmittedCard,
    build_approval_request_card,
    build_approval_result_card,
    build_approval_form_card,
    build_my_approvals_card,
    build_approval_submitted_card,
)

from .report_cards import (
    DailyReportCard,
    WeeklyReportCard,
    InfoHubSummaryCard,
    build_daily_report_card,
    build_weekly_report_card,
    build_info_hub_summary_card,
)

from .alert_cards import (
    TaskOverdueAlertCard,
    TaskBlockedAlertCard,
    ApprovalPendingAlertCard,
    UrgentEmailAlertCard,
    SystemAlertCard,
    NoResponseAlertCard,
    build_task_overdue_alert_card,
    build_task_blocked_alert_card,
    build_approval_pending_alert_card,
    build_urgent_email_alert_card,
    build_system_alert_card,
    build_no_response_alert_card,
)

__all__ = [
    # Base
    "BaseCard",
    "markdown_text",
    "plain_text",
    "button",
    "button_primary",
    "button_danger",
    "button_link",
    "select_static",
    "input_field",
    "divider",
    "note",
    # Task cards
    "TaskAssignmentCard",
    "TaskProgressCard",
    "TaskOverdueCard",
    "MyTasksCard",
    "TaskUpdateFormCard",
    "TaskCompletedCard",
    "build_task_assignment_card",
    "build_task_progress_card",
    "build_task_overdue_card",
    "build_my_tasks_card",
    "build_task_update_form_card",
    "build_task_completed_card",
    # Approval cards
    "APPROVAL_TYPES",
    "ApprovalRequestCard",
    "ApprovalResultCard",
    "ApprovalFormCard",
    "MyApprovalsCard",
    "ApprovalSubmittedCard",
    "build_approval_request_card",
    "build_approval_result_card",
    "build_approval_form_card",
    "build_my_approvals_card",
    "build_approval_submitted_card",
    # Report cards
    "DailyReportCard",
    "WeeklyReportCard",
    "InfoHubSummaryCard",
    "build_daily_report_card",
    "build_weekly_report_card",
    "build_info_hub_summary_card",
    # Alert cards
    "TaskOverdueAlertCard",
    "TaskBlockedAlertCard",
    "ApprovalPendingAlertCard",
    "UrgentEmailAlertCard",
    "SystemAlertCard",
    "NoResponseAlertCard",
    "build_task_overdue_alert_card",
    "build_task_blocked_alert_card",
    "build_approval_pending_alert_card",
    "build_urgent_email_alert_card",
    "build_system_alert_card",
    "build_no_response_alert_card",
]
