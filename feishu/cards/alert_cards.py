"""
告警通知相关卡片模板
"""

from typing import Dict, Any, List
from datetime import datetime
from .base import (
    BaseCard,
    markdown_text,
    button_primary,
    button_danger,
    button,
    button_link,
    divider,
    note
)


class TaskOverdueAlertCard(BaseCard):
    """
    任务逾期告警卡片
    发送给负责人和 PM
    """

    def __init__(self, tasks: List[Dict[str, Any]]):
        super().__init__(
            title=f"任务逾期告警 ({len(tasks)} 个)",
            color="red",
            icon="🚨"
        )
        self.tasks = tasks

    def build_content(self) -> List[Dict]:
        if not self.tasks:
            return [markdown_text("暂无逾期任务")]

        lines = ["以下任务已逾期，请尽快处理：\n"]

        for task in self.tasks[:10]:
            name = task.get("name", "未命名")
            assignee = task.get("assignee_name", "未分配")
            deadline = task.get("deadline")
            if isinstance(deadline, datetime):
                overdue_days = (datetime.now() - deadline).days
                deadline_str = deadline.strftime("%m-%d")
            else:
                overdue_days = 0
                deadline_str = str(deadline)[:10] if deadline else "未设置"

            lines.append(f"• **{name}**")
            lines.append(f"  负责人: {assignee} | 截止: {deadline_str} | 逾期 {overdue_days} 天")
            lines.append("")

        if len(self.tasks) > 10:
            lines.append(f"... 还有 {len(self.tasks) - 10} 个逾期任务")

        return [markdown_text("\n".join(lines))]

    def build_actions(self) -> List[Dict]:
        return [
            button_primary("📋 查看全部", "view_overdue_tasks", {}),
            button_link("🔧 项目管理", "https://vsg-brain.com/projects"),
        ]


class TaskBlockedAlertCard(BaseCard):
    """
    任务阻塞告警卡片
    """

    def __init__(self, tasks: List[Dict[str, Any]]):
        super().__init__(
            title=f"任务阻塞告警 ({len(tasks)} 个)",
            color="orange",
            icon="⚠️"
        )
        self.tasks = tasks

    def build_content(self) -> List[Dict]:
        if not self.tasks:
            return [markdown_text("暂无阻塞任务")]

        lines = ["以下任务处于阻塞状态：\n"]

        for task in self.tasks[:10]:
            name = task.get("name", "未命名")
            assignee = task.get("assignee_name", "未分配")
            blocked_reason = task.get("blocked_reason", "未说明原因")

            lines.append(f"• **{name}** ({assignee})")
            lines.append(f"  原因: {blocked_reason}")
            lines.append("")

        return [markdown_text("\n".join(lines))]

    def build_actions(self) -> List[Dict]:
        return [
            button_primary("🔍 查看详情", "view_blocked_tasks", {}),
            button_link("🔧 项目管理", "https://vsg-brain.com/projects"),
        ]


class ApprovalPendingAlertCard(BaseCard):
    """
    审批待处理提醒卡片
    """

    def __init__(self, approvals: List[Dict[str, Any]], approver_name: str = ""):
        count = len(approvals)
        super().__init__(
            title=f"待处理审批提醒 ({count} 条)",
            color="orange",
            icon="📋"
        )
        self.approvals = approvals
        self.approver_name = approver_name

    def build_content(self) -> List[Dict]:
        if not self.approvals:
            return [markdown_text("🎉 暂无待处理审批")]

        lines = []
        if self.approver_name:
            lines.append(f"**{self.approver_name}**，您有 {len(self.approvals)} 条审批待处理：\n")
        else:
            lines.append(f"您有 {len(self.approvals)} 条审批待处理：\n")

        for a in self.approvals[:5]:
            type_name = a.get("type_name", "审批")
            applicant = a.get("applicant_name", "未知")
            created = a.get("created_at")
            if isinstance(created, datetime):
                created_str = created.strftime("%m-%d %H:%M")
            else:
                created_str = ""

            lines.append(f"• {type_name} - {applicant} ({created_str})")

        if len(self.approvals) > 5:
            lines.append(f"\n... 还有 {len(self.approvals) - 5} 条")

        return [markdown_text("\n".join(lines))]

    def build_actions(self) -> List[Dict]:
        return [
            button_primary("📥 立即处理", "show_pending_approvals", {}),
            button_link("📊 审批中心", "https://vsg-brain.com/approval"),
        ]


class UrgentEmailAlertCard(BaseCard):
    """
    紧急邮件提醒卡片
    """

    def __init__(self, emails: List[Dict[str, Any]]):
        super().__init__(
            title=f"紧急邮件提醒 ({len(emails)} 封)",
            color="red",
            icon="📧"
        )
        self.emails = emails

    def build_content(self) -> List[Dict]:
        if not self.emails:
            return [markdown_text("暂无紧急邮件")]

        lines = ["以下邮件需要您关注：\n"]

        for email in self.emails[:5]:
            subject = email.get("subject", "无主题")[:30]
            sender = email.get("sender_name", email.get("sender", "未知"))
            received = email.get("received_at")
            if isinstance(received, datetime):
                received_str = received.strftime("%m-%d %H:%M")
            else:
                received_str = ""

            lines.append(f"• **{subject}**")
            lines.append(f"  发件人: {sender} | {received_str}")
            lines.append("")

        return [markdown_text("\n".join(lines))]

    def build_actions(self) -> List[Dict]:
        return [
            button_link("📧 邮件情报", "https://vsg-brain.com/email-intel"),
        ]


class SystemAlertCard(BaseCard):
    """
    系统告警卡片
    """

    def __init__(
        self,
        alert_type: str,
        message: str,
        severity: str = "warning",
        details: Dict[str, Any] = None
    ):
        """
        Args:
            alert_type: 告警类型 (service_down, high_load, error_spike, etc.)
            message: 告警消息
            severity: 严重程度 (info, warning, critical)
            details: 详细信息
        """
        severity_config = {
            "info": ("blue", "ℹ️"),
            "warning": ("orange", "⚠️"),
            "critical": ("red", "🚨"),
        }
        color, icon = severity_config.get(severity, ("grey", "❓"))

        super().__init__(
            title=f"系统告警: {alert_type}",
            color=color,
            icon=icon
        )
        self.alert_type = alert_type
        self.message = message
        self.severity = severity
        self.details = details or {}

    def build_content(self) -> List[Dict]:
        content = f"**{self.message}**\n\n"
        content += f"• 告警时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"• 严重程度: {self.severity.upper()}\n"

        if self.details:
            content += "\n**详细信息:**\n"
            for k, v in self.details.items():
                content += f"• {k}: {v}\n"

        return [markdown_text(content)]

    def build_actions(self) -> List[Dict]:
        return [
            button_danger("🔧 立即处理", "handle_system_alert", {"type": self.alert_type}),
        ]


class NoResponseAlertCard(BaseCard):
    """
    任务无响应告警卡片
    提醒 PM 有任务长时间未响应
    """

    def __init__(self, tasks: List[Dict[str, Any]], hours: int = 24):
        super().__init__(
            title=f"任务无响应告警 ({len(tasks)} 个)",
            color="orange",
            icon="🔔"
        )
        self.tasks = tasks
        self.hours = hours

    def build_content(self) -> List[Dict]:
        if not self.tasks:
            return [markdown_text("所有任务都已响应")]

        lines = [f"以下任务分配超过 {self.hours} 小时仍未响应：\n"]

        for task in self.tasks[:10]:
            name = task.get("name", "未命名")
            assignee = task.get("assignee_name", "未分配")
            created = task.get("created_at")
            if isinstance(created, datetime):
                hours_ago = int((datetime.now() - created).total_seconds() / 3600)
                time_str = f"{hours_ago} 小时前"
            else:
                time_str = ""

            lines.append(f"• **{name}**")
            lines.append(f"  负责人: {assignee} | 分配于: {time_str}")
            lines.append("")

        return [markdown_text("\n".join(lines))]

    def build_actions(self) -> List[Dict]:
        return [
            button_primary("📤 发送提醒", "send_task_reminder", {}),
            button_link("📋 项目管理", "https://vsg-brain.com/projects"),
        ]


# ==================== 便捷函数 ====================

def build_task_overdue_alert_card(tasks: List[Dict]) -> Dict:
    """构建任务逾期告警卡片"""
    return TaskOverdueAlertCard(tasks).build()


def build_task_blocked_alert_card(tasks: List[Dict]) -> Dict:
    """构建任务阻塞告警卡片"""
    return TaskBlockedAlertCard(tasks).build()


def build_approval_pending_alert_card(
    approvals: List[Dict],
    approver_name: str = ""
) -> Dict:
    """构建审批待处理提醒卡片"""
    return ApprovalPendingAlertCard(approvals, approver_name).build()


def build_urgent_email_alert_card(emails: List[Dict]) -> Dict:
    """构建紧急邮件提醒卡片"""
    return UrgentEmailAlertCard(emails).build()


def build_system_alert_card(
    alert_type: str,
    message: str,
    severity: str = "warning",
    details: Dict = None
) -> Dict:
    """构建系统告警卡片"""
    return SystemAlertCard(alert_type, message, severity, details).build()


def build_no_response_alert_card(tasks: List[Dict], hours: int = 24) -> Dict:
    """构建无响应告警卡片"""
    return NoResponseAlertCard(tasks, hours).build()
