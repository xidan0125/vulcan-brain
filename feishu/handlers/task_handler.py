"""
任务相关事件处理器
处理任务卡片的回调事件
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger("TaskHandler")

# Tony (PM) 的 open_id
PM_OPEN_ID = "ou_441c5dfc10e08385324be3ef7684e6bd"


class TaskHandler:
    """任务事件处理器"""

    def __init__(self):
        self._sdk = None
        self._task_service = None

    @property
    def sdk(self):
        if self._sdk is None:
            from feishu.sdk import get_feishu_sdk
            self._sdk = get_feishu_sdk()
        return self._sdk

    @property
    def task_service(self):
        if self._task_service is None:
            from services.project_store import get_project_store
            self._task_service = get_project_store()
        return self._task_service

    async def _notify_pm(self, task: Dict, event_type: str, user_name: str, note: str = ""):
        """
        通知 PM 任务状态变化

        Args:
            task: 任务数据
            event_type: 事件类型 (accepted/difficulty/clarify/progress/completed/delay)
            user_name: 操作用户名
            note: 附加说明
        """
        task_name = task.get("name", "未命名任务")

        messages = {
            "accepted": f"✅ **{user_name}** 已接受任务「{task_name}」",
            "difficulty": f"⚠️ **{user_name}** 反馈任务「{task_name}」有困难，请关注",
            "clarify": f"❓ **{user_name}** 需要澄清任务「{task_name}」的详情",
            "progress": f"📊 **{user_name}** 更新了任务「{task_name}」的进度" + (f"\n{note}" if note else ""),
            "completed": f"🎉 **{user_name}** 完成了任务「{task_name}」",
            "delay": f"📝 **{user_name}** 申请延期任务「{task_name}」",
        }

        message = messages.get(event_type, f"任务「{task_name}」状态变化")

        try:
            await self.sdk.send_text(PM_OPEN_ID, message, bot="brain")
            logger.info(f"[TaskHandler] PM 通知已发送: {event_type}")
        except Exception as e:
            logger.error(f"[TaskHandler] PM 通知发送失败: {e}")

    async def handle_accept(self, event: Dict[str, Any]) -> Dict:
        """
        处理任务接受事件

        更新任务状态 + 通知 PM
        """
        value = self._extract_value(event)
        task_id = value.get("task_id", "")
        open_id = self._extract_open_id(event)

        logger.info(f"[TaskHandler] 任务接受: task_id={task_id}, user={open_id}")

        try:
            # 获取用户名
            user_name = await self.sdk.get_user_name(open_id)

            # 更新任务状态
            update_data = {
                "lifecycle_status": "acknowledged",
                f"response_status.{open_id}": "accepted",
                f"response_notes.{open_id}": "已接受任务",
                "response_at": datetime.now(),
            }

            await self.task_service.update_task(task_id, update_data)

            # 获取任务详情
            task = await self.task_service.get_task(task_id)

            # 发送确认消息给员工
            await self.sdk.send_text(
                open_id,
                "✅ 任务已接受！加油完成吧~",
                bot="pmo"
            )

            # 通知 PM
            if task:
                await self._notify_pm(task, "accepted", user_name)

            logger.info(f"[TaskHandler] 任务接受处理完成: {task_id}")

        except Exception as e:
            logger.error(f"[TaskHandler] 任务接受处理失败: {e}")
            await self.sdk.send_text(open_id, f"❌ 操作失败: {e}", bot="pmo")

        return {"code": 0}

    async def handle_difficulty(self, event: Dict[str, Any]) -> Dict:
        """
        处理任务有困难事件

        更新任务状态 + 立即通知 PM
        """
        value = self._extract_value(event)
        task_id = value.get("task_id", "")
        open_id = self._extract_open_id(event)

        logger.info(f"[TaskHandler] 任务困难: task_id={task_id}, user={open_id}")

        try:
            user_name = await self.sdk.get_user_name(open_id)

            update_data = {
                "lifecycle_status": "needs_attention",
                f"response_status.{open_id}": "has_difficulty",
                f"response_notes.{open_id}": "反馈有困难",
                "response_at": datetime.now(),
            }

            await self.task_service.update_task(task_id, update_data)
            task = await self.task_service.get_task(task_id)

            # 通知员工
            await self.sdk.send_text(
                open_id,
                "⚠️ 已记录您的困难反馈，PM 会尽快与您沟通。",
                bot="pmo"
            )

            # 立即通知 PM (重要告警)
            if task:
                await self._notify_pm(task, "difficulty", user_name)

        except Exception as e:
            logger.error(f"[TaskHandler] 任务困难处理失败: {e}")

        return {"code": 0}

    async def handle_clarify(self, event: Dict[str, Any]) -> Dict:
        """
        处理任务需澄清事件

        更新任务状态 + 通知 PM
        """
        value = self._extract_value(event)
        task_id = value.get("task_id", "")
        open_id = self._extract_open_id(event)

        logger.info(f"[TaskHandler] 任务澄清: task_id={task_id}, user={open_id}")

        try:
            user_name = await self.sdk.get_user_name(open_id)

            update_data = {
                "lifecycle_status": "needs_attention",
                f"response_status.{open_id}": "needs_clarification",
                f"response_notes.{open_id}": "需要澄清任务详情",
                "response_at": datetime.now(),
            }

            await self.task_service.update_task(task_id, update_data)
            task = await self.task_service.get_task(task_id)

            await self.sdk.send_text(
                open_id,
                "❓ 已记录您的澄清请求，PM 会尽快与您沟通细节。",
                bot="pmo"
            )

            if task:
                await self._notify_pm(task, "clarify", user_name)

        except Exception as e:
            logger.error(f"[TaskHandler] 任务澄清处理失败: {e}")

        return {"code": 0}

    async def handle_progress_update(self, event: Dict[str, Any]) -> Dict:
        """
        处理进度更新事件
        """
        value = self._extract_value(event)
        form_value = self._extract_form_value(event)
        task_id = value.get("task_id", "") or form_value.get("task_id", "")
        open_id = self._extract_open_id(event)

        new_status = form_value.get("new_status", "in_progress")
        progress_note = form_value.get("progress_note", "")

        logger.info(f"[TaskHandler] 进度更新: task_id={task_id}, status={new_status}")

        try:
            user_name = await self.sdk.get_user_name(open_id)

            update_data = {
                "status": new_status,
                "lifecycle_status": "in_progress" if new_status == "in_progress" else "acknowledged",
                f"response_status.{open_id}": "progress_updated",
                f"response_notes.{open_id}": progress_note or f"状态更新为: {new_status}",
                "response_at": datetime.now(),
            }

            if new_status == "completed":
                update_data["lifecycle_status"] = "completed"
                update_data["completed_at"] = datetime.now()

            await self.task_service.update_task(task_id, update_data)
            task = await self.task_service.get_task(task_id)

            status_text = {
                "pending": "待开始",
                "in_progress": "进行中",
                "blocked": "阻塞",
                "completed": "已完成"
            }.get(new_status, new_status)

            await self.sdk.send_text(
                open_id,
                f"✅ 任务状态已更新为: {status_text}",
                bot="pmo"
            )

            # 通知 PM (完成是重要事件)
            if task:
                note = f"状态: {status_text}" + (f"\n备注: {progress_note}" if progress_note else "")
                if new_status == "completed":
                    await self._notify_pm(task, "completed", user_name)
                elif new_status == "blocked":
                    await self._notify_pm(task, "difficulty", user_name, "任务被阻塞")
                else:
                    await self._notify_pm(task, "progress", user_name, note)

        except Exception as e:
            logger.error(f"[TaskHandler] 进度更新失败: {e}")
            await self.sdk.send_text(open_id, f"❌ 更新失败: {e}", bot="pmo")

        return {"code": 0}

    async def handle_complete(self, event: Dict[str, Any]) -> Dict:
        """
        处理任务完成事件
        """
        value = self._extract_value(event)
        task_id = value.get("task_id", "")
        open_id = self._extract_open_id(event)

        logger.info(f"[TaskHandler] 任务完成: task_id={task_id}")

        try:
            user_name = await self.sdk.get_user_name(open_id)

            update_data = {
                "status": "completed",
                "lifecycle_status": "completed",
                f"response_status.{open_id}": "completed",
                "response_at": datetime.now(),
                "completed_at": datetime.now(),
            }

            await self.task_service.update_task(task_id, update_data)
            task = await self.task_service.get_task(task_id)

            await self.sdk.send_text(
                open_id,
                "🎉 恭喜！任务已标记完成！",
                bot="pmo"
            )

            # 通知 PM
            if task:
                await self._notify_pm(task, "completed", user_name)

        except Exception as e:
            logger.error(f"[TaskHandler] 任务完成处理失败: {e}")

        return {"code": 0}

    async def handle_delay_request(self, event: Dict[str, Any]) -> Dict:
        """
        处理延期申请事件
        """
        value = self._extract_value(event)
        task_id = value.get("task_id", "")
        open_id = self._extract_open_id(event)

        logger.info(f"[TaskHandler] 延期申请: task_id={task_id}")

        try:
            user_name = await self.sdk.get_user_name(open_id)

            update_data = {
                "lifecycle_status": "needs_attention",
                f"response_status.{open_id}": "delay_requested",
                f"response_notes.{open_id}": "申请延期",
                "response_at": datetime.now(),
            }

            await self.task_service.update_task(task_id, update_data)
            task = await self.task_service.get_task(task_id)

            await self.sdk.send_text(
                open_id,
                "📝 延期申请已提交，PM 会尽快审批。",
                bot="pmo"
            )

            # 通知 PM
            if task:
                await self._notify_pm(task, "delay", user_name)

        except Exception as e:
            logger.error(f"[TaskHandler] 延期申请处理失败: {e}")

        return {"code": 0}


    async def handle_send_reminder(self, event: Dict[str, Any]) -> Dict:
        """
        处理发送催办事件
        PM 点击告警卡片上的"发送提醒"按钮
        """
        open_id = self._extract_open_id(event)

        logger.info(f"[TaskHandler] 发送催办: operator={open_id}")

        try:
            # 获取所有未响应任务
            tasks = await self.task_service.list_tasks()

            no_response = [
                t for t in tasks
                if t.get("lifecycle_status") in [None, "assigned", "pending"]
                and t.get("status") not in ["completed", "cancelled"]
                and t.get("assignee_feishu_id")
            ]

            if not no_response:
                await self.sdk.send_text(open_id, "✅ 暂无需要催办的任务", bot="brain")
                return {"code": 0}

            # 发送提醒给每个负责人
            reminded_count = 0
            for task in no_response:
                assignee_id = task.get("assignee_feishu_id")
                task_name = task.get("name", "未命名任务")
                deadline = task.get("deadline", "")
                if hasattr(deadline, 'strftime'):
                    deadline = deadline.strftime("%Y-%m-%d")
                else:
                    deadline = str(deadline)[:10] if deadline else "未设置"

                reminder_msg = f"📢 **任务提醒**\n\n"
                reminder_msg += f"任务: {task_name}\n"
                reminder_msg += f"截止日期: {deadline}\n\n"
                reminder_msg += f"请及时响应或更新进度~"

                await self.sdk.send_text(assignee_id, reminder_msg, bot="pmo")
                reminded_count += 1

            # 反馈给 PM
            await self.sdk.send_text(
                open_id,
                f"✅ 已发送 {reminded_count} 条催办提醒",
                bot="brain"
            )

            logger.info(f"[TaskHandler] 催办已发送: {reminded_count} 条")

        except Exception as e:
            logger.error(f"[TaskHandler] 发送催办失败: {e}")
            await self.sdk.send_text(open_id, f"❌ 发送催办失败: {e}", bot="brain")

        return {"code": 0}

    async def handle_view_overdue_tasks(self, event: Dict[str, Any]) -> Dict:
        """
        处理查看逾期任务事件
        """
        open_id = self._extract_open_id(event)

        try:
            tasks = await self.task_service.list_tasks()
            now = datetime.now()

            overdue = [
                t for t in tasks
                if t.get("deadline") and isinstance(t.get("deadline"), datetime)
                and t.get("deadline") < now
                and t.get("status") not in ["completed", "cancelled"]
            ]

            if not overdue:
                await self.sdk.send_text(open_id, "🎉 暂无逾期任务", bot="brain")
                return {"code": 0}

            # 构建详情
            lines = [f"📋 **逾期任务列表** ({len(overdue)} 个)\n"]
            for t in overdue[:15]:
                name = t.get("name", "未命名")
                assignee = t.get("assignee_name", "未分配")
                deadline = t.get("deadline")
                overdue_days = (now - deadline).days if deadline else 0
                lines.append(f"• {name}")
                lines.append(f"  负责人: {assignee} | 逾期 {overdue_days} 天")

            if len(overdue) > 15:
                lines.append(f"\n... 还有 {len(overdue) - 15} 个")

            await self.sdk.send_text(open_id, "\n".join(lines), bot="brain")

        except Exception as e:
            logger.error(f"[TaskHandler] 查看逾期任务失败: {e}")

        return {"code": 0}


    # ==================== 辅助方法 ====================

    def _extract_value(self, event: Dict) -> Dict:
        """提取卡片按钮的 value"""
        action = event.get("action", {})
        return action.get("value", {})

    def _extract_form_value(self, event: Dict) -> Dict:
        """提取表单值"""
        action = event.get("action", {})
        return action.get("form_value", {})

    def _extract_open_id(self, event: Dict) -> str:
        """提取操作用户的 open_id"""
        operator = event.get("operator", {})
        return operator.get("open_id", "")


# ==================== 单例获取 ====================

_handler_instance = None


def get_task_handler() -> TaskHandler:
    """获取 TaskHandler 单例"""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = TaskHandler()
    return _handler_instance
