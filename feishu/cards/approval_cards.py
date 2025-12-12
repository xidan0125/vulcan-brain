"""
审批相关卡片模板
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
    select_static,
    input_field,
    divider,
    note
)


# ==================== 审批类型配置 ====================

APPROVAL_TYPES = {
    "leave": {
        "name": "请假申请",
        "icon": "📅",
        "color": "blue",
        "fields": ["leave_type", "start_date", "end_date", "reason"],
    },
    "expense": {
        "name": "费用报销",
        "icon": "💰",
        "color": "green",
        "fields": ["amount", "category", "description", "attachments"],
    },
    "purchase": {
        "name": "采购申请",
        "icon": "🛒",
        "color": "orange",
        "fields": ["item_name", "quantity", "unit_price", "reason"],
    },
    "overtime": {
        "name": "加班申请",
        "icon": "⏰",
        "color": "purple",
        "fields": ["date", "hours", "reason"],
    },
    "other": {
        "name": "其他申请",
        "icon": "📝",
        "color": "grey",
        "fields": ["title", "content"],
    },
}


class ApprovalRequestCard(BaseCard):
    """
    审批请求卡片
    发送给审批人
    """

    def __init__(self, approval: Dict[str, Any]):
        type_key = approval.get("type", "other")
        type_config = APPROVAL_TYPES.get(type_key, APPROVAL_TYPES["other"])

        super().__init__(
            title=type_config["name"],
            color=type_config["color"],
            icon=type_config["icon"]
        )
        self.approval = approval
        self.type_config = type_config

    def build_content(self) -> List[Dict]:
        approval = self.approval
        created_at = approval.get("created_at")
        if isinstance(created_at, datetime):
            created_str = created_at.strftime("%Y-%m-%d %H:%M")
        else:
            created_str = str(created_at) if created_at else "未知"

        # 构建表单内容显示
        form_data = approval.get("form_data", {})
        form_lines = []
        for key, value in form_data.items():
            # 美化字段名
            key_display = {
                "title": "标题",
                "content": "内容",
                "reason": "原因",
                "amount": "金额",
                "leave_type": "请假类型",
                "start_date": "开始日期",
                "end_date": "结束日期",
                "hours": "时长",
                "item_name": "物品名称",
                "quantity": "数量",
                "unit_price": "单价",
            }.get(key, key)
            form_lines.append(f"**{key_display}**: {value}")

        form_content = "\n".join(form_lines) if form_lines else "无详细信息"

        content = f"""**申请人**: {approval.get('applicant_name', '未知')}
**提交时间**: {created_str}

---

{form_content}"""

        return [markdown_text(content)]

    def build_actions(self) -> List[Dict]:
        approval_id = str(self.approval.get("_id", ""))
        return [
            button_primary("✅ 通过", "approval_approve", {"approval_id": approval_id}),
            button_danger("❌ 拒绝", "approval_reject", {"approval_id": approval_id}),
            button_link("💬 查看详情", f"https://vsg-brain.com/approval/{approval_id}"),
        ]


class ApprovalResultCard(BaseCard):
    """
    审批结果通知卡片
    发送给申请人
    """

    def __init__(
        self,
        approval: Dict[str, Any],
        action: str,
        operator_name: str,
        comment: str = ""
    ):
        type_key = approval.get("type", "other")
        type_config = APPROVAL_TYPES.get(type_key, APPROVAL_TYPES["other"])

        if action == "approved":
            color = "green"
            status_icon = "✅"
            status_text = "已通过"
        elif action == "rejected":
            color = "red"
            status_icon = "❌"
            status_text = "已拒绝"
        else:
            color = "grey"
            status_icon = "⚪"
            status_text = "已处理"

        super().__init__(
            title=f"{type_config['name']} - 审批结果",
            color=color,
            icon=type_config["icon"]
        )
        self.approval = approval
        self.action = action
        self.operator_name = operator_name
        self.comment = comment
        self.status_icon = status_icon
        self.status_text = status_text

    def build_content(self) -> List[Dict]:
        content = f"""**审批结果**: {self.status_icon} {self.status_text}
**审批人**: {self.operator_name}
**处理时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}"""

        if self.comment:
            content += f"\n\n**审批意见**: {self.comment}"

        return [markdown_text(content)]


class ApprovalFormCard(BaseCard):
    """
    审批申请表单卡片
    让用户填写审批信息
    """

    def __init__(self, approval_type: str = "other"):
        type_config = APPROVAL_TYPES.get(approval_type, APPROVAL_TYPES["other"])
        super().__init__(
            title=f"发起{type_config['name']}",
            color=type_config["color"],
            icon=type_config["icon"]
        )
        self.approval_type = approval_type
        self.type_config = type_config

    def build_content(self) -> List[Dict]:
        # 审批类型选择
        type_options = [
            {"text": f"{v['icon']} {v['name']}", "value": k}
            for k, v in APPROVAL_TYPES.items()
        ]

        elements = [
            markdown_text("请填写审批信息："),
            {"tag": "action", "actions": [select_static("选择审批类型", type_options, "approval_type")]},
            {"tag": "action", "actions": [input_field("approval_title", "审批标题")]},
            {"tag": "action", "actions": [input_field("approval_content", "详细说明")]},
        ]

        return elements

    def build_actions(self) -> List[Dict]:
        return [
            button_primary("📤 提交审批", "approval_submit", {}),
            button("❌ 取消", "approval_cancel", {}),
        ]


class MyApprovalsCard(BaseCard):
    """
    待我审批的列表卡片
    """

    def __init__(self, approvals: List[Dict[str, Any]]):
        super().__init__(
            title="待处理审批",
            color="orange",
            icon="📥"
        )
        self.approvals = approvals

    def build_content(self) -> List[Dict]:
        if not self.approvals:
            return [markdown_text("🎉 暂无待处理审批")]

        lines = []
        for a in self.approvals[:10]:
            type_config = APPROVAL_TYPES.get(a.get("type", "other"), APPROVAL_TYPES["other"])
            created = a.get("created_at")
            if isinstance(created, datetime):
                created_str = created.strftime("%m-%d")
            else:
                created_str = ""

            lines.append(
                f"• {type_config['icon']} {a.get('applicant_name', '未知')} - "
                f"{type_config['name']} ({created_str})"
            )

        if len(self.approvals) > 10:
            lines.append(f"\n... 还有 {len(self.approvals) - 10} 条")

        return [markdown_text("\n".join(lines))]

    def build_actions(self) -> List[Dict]:
        return [
            button_primary("🔄 刷新", "refresh_my_approvals", {}),
            button_link("📊 查看全部", "https://vsg-brain.com/approval"),
        ]


class ApprovalSubmittedCard(BaseCard):
    """
    审批已提交确认卡片
    """

    def __init__(self, approval: Dict[str, Any]):
        type_config = APPROVAL_TYPES.get(approval.get("type", "other"), APPROVAL_TYPES["other"])
        super().__init__(
            title="审批已提交",
            color="green",
            icon="✅"
        )
        self.approval = approval
        self.type_config = type_config

    def build_content(self) -> List[Dict]:
        approval = self.approval
        content = f"""您的 **{self.type_config['name']}** 已成功提交。

**审批编号**: {str(approval.get('_id', ''))[-8:]}
**提交时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}

审批人将尽快处理，请耐心等待。"""

        return [markdown_text(content)]


# ==================== 便捷函数 ====================

def build_approval_request_card(approval: Dict) -> Dict:
    """构建审批请求卡片"""
    return ApprovalRequestCard(approval).build()


def build_approval_result_card(
    approval: Dict,
    action: str,
    operator_name: str,
    comment: str = ""
) -> Dict:
    """构建审批结果卡片"""
    return ApprovalResultCard(approval, action, operator_name, comment).build()


def build_approval_form_card(approval_type: str = "other") -> Dict:
    """构建审批表单卡片"""
    return ApprovalFormCard(approval_type).build()


def build_my_approvals_card(approvals: List[Dict]) -> Dict:
    """构建待我审批列表卡片"""
    return MyApprovalsCard(approvals).build()


def build_approval_submitted_card(approval: Dict) -> Dict:
    """构建审批已提交确认卡片"""
    return ApprovalSubmittedCard(approval).build()
