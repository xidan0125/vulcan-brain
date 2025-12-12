"""
Vulcan Brain 统一通知服务

所有飞书通知的统一入口，确保：
1. 通知不遗漏
2. 格式统一
3. 便于追踪和调试
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("NotificationService")

# Tony (PM/Admin) 的 open_id
PM_OPEN_ID = "ou_441c5dfc10e08385324be3ef7684e6bd"


class NotificationService:
    """统一通知服务"""

    def __init__(self):
        self._sdk = None

    @property
    def sdk(self):
        if self._sdk is None:
            from feishu.sdk import get_feishu_sdk
            self._sdk = get_feishu_sdk()
        return self._sdk

    # ==================== 通用通知 ====================

    async def notify_user(
        self,
        user_id: str,
        title: str,
        content: str,
        card: Dict = None,
        bot: str = "brain"
    ) -> bool:
        """
        发送通知给用户

        Args:
            user_id: 用户 open_id
            title: 通知标题 (用于日志)
            content: 文本内容 (如果没有 card)
            card: 卡片内容 (可选)
            bot: 使用哪个机器人

        Returns:
            是否发送成功
        """
        try:
            if card:
                await self.sdk.send_card(user_id, card, bot=bot)
            else:
                await self.sdk.send_text(user_id, content, bot=bot)

            logger.info(f"[Notify] 已通知 {user_id}: {title}")
            return True
        except Exception as e:
            logger.error(f"[Notify] 通知失败 {user_id}: {title} - {e}")
            return False

    async def notify_pm(
        self,
        title: str,
        content: str,
        card: Dict = None,
        urgent: bool = False
    ) -> bool:
        """
        通知 PM (Tony)

        Args:
            title: 通知标题
            content: 内容
            card: 卡片 (可选)
            urgent: 是否紧急 (会加前缀)
        """
        if urgent:
            content = f"🚨 **紧急** 🚨\n\n{content}"

        return await self.notify_user(PM_OPEN_ID, title, content, card)

    # ==================== 任务通知 ====================

    async def notify_task_assigned(
        self,
        task: Dict,
        assignee_id: str,
        project_name: str = ""
    ) -> bool:
        """
        通知：任务已分配给你

        Args:
            task: 任务数据
            assignee_id: 被分配人 open_id
            project_name: 项目名称
        """
        from feishu.cards.task_cards import build_task_assignment_card
        card = build_task_assignment_card(task, project_name)

        return await self.notify_user(
            assignee_id,
            f"任务分配: {task.get('name', '')}",
            "",
            card,
            bot="pmo"
        )

    async def notify_task_accepted(
        self,
        task: Dict,
        user_name: str
    ) -> bool:
        """通知 PM：某人接受了任务"""
        task_name = task.get("name", "未命名任务")
        content = f"✅ **{user_name}** 已接受任务「{task_name}」"

        return await self.notify_pm(f"任务接受: {task_name}", content)

    async def notify_task_difficulty(
        self,
        task: Dict,
        user_name: str,
        note: str = ""
    ) -> bool:
        """通知 PM：某人反馈任务有困难 (紧急)"""
        task_name = task.get("name", "未命名任务")
        content = f"⚠️ **{user_name}** 反馈任务「{task_name}」有困难"
        if note:
            content += f"\n\n备注: {note}"

        return await self.notify_pm(f"任务困难: {task_name}", content, urgent=True)

    async def notify_task_blocked(
        self,
        task: Dict,
        user_name: str,
        reason: str = ""
    ) -> bool:
        """通知 PM：任务被阻塞 (紧急)"""
        task_name = task.get("name", "未命名任务")
        content = f"🚧 **{user_name}** 报告任务「{task_name}」被阻塞"
        if reason:
            content += f"\n\n原因: {reason}"

        return await self.notify_pm(f"任务阻塞: {task_name}", content, urgent=True)

    async def notify_task_completed(
        self,
        task: Dict,
        user_name: str
    ) -> bool:
        """通知 PM：任务已完成"""
        task_name = task.get("name", "未命名任务")
        content = f"🎉 **{user_name}** 完成了任务「{task_name}」"

        return await self.notify_pm(f"任务完成: {task_name}", content)

    async def notify_task_progress(
        self,
        task: Dict,
        user_name: str,
        new_status: str,
        note: str = ""
    ) -> bool:
        """通知 PM：任务进度更新"""
        task_name = task.get("name", "未命名任务")
        status_text = {
            "pending": "待开始",
            "in_progress": "进行中",
            "blocked": "阻塞",
            "completed": "已完成"
        }.get(new_status, new_status)

        content = f"📊 **{user_name}** 更新了任务「{task_name}」\n状态: {status_text}"
        if note:
            content += f"\n备注: {note}"

        return await self.notify_pm(f"任务进度: {task_name}", content)

    async def notify_task_delay_request(
        self,
        task: Dict,
        user_name: str,
        reason: str = ""
    ) -> bool:
        """通知 PM：申请延期"""
        task_name = task.get("name", "未命名任务")
        content = f"📝 **{user_name}** 申请延期任务「{task_name}」"
        if reason:
            content += f"\n\n原因: {reason}"

        return await self.notify_pm(f"延期申请: {task_name}", content)

    # ==================== 审批通知 ====================

    async def notify_approval_submitted(
        self,
        approval: Dict,
        applicant_id: str
    ) -> bool:
        """通知申请人：审批已提交"""
        from feishu.cards.approval_cards import build_approval_submitted_card
        card = build_approval_submitted_card(approval)

        return await self.notify_user(
            applicant_id,
            f"审批已提交: {approval.get('type_name', '')}",
            "",
            card
        )

    async def notify_approval_request(
        self,
        approval: Dict,
        approver_id: str
    ) -> bool:
        """通知审批人：有新审批待处理"""
        from feishu.cards.approval_cards import build_approval_request_card
        card = build_approval_request_card(approval)

        return await self.notify_user(
            approver_id,
            f"新审批: {approval.get('type_name', '')}",
            "",
            card
        )

    async def notify_approval_result(
        self,
        approval: Dict,
        applicant_id: str,
        action: str,
        operator_name: str,
        comment: str = ""
    ) -> bool:
        """通知申请人：审批结果"""
        from feishu.cards.approval_cards import build_approval_result_card
        card = build_approval_result_card(approval, action, operator_name, comment)

        action_text = "通过" if action == "approved" else "拒绝"
        return await self.notify_user(
            applicant_id,
            f"审批{action_text}: {approval.get('type_name', '')}",
            "",
            card
        )

    # ==================== 告警通知 ====================

    async def notify_overdue_tasks(
        self,
        tasks: List[Dict]
    ) -> bool:
        """通知 PM：有逾期任务"""
        if not tasks:
            return True

        from feishu.cards.alert_cards import build_task_overdue_alert_card
        card = build_task_overdue_alert_card(tasks)

        return await self.notify_pm(
            f"逾期告警: {len(tasks)} 个任务",
            "",
            card,
            urgent=True
        )

    async def notify_no_response_tasks(
        self,
        tasks: List[Dict],
        hours: int = 24
    ) -> bool:
        """通知 PM：有任务长时间未响应"""
        if not tasks:
            return True

        from feishu.cards.alert_cards import build_no_response_alert_card
        card = build_no_response_alert_card(tasks, hours)

        return await self.notify_pm(
            f"无响应告警: {len(tasks)} 个任务",
            "",
            card
        )

    async def notify_approval_pending(
        self,
        approvals: List[Dict],
        approver_id: str
    ) -> bool:
        """通知审批人：有待处理审批"""
        if not approvals:
            return True

        from feishu.cards.alert_cards import build_approval_pending_alert_card
        card = build_approval_pending_alert_card(approvals)

        return await self.notify_user(
            approver_id,
            f"审批提醒: {len(approvals)} 条待处理",
            "",
            card
        )

    # ==================== 催办通知 ====================

    async def send_task_reminder(
        self,
        task: Dict,
        assignee_id: str,
        message: str = ""
    ) -> bool:
        """发送任务催办"""
        task_name = task.get("name", "未命名任务")
        deadline = task.get("deadline", "")
        if deadline and len(str(deadline)) > 10:
            deadline = str(deadline)[:10]

        content = f"📢 **任务提醒**\n\n"
        content += f"任务: {task_name}\n"
        if deadline:
            content += f"截止日期: {deadline}\n"
        if message:
            content += f"\nPM 留言: {message}"

        return await self.notify_user(
            assignee_id,
            f"任务催办: {task_name}",
            content,
            bot="pmo"
        )

    async def send_bulk_task_reminder(
        self,
        tasks: List[Dict]
    ) -> Dict[str, bool]:
        """批量发送任务催办"""
        results = {}
        for task in tasks:
            assignee_id = task.get("assignee_feishu_id")
            if assignee_id:
                task_id = task.get("id", task.get("_id", ""))
                results[task_id] = await self.send_task_reminder(task, assignee_id)
        return results


# ==================== 单例 ====================

_service_instance = None


def get_notification_service() -> NotificationService:
    """获取通知服务单例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = NotificationService()
    return _service_instance
