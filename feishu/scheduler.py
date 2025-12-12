"""
飞书定时任务调度器
负责定时推送日报、告警等
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any

logger = logging.getLogger("FeishuScheduler")


class FeishuScheduler:
    """飞书定时任务调度器"""

    def __init__(self):
        self._sdk = None
        self._running = False
        self._tasks = []

    @property
    def sdk(self):
        if self._sdk is None:
            from feishu.sdk import get_feishu_sdk
            self._sdk = get_feishu_sdk()
        return self._sdk

    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("[Scheduler] 调度器已在运行")
            return

        self._running = True
        logger.info("[Scheduler] 调度器启动")

        # 启动各个定时任务
        self._tasks = [
            asyncio.create_task(self._daily_report_task()),
            asyncio.create_task(self._overdue_alert_task()),
            asyncio.create_task(self._no_response_alert_task()),
            asyncio.create_task(self._approval_reminder_task()),
        ]

    async def stop(self):
        """停止调度器"""
        self._running = False
        for task in self._tasks:
            task.cancel()
        logger.info("[Scheduler] 调度器停止")

    # ==================== 日报推送 ====================

    async def _daily_report_task(self):
        """每日日报推送任务 (每天 18:00)"""
        while self._running:
            try:
                now = datetime.now()
                # 计算下一个 18:00
                target = now.replace(hour=18, minute=0, second=0, microsecond=0)
                if now >= target:
                    target += timedelta(days=1)

                wait_seconds = (target - now).total_seconds()
                logger.info(f"[Scheduler] 日报任务将在 {wait_seconds/3600:.1f} 小时后执行")

                await asyncio.sleep(wait_seconds)

                if self._running:
                    await self.send_daily_report()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Scheduler] 日报任务异常: {e}")
                await asyncio.sleep(3600)  # 出错后等 1 小时重试

    async def send_daily_report(self, target_users: List[str] = None):
        """
        发送日报

        Args:
            target_users: 接收者 open_id 列表，为空则发送给管理员
        """
        logger.info("[Scheduler] 开始生成日报...")

        try:
            # 收集数据
            today = date.today()
            chat_summary = await self._get_chat_summary(today)
            task_stats = await self._get_task_stats(today)
            approval_stats = await self._get_approval_stats(today)
            email_highlights = await self._get_email_highlights(today)

            # 生成 AI 洞察 (可选)
            ai_insights = ""

            # 构建卡片
            from feishu.cards.report_cards import build_daily_report_card
            card = build_daily_report_card(
                report_date=today,
                chat_summary=chat_summary,
                task_stats=task_stats,
                approval_stats=approval_stats,
                email_highlights=email_highlights,
                ai_insights=ai_insights,
            )

            # 发送
            if not target_users:
                # 默认发送给 Tony
                target_users = ["ou_441c5dfc10e08385324be3ef7684e6bd"]

            for user_id in target_users:
                await self.sdk.send_card(user_id, card)
                logger.info(f"[Scheduler] 日报已发送给 {user_id}")

        except Exception as e:
            logger.error(f"[Scheduler] 日报发送失败: {e}")

    async def _get_chat_summary(self, day: date) -> Dict:
        """获取聊天摘要"""
        try:
            from services.message_store import get_message_store
            store = get_message_store()
            # 简化：返回基本统计
            return {
                "total_messages": 0,
                "active_chats": 0,
                "key_topics": [],
            }
        except:
            return {}

    async def _get_task_stats(self, day: date) -> Dict:
        """获取任务统计"""
        try:
            from services.project_store import get_project_store
            store = get_project_store()
            tasks = await store.list_tasks()

            completed = len([t for t in tasks if t.get("status") == "completed"])
            in_progress = len([t for t in tasks if t.get("status") == "in_progress"])
            pending = len([t for t in tasks if t.get("status") == "pending"])
            blocked = len([t for t in tasks if t.get("status") == "blocked"])

            # 计算逾期
            now = datetime.now()
            overdue = len([
                t for t in tasks
                if t.get("deadline") and isinstance(t.get("deadline"), datetime)
                and t.get("deadline") < now and t.get("status") != "completed"
            ])

            return {
                "completed": completed,
                "in_progress": in_progress,
                "pending": pending,
                "blocked": blocked,
                "overdue": overdue,
            }
        except Exception as e:
            logger.error(f"[Scheduler] 获取任务统计失败: {e}")
            return {}

    async def _get_approval_stats(self, day: date) -> Dict:
        """获取审批统计"""
        try:
            from services.approval_bot_service import get_approval_bot_service
            service = get_approval_bot_service()
            stats = await service.get_stats(days=1)
            return {
                "pending": stats.get("pending", 0),
                "processed": stats.get("approved", 0) + stats.get("rejected", 0),
            }
        except:
            return {}

    async def _get_email_highlights(self, day: date) -> List[str]:
        """获取邮件要点"""
        # TODO: 从邮件情报服务获取
        return []

    # ==================== 逾期告警 ====================

    async def _overdue_alert_task(self):
        """逾期任务告警 (每 4 小时检查一次)"""
        while self._running:
            try:
                await asyncio.sleep(4 * 3600)  # 4 小时

                if self._running:
                    await self.check_overdue_tasks()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Scheduler] 逾期告警任务异常: {e}")

    async def check_overdue_tasks(self):
        """检查并发送逾期告警"""
        try:
            from services.project_store import get_project_store
            store = get_project_store()
            tasks = await store.list_tasks()

            now = datetime.now()
            overdue_tasks = [
                t for t in tasks
                if t.get("deadline") and isinstance(t.get("deadline"), datetime)
                and t.get("deadline") < now and t.get("status") not in ["completed", "cancelled"]
            ]

            if overdue_tasks:
                from feishu.cards.alert_cards import build_task_overdue_alert_card
                card = build_task_overdue_alert_card(overdue_tasks)

                # 发送给管理员
                await self.sdk.send_card("ou_441c5dfc10e08385324be3ef7684e6bd", card)
                logger.info(f"[Scheduler] 逾期告警已发送，共 {len(overdue_tasks)} 个任务")

        except Exception as e:
            logger.error(f"[Scheduler] 逾期检查失败: {e}")

    # ==================== 无响应告警 ====================

    async def _no_response_alert_task(self):
        """无响应任务告警 (每 6 小时检查一次)"""
        while self._running:
            try:
                await asyncio.sleep(6 * 3600)

                if self._running:
                    await self.check_no_response_tasks()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Scheduler] 无响应告警任务异常: {e}")

    async def check_no_response_tasks(self, hours: int = 24):
        """检查无响应任务"""
        try:
            from services.project_store import get_project_store
            store = get_project_store()
            tasks = await store.list_tasks()

            now = datetime.now()
            threshold = now - timedelta(hours=hours)

            no_response = [
                t for t in tasks
                if t.get("created_at") and isinstance(t.get("created_at"), datetime)
                and t.get("created_at") < threshold
                and t.get("lifecycle_status") in [None, "assigned", "pending"]
                and t.get("status") not in ["completed", "cancelled"]
            ]

            if no_response:
                from feishu.cards.alert_cards import build_no_response_alert_card
                card = build_no_response_alert_card(no_response, hours)

                await self.sdk.send_card("ou_441c5dfc10e08385324be3ef7684e6bd", card)
                logger.info(f"[Scheduler] 无响应告警已发送，共 {len(no_response)} 个任务")

        except Exception as e:
            logger.error(f"[Scheduler] 无响应检查失败: {e}")

    # ==================== 审批提醒 ====================

    async def _approval_reminder_task(self):
        """审批提醒 (每天 10:00 和 15:00)"""
        while self._running:
            try:
                now = datetime.now()

                # 计算下一个提醒时间 (10:00 或 15:00)
                if now.hour < 10:
                    target = now.replace(hour=10, minute=0, second=0)
                elif now.hour < 15:
                    target = now.replace(hour=15, minute=0, second=0)
                else:
                    target = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0)

                wait_seconds = (target - now).total_seconds()
                await asyncio.sleep(wait_seconds)

                if self._running:
                    await self.send_approval_reminders()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Scheduler] 审批提醒任务异常: {e}")

    async def send_approval_reminders(self):
        """发送审批提醒"""
        try:
            from services.approval_bot_service import get_approval_bot_service
            service = get_approval_bot_service()

            # 获取所有待处理审批
            pending = await service.list_approvals(status="pending")

            if not pending:
                return

            # 按审批人分组
            by_approver = {}
            for a in pending:
                for approver_id in a.get("approver_ids", []):
                    if approver_id not in by_approver:
                        by_approver[approver_id] = []
                    by_approver[approver_id].append(a)

            # 发送提醒
            from feishu.cards.alert_cards import build_approval_pending_alert_card
            for approver_id, approvals in by_approver.items():
                if len(approvals) >= 1:  # 有待处理审批就提醒
                    card = build_approval_pending_alert_card(approvals)
                    await self.sdk.send_card(approver_id, card)
                    logger.info(f"[Scheduler] 审批提醒已发送给 {approver_id}，共 {len(approvals)} 条")

        except Exception as e:
            logger.error(f"[Scheduler] 审批提醒失败: {e}")


# ==================== 单例 ====================

_scheduler_instance = None

def get_feishu_scheduler() -> FeishuScheduler:
    """获取调度器单例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = FeishuScheduler()
    return _scheduler_instance


async def start_scheduler():
    """启动调度器"""
    scheduler = get_feishu_scheduler()
    await scheduler.start()


async def stop_scheduler():
    """停止调度器"""
    scheduler = get_feishu_scheduler()
    await scheduler.stop()
