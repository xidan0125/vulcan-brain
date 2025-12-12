"""
日报/周报相关卡片模板
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
from .base import (
    BaseCard,
    markdown_text,
    button_primary,
    button,
    button_link,
    divider,
    note
)


class DailyReportCard(BaseCard):
    """
    每日工作日报卡片
    汇总当天的工作情况
    """

    def __init__(
        self,
        report_date: date,
        chat_summary: Dict[str, Any] = None,
        task_stats: Dict[str, Any] = None,
        approval_stats: Dict[str, Any] = None,
        email_highlights: List[str] = None,
        ai_insights: str = ""
    ):
        date_str = report_date.strftime("%Y-%m-%d")
        weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][report_date.weekday()]

        super().__init__(
            title=f"{date_str} ({weekday}) 工作日报",
            color="blue",
            icon="📊"
        )
        self.report_date = report_date
        self.chat_summary = chat_summary or {}
        self.task_stats = task_stats or {}
        self.approval_stats = approval_stats or {}
        self.email_highlights = email_highlights or []
        self.ai_insights = ai_insights

    def build_content(self) -> List[Dict]:
        elements = []

        # 1. 沟通概览
        chat = self.chat_summary
        if chat:
            chat_content = f"""**💬 沟通概览**
• 消息总数: {chat.get('total_messages', 0)} 条
• 活跃群聊: {chat.get('active_chats', 0)} 个
• 重点话题: {', '.join(chat.get('key_topics', ['无'])) or '无'}"""
            elements.append(markdown_text(chat_content))
            elements.append(divider())

        # 2. 任务进展
        task = self.task_stats
        if task:
            task_content = f"""**✅ 任务进展**
• 今日完成: {task.get('completed', 0)} 个
• 进行中: {task.get('in_progress', 0)} 个
• 待开始: {task.get('pending', 0)} 个
• 阻塞中: {task.get('blocked', 0)} 个"""

            if task.get('overdue', 0) > 0:
                task_content += f"\n• ⚠️ 逾期: {task.get('overdue', 0)} 个"

            elements.append(markdown_text(task_content))
            elements.append(divider())

        # 3. 审批情况
        approval = self.approval_stats
        if approval and (approval.get('pending', 0) > 0 or approval.get('processed', 0) > 0):
            approval_content = f"""**📄 审批情况**
• 待处理: {approval.get('pending', 0)} 条
• 今日处理: {approval.get('processed', 0)} 条"""
            elements.append(markdown_text(approval_content))
            elements.append(divider())

        # 4. 邮件要点
        if self.email_highlights:
            email_content = "**📧 邮件要点**\n"
            for i, highlight in enumerate(self.email_highlights[:5], 1):
                email_content += f"• {highlight}\n"
            elements.append(markdown_text(email_content))
            elements.append(divider())

        # 5. AI 洞察
        if self.ai_insights:
            elements.append(markdown_text(f"**🤖 AI 洞察**\n{self.ai_insights}"))

        # 如果没有任何内容
        if not elements:
            elements.append(markdown_text("📭 今日暂无数据"))

        return elements

    def build_actions(self) -> List[Dict]:
        date_str = self.report_date.strftime("%Y-%m-%d")
        return [
            button_link("📊 查看详情", f"https://vsg-brain.com/info-hub?date={date_str}"),
            button_link("📋 项目管理", "https://vsg-brain.com/projects"),
        ]


class WeeklyReportCard(BaseCard):
    """
    周报卡片
    汇总本周工作情况
    """

    def __init__(
        self,
        week_start: date,
        week_end: date,
        task_summary: Dict[str, Any] = None,
        highlights: List[str] = None,
        next_week_focus: List[str] = None,
        team_stats: Dict[str, Any] = None
    ):
        super().__init__(
            title=f"周报 ({week_start.strftime('%m/%d')} - {week_end.strftime('%m/%d')})",
            color="purple",
            icon="📈"
        )
        self.week_start = week_start
        self.week_end = week_end
        self.task_summary = task_summary or {}
        self.highlights = highlights or []
        self.next_week_focus = next_week_focus or []
        self.team_stats = team_stats or {}

    def build_content(self) -> List[Dict]:
        elements = []

        # 1. 本周数据
        task = self.task_summary
        if task:
            summary = f"""**📊 本周数据**
• 完成任务: {task.get('completed', 0)} 个
• 新增任务: {task.get('created', 0)} 个
• 处理审批: {task.get('approvals_processed', 0)} 条
• 沟通消息: {task.get('messages', 0)} 条"""
            elements.append(markdown_text(summary))
            elements.append(divider())

        # 2. 本周亮点
        if self.highlights:
            highlights_content = "**🌟 本周亮点**\n"
            for h in self.highlights[:5]:
                highlights_content += f"• {h}\n"
            elements.append(markdown_text(highlights_content))
            elements.append(divider())

        # 3. 下周重点
        if self.next_week_focus:
            focus_content = "**🎯 下周重点**\n"
            for f in self.next_week_focus[:5]:
                focus_content += f"• {f}\n"
            elements.append(markdown_text(focus_content))
            elements.append(divider())

        # 4. 团队活跃度
        team = self.team_stats
        if team:
            team_content = f"""**👥 团队活跃**
• 活跃成员: {team.get('active_members', 0)} 人
• 响应率: {team.get('response_rate', 0)}%"""
            elements.append(markdown_text(team_content))

        return elements

    def build_actions(self) -> List[Dict]:
        return [
            button_link("📊 信息中心", "https://vsg-brain.com/info-hub"),
        ]


class InfoHubSummaryCard(BaseCard):
    """
    信息中心摘要卡片
    五维信息概览
    """

    def __init__(
        self,
        dimensions: Dict[str, Dict[str, Any]]
    ):
        """
        Args:
            dimensions: {
                "chat": {"status": "normal", "count": 10, "highlights": []},
                "task": {"status": "warning", "count": 5, "highlights": []},
                "approval": {"status": "normal", "count": 2, "highlights": []},
                "email": {"status": "alert", "count": 3, "highlights": []},
                "people": {"status": "normal", "count": 8, "highlights": []},
            }
        """
        super().__init__(
            title="信息中心概览",
            color="blue",
            icon="🎯"
        )
        self.dimensions = dimensions

    def build_content(self) -> List[Dict]:
        status_icons = {
            "normal": "🟢",
            "warning": "🟡",
            "alert": "🔴",
        }

        dimension_names = {
            "chat": "沟通动态",
            "task": "任务进展",
            "approval": "审批流程",
            "email": "邮件情报",
            "people": "人员状态",
        }

        lines = []
        for key, name in dimension_names.items():
            dim = self.dimensions.get(key, {})
            status = dim.get("status", "normal")
            icon = status_icons.get(status, "⚪")
            count = dim.get("count", 0)

            line = f"{icon} **{name}**: {count} 条"
            if dim.get("highlights"):
                line += f" - {dim['highlights'][0]}"

            lines.append(line)

        return [markdown_text("\n".join(lines))]

    def build_actions(self) -> List[Dict]:
        return [
            button_primary("🔄 刷新", "refresh_info_hub", {}),
            button_link("📊 查看详情", "https://vsg-brain.com/info-hub"),
        ]


# ==================== 便捷函数 ====================

def build_daily_report_card(
    report_date: date,
    chat_summary: Dict = None,
    task_stats: Dict = None,
    approval_stats: Dict = None,
    email_highlights: List[str] = None,
    ai_insights: str = ""
) -> Dict:
    """构建日报卡片"""
    return DailyReportCard(
        report_date,
        chat_summary,
        task_stats,
        approval_stats,
        email_highlights,
        ai_insights
    ).build()


def build_weekly_report_card(
    week_start: date,
    week_end: date,
    task_summary: Dict = None,
    highlights: List[str] = None,
    next_week_focus: List[str] = None,
    team_stats: Dict = None
) -> Dict:
    """构建周报卡片"""
    return WeeklyReportCard(
        week_start,
        week_end,
        task_summary,
        highlights,
        next_week_focus,
        team_stats
    ).build()


def build_info_hub_summary_card(dimensions: Dict) -> Dict:
    """构建信息中心摘要卡片"""
    return InfoHubSummaryCard(dimensions).build()
