"""
机器人菜单事件处理器
处理用户点击机器人菜单的事件
"""

import logging
from typing import Dict, Any

logger = logging.getLogger("MenuHandler")


class MenuHandler:
    """菜单事件处理器"""

    def __init__(self):
        self._sdk = None
        self._task_service = None
        self._approval_service = None

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

    @property
    def approval_service(self):
        if self._approval_service is None:
            from services.approval_bot_service import get_approval_bot_service
            self._approval_service = get_approval_bot_service()
        return self._approval_service

    # ==================== 任务相关菜单 ====================

    async def show_my_tasks(self, event: Dict[str, Any]) -> Dict:
        """
        显示我的任务列表

        菜单: 我的任务 (my_tasks)
        """
        open_id = self._extract_open_id(event)
        logger.info(f"[MenuHandler] 显示我的任务: user={open_id}")

        try:
            # 获取用户的任务
            tasks = await self.task_service.get_tasks_by_assignee(open_id)

            # 过滤未完成的任务
            active_tasks = [
                t for t in tasks
                if t.get("status") not in ["completed", "cancelled"]
            ]

            # 获取用户名
            user_name = await self.sdk.get_user_name(open_id)

            # 构建卡片
            from feishu.cards.task_cards import build_my_tasks_card
            card = build_my_tasks_card(active_tasks, user_name)

            await self.sdk.send_card(open_id, card, bot="brain")

        except Exception as e:
            logger.error(f"[MenuHandler] 显示任务失败: {e}")
            await self.sdk.send_text(open_id, f"❌ 获取任务失败: {e}", bot="brain")

        return {"code": 0}

    async def show_update_status_form(self, event: Dict[str, Any]) -> Dict:
        """
        显示任务状态更新表单

        菜单: 更新状态 (update_status)
        """
        open_id = self._extract_open_id(event)
        logger.info(f"[MenuHandler] 显示更新表单: user={open_id}")

        try:
            # 获取用户的进行中任务
            tasks = await self.task_service.get_tasks_by_assignee(open_id)
            active_tasks = [
                t for t in tasks
                if t.get("status") not in ["completed", "cancelled"]
            ]

            if not active_tasks:
                await self.sdk.send_text(
                    open_id,
                    "🎉 您当前没有进行中的任务",
                    bot="brain"
                )
                return {"code": 0}

            # 构建更新表单卡片
            from feishu.cards.task_cards import build_task_update_form_card
            card = build_task_update_form_card(active_tasks)

            await self.sdk.send_card(open_id, card, bot="brain")

        except Exception as e:
            logger.error(f"[MenuHandler] 显示更新表单失败: {e}")
            await self.sdk.send_text(open_id, f"❌ 获取任务失败: {e}", bot="brain")

        return {"code": 0}

    async def refresh_my_tasks(self, event: Dict[str, Any]) -> Dict:
        """刷新我的任务 (卡片按钮回调)"""
        return await self.show_my_tasks(event)

    # ==================== 审批相关菜单 ====================

    async def show_approval_form(self, event: Dict[str, Any]) -> Dict:
        """
        显示审批申请表单

        菜单: 发起审批 (start_approval)
        """
        open_id = self._extract_open_id(event)
        logger.info(f"[MenuHandler] 显示审批表单: user={open_id}")

        try:
            from feishu.cards.approval_cards import build_approval_form_card
            card = build_approval_form_card()
            await self.sdk.send_card(open_id, card, bot="brain")

        except Exception as e:
            logger.error(f"[MenuHandler] 显示审批表单失败: {e}")
            await self.sdk.send_text(open_id, f"❌ 加载失败: {e}", bot="brain")

        return {"code": 0}

    async def show_my_approvals(self, event: Dict[str, Any]) -> Dict:
        """
        显示待我审批的列表

        菜单: 我的审批 (my_approvals)
        """
        open_id = self._extract_open_id(event)
        logger.info(f"[MenuHandler] 显示待审批: user={open_id}")

        try:
            # 获取待审批列表
            approvals = await self.approval_service.get_pending_for_approver(open_id)

            from feishu.cards.approval_cards import build_my_approvals_card
            card = build_my_approvals_card(approvals)

            await self.sdk.send_card(open_id, card, bot="brain")

        except Exception as e:
            logger.error(f"[MenuHandler] 显示待审批失败: {e}")
            await self.sdk.send_text(open_id, f"❌ 获取失败: {e}", bot="brain")

        return {"code": 0}

    async def refresh_my_approvals(self, event: Dict[str, Any]) -> Dict:
        """刷新待审批列表 (卡片按钮回调)"""
        return await self.show_my_approvals(event)

    # ==================== 其他菜单 ====================

    async def show_daily_report(self, event: Dict[str, Any]) -> Dict:
        """
        显示今日日报

        菜单: 今日日报 (daily_report)
        """
        open_id = self._extract_open_id(event)
        logger.info(f"[MenuHandler] 显示日报: user={open_id}")

        try:
            from feishu.scheduler import get_feishu_scheduler
            scheduler = get_feishu_scheduler()

            # 发送日报给当前用户
            await scheduler.send_daily_report(target_users=[open_id])

            logger.info(f"[MenuHandler] 日报已发送给 {open_id}")

        except Exception as e:
            logger.error(f"[MenuHandler] 显示日报失败: {e}")
            await self.sdk.send_text(
                open_id,
                f"❌ 获取日报失败: {e}\n\n您可以访问 https://vsg-brain.com/info-hub 查看信息中心。",
                bot="brain"
            )

        return {"code": 0}

    async def start_chat(self, event: Dict[str, Any]) -> Dict:
        """
        启动 AI 对话

        菜单: 对话助手 (start_chat)
        """
        open_id = self._extract_open_id(event)
        logger.info(f"[MenuHandler] 启动对话: user={open_id}")

        await self.sdk.send_text(
            open_id,
            "👋 您好！我是 Vulcan Brain 智能助手。\n\n"
            "您可以直接向我发送消息进行对话，或访问 https://vsg-brain.com/gemini 使用完整功能。",
            bot="brain"
        )

        return {"code": 0}

    # ==================== 辅助方法 ====================

    def _extract_open_id(self, event: Dict) -> str:
        """从不同事件结构中提取 open_id"""
        # 菜单事件结构
        operator = event.get("operator", {})
        operator_id = operator.get("operator_id", {})
        if operator_id:
            return operator_id.get("open_id", "")

        # 卡片回调结构
        return operator.get("open_id", "")


# ==================== 单例获取 ====================

_handler_instance = None

def get_menu_handler() -> MenuHandler:
    """获取 MenuHandler 单例"""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = MenuHandler()
    return _handler_instance
