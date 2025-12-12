"""
任务相关卡片模板
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import (
    BaseCard,
    markdown_text,
    button_primary,
    button_danger,
    button,
    button_link,
    select_static,
    input_field,
    divider,
    note
)


class TaskAssignmentCard(BaseCard):
    """
    任务分配卡片
    发送给任务负责人，让其确认接受任务
    """

    def __init__(self, task: Dict[str, Any]):
        super().__init__(
            title=f"新任务: {task.get('name', '未命名任务')}",
            color="blue",
            icon="📋"
        )
        self.task = task

    def build_content(self) -> List[Dict]:
        task = self.task
        deadline = task.get("deadline", "未设置")
        if isinstance(deadline, datetime):
            deadline = deadline.strftime("%Y-%m-%d")

        priority_map = {"high": "🔴 高", "medium": "🟡 中", "low": "🟢 低"}
        priority = priority_map.get(task.get("priority", "medium"), "🟡 中")

        content = f"""**项目**: {task.get('project_name', '未分配项目')}
**负责人**: {task.get('assignee_name', '未分配')}
**截止日期**: {deadline}
**优先级**: {priority}

---

**任务描述**:
{task.get('description', '无描述')}"""

        return [markdown_text(content)]

    def build_actions(self) -> List[Dict]:
        task_id = str(self.task.get("_id", ""))
        return [
            button_primary("✅ 接受任务", "task_accept", {"task_id": task_id}),
            button_danger("⚠️ 有困难", "task_difficulty", {"task_id": task_id}),
            button("❓ 需要澄清", "task_clarify", {"task_id": task_id}),
        ]


class TaskProgressCard(BaseCard):
    """
    任务进度提醒卡片
    定期发送，提醒更新进度
    """

    def __init__(self, task: Dict[str, Any]):
        super().__init__(
            title=f"进度提醒: {task.get('name', '')}",
            color="orange",
            icon="⏰"
        )
        self.task = task

    def build_content(self) -> List[Dict]:
        task = self.task
        deadline = task.get("deadline", "未设置")
        if isinstance(deadline, datetime):
            deadline = deadline.strftime("%Y-%m-%d")

        status_map = {
            "pending": "⏳ 待开始",
            "in_progress": "🔄 进行中",
            "blocked": "🚫 阻塞",
            "completed": "✅ 已完成"
        }
        status = status_map.get(task.get("status", "pending"), "⏳ 待开始")

        content = f"""**当前状态**: {status}
**截止日期**: {deadline}
**已用时间**: {self._calc_elapsed_days()} 天

请更新您的任务进度。"""

        return [markdown_text(content)]

    def _calc_elapsed_days(self) -> int:
        created = self.task.get("created_at")
        if isinstance(created, datetime):
            return (datetime.now() - created).days
        return 0

    def build_actions(self) -> List[Dict]:
        task_id = str(self.task.get("_id", ""))
        return [
            button_primary("📝 更新进度", "task_update_progress", {"task_id": task_id}),
            button("✅ 标记完成", "task_complete", {"task_id": task_id}),
            button_danger("🚫 申请延期", "task_delay", {"task_id": task_id}),
        ]


class TaskOverdueCard(BaseCard):
    """
    任务逾期告警卡片
    """

    def __init__(self, task: Dict[str, Any]):
        super().__init__(
            title=f"逾期告警: {task.get('name', '')}",
            color="red",
            icon="🚨"
        )
        self.task = task

    def build_content(self) -> List[Dict]:
        task = self.task
        deadline = task.get("deadline", "未设置")
        if isinstance(deadline, datetime):
            overdue_days = (datetime.now() - deadline).days
            deadline = deadline.strftime("%Y-%m-%d")
        else:
            overdue_days = 0

        content = f"""**任务已逾期 {overdue_days} 天！**

**原定截止**: {deadline}
**负责人**: {task.get('assignee_name', '未分配')}

请立即处理或说明原因。"""

        return [markdown_text(content)]

    def build_actions(self) -> List[Dict]:
        task_id = str(self.task.get("_id", ""))
        return [
            button_primary("🔥 立即处理", "task_handle_overdue", {"task_id": task_id}),
            button("📝 说明原因", "task_explain_overdue", {"task_id": task_id}),
            button_danger("🗓️ 申请延期", "task_delay", {"task_id": task_id}),
        ]


class MyTasksCard(BaseCard):
    """
    我的任务列表卡片
    """

    def __init__(self, tasks: List[Dict[str, Any]], user_name: str = ""):
        super().__init__(
            title=f"{user_name} 的任务列表" if user_name else "我的任务",
            color="blue",
            icon="📋"
        )
        self.tasks = tasks

    def build_content(self) -> List[Dict]:
        if not self.tasks:
            return [markdown_text("🎉 暂无待办任务")]

        # 按状态分组
        pending = [t for t in self.tasks if t.get("status") == "pending"]
        in_progress = [t for t in self.tasks if t.get("status") == "in_progress"]
        blocked = [t for t in self.tasks if t.get("status") == "blocked"]

        lines = []

        if in_progress:
            lines.append("**🔄 进行中**")
            for t in in_progress[:5]:
                lines.append(f"• {t.get('name', '未命名')}")
            lines.append("")

        if pending:
            lines.append("**⏳ 待开始**")
            for t in pending[:5]:
                lines.append(f"• {t.get('name', '未命名')}")
            lines.append("")

        if blocked:
            lines.append("**🚫 阻塞中**")
            for t in blocked[:3]:
                lines.append(f"• {t.get('name', '未命名')}")

        summary = f"\n---\n**共 {len(self.tasks)} 个任务**"
        lines.append(summary)

        return [markdown_text("\n".join(lines))]

    def build_actions(self) -> List[Dict]:
        return [
            button_primary("🔄 刷新", "refresh_my_tasks", {}),
            button("📝 更新状态", "show_update_status_form", {}),
            button_link("📊 查看详情", "https://vsg-brain.com/projects"),
        ]


class TaskUpdateFormCard(BaseCard):
    """
    任务状态更新表单卡片
    """

    def __init__(self, tasks: List[Dict[str, Any]]):
        super().__init__(
            title="更新任务状态",
            color="blue",
            icon="📝"
        )
        self.tasks = tasks

    def build_content(self) -> List[Dict]:
        if not self.tasks:
            return [markdown_text("暂无可更新的任务")]

        # 任务选择下拉框
        task_options = [
            {"text": t.get("name", "未命名"), "value": str(t.get("_id", ""))}
            for t in self.tasks
        ]

        # 状态选择下拉框
        status_options = [
            {"text": "⏳ 待开始", "value": "pending"},
            {"text": "🔄 进行中", "value": "in_progress"},
            {"text": "🚫 阻塞", "value": "blocked"},
            {"text": "✅ 已完成", "value": "completed"},
        ]

        elements = [
            markdown_text("选择任务和新状态："),
            {"tag": "action", "actions": [select_static("选择任务", task_options, "task_id")]},
            {"tag": "action", "actions": [select_static("选择状态", status_options, "new_status")]},
            {"tag": "action", "actions": [input_field("progress_note", "备注说明（可选）")]},
        ]

        return elements

    def build_actions(self) -> List[Dict]:
        return [
            button_primary("📤 提交更新", "submit_task_status_update", {}),
            button("❌ 取消", "cancel_update", {}),
        ]


class TaskCompletedCard(BaseCard):
    """
    任务完成通知卡片
    发送给任务创建者/PM
    """

    def __init__(self, task: Dict[str, Any], completed_by: str):
        super().__init__(
            title=f"任务已完成: {task.get('name', '')}",
            color="green",
            icon="✅"
        )
        self.task = task
        self.completed_by = completed_by

    def build_content(self) -> List[Dict]:
        task = self.task
        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M")

        content = f"""**完成人**: {self.completed_by}
**完成时间**: {completed_at}
**项目**: {task.get('project_name', '未分配')}

任务已标记为完成，请确认。"""

        return [markdown_text(content)]

    def build_actions(self) -> List[Dict]:
        task_id = str(self.task.get("_id", ""))
        return [
            button_primary("✅ 确认完成", "task_confirm_complete", {"task_id": task_id}),
            button_danger("🔙 打回重做", "task_reopen", {"task_id": task_id}),
        ]


# ==================== 便捷函数 ====================

def build_task_assignment_card(task: Dict) -> Dict:
    """构建任务分配卡片"""
    return TaskAssignmentCard(task).build()


def build_task_progress_card(task: Dict) -> Dict:
    """构建进度提醒卡片"""
    return TaskProgressCard(task).build()


def build_task_overdue_card(task: Dict) -> Dict:
    """构建逾期告警卡片"""
    return TaskOverdueCard(task).build()


def build_my_tasks_card(tasks: List[Dict], user_name: str = "") -> Dict:
    """构建我的任务列表卡片"""
    return MyTasksCard(tasks, user_name).build()


def build_task_update_form_card(tasks: List[Dict]) -> Dict:
    """构建任务更新表单卡片"""
    return TaskUpdateFormCard(tasks).build()


def build_task_completed_card(task: Dict, completed_by: str) -> Dict:
    """构建任务完成通知卡片"""
    return TaskCompletedCard(task, completed_by).build()
