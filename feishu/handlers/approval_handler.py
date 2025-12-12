"""
审批相关事件处理器
处理审批卡片的回调事件
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger("ApprovalHandler")

# Tony 的 open_id (默认审批人)
TONY_OPEN_ID = "ou_441c5dfc10e08385324be3ef7684e6bd"


class ApprovalHandler:
    """审批事件处理器"""

    def __init__(self):
        self._sdk = None
        self._approval_service = None

    @property
    def sdk(self):
        if self._sdk is None:
            from feishu.sdk import get_feishu_sdk
            self._sdk = get_feishu_sdk()
        return self._sdk

    @property
    def approval_service(self):
        if self._approval_service is None:
            from services.approval_bot_service import get_approval_bot_service
            self._approval_service = get_approval_bot_service()
        return self._approval_service

    async def handle_submit(self, event: Dict[str, Any]) -> Dict:
        """
        处理审批提交事件

        从表单中获取数据，创建审批记录，通知审批人
        """
        form_value = self._extract_form_value(event)
        open_id = self._extract_open_id(event)

        approval_type = form_value.get("approval_type", "other")
        title = form_value.get("approval_title", "")
        content = form_value.get("approval_content", "")

        logger.info(f"[ApprovalHandler] 审批提交: type={approval_type}, user={open_id}")

        try:
            # 获取用户名
            user_name = await self.sdk.get_user_name(open_id)

            # 创建审批记录
            approval = await self.approval_service.create_approval(
                approval_type=approval_type,
                applicant_id=open_id,
                applicant_name=user_name,
                form_data={"title": title, "content": content},
                approver_ids=[TONY_OPEN_ID],  # 默认审批人
            )

            logger.info(f"[ApprovalHandler] 审批已创建: {approval['_id']}")

            # 发送确认卡片给申请人
            from feishu.cards.approval_cards import build_approval_submitted_card
            submitted_card = build_approval_submitted_card(approval)
            await self.sdk.send_card(open_id, submitted_card)

            # 发送审批请求卡片给审批人
            from feishu.cards.approval_cards import build_approval_request_card
            request_card = build_approval_request_card(approval)
            await self.sdk.send_card(TONY_OPEN_ID, request_card)

            logger.info(f"[ApprovalHandler] 审批通知已发送给 Tony")

        except Exception as e:
            logger.error(f"[ApprovalHandler] 审批提交失败: {e}")
            await self.sdk.send_text(open_id, f"❌ 审批提交失败: {e}")

        return {"code": 0}

    async def handle_approve(self, event: Dict[str, Any]) -> Dict:
        """
        处理审批通过事件
        """
        value = self._extract_value(event)
        form_value = self._extract_form_value(event)
        approval_id = value.get("approval_id", "")
        open_id = self._extract_open_id(event)
        comment = form_value.get("comment", "")

        logger.info(f"[ApprovalHandler] 审批通过: approval_id={approval_id}")

        try:
            # 获取审批人名称
            approver_name = await self.sdk.get_user_name(open_id)

            # 更新审批状态
            approval = await self.approval_service.approve(
                approval_id=approval_id,
                approver_id=open_id,
                approver_name=approver_name,
                comment=comment,
            )

            # 通知申请人
            applicant_id = approval.get("applicant_id", "")
            if applicant_id:
                from feishu.cards.approval_cards import build_approval_result_card
                result_card = build_approval_result_card(
                    approval, "approved", approver_name, comment
                )
                await self.sdk.send_card(applicant_id, result_card)

            # 给审批人发送确认
            await self.sdk.send_text(open_id, "✅ 审批已通过")

            logger.info(f"[ApprovalHandler] 审批通过处理完成")

        except ValueError as e:
            logger.error(f"[ApprovalHandler] 审批通过失败: {e}")
            await self.sdk.send_text(open_id, f"❌ 操作失败: {e}")
        except Exception as e:
            logger.error(f"[ApprovalHandler] 审批通过异常: {e}")

        return {"code": 0}

    async def handle_reject(self, event: Dict[str, Any]) -> Dict:
        """
        处理审批拒绝事件
        """
        value = self._extract_value(event)
        form_value = self._extract_form_value(event)
        approval_id = value.get("approval_id", "")
        open_id = self._extract_open_id(event)
        reason = form_value.get("reason", "") or form_value.get("comment", "")

        logger.info(f"[ApprovalHandler] 审批拒绝: approval_id={approval_id}")

        try:
            approver_name = await self.sdk.get_user_name(open_id)

            approval = await self.approval_service.reject(
                approval_id=approval_id,
                approver_id=open_id,
                approver_name=approver_name,
                reason=reason,
            )

            # 通知申请人
            applicant_id = approval.get("applicant_id", "")
            if applicant_id:
                from feishu.cards.approval_cards import build_approval_result_card
                result_card = build_approval_result_card(
                    approval, "rejected", approver_name, reason
                )
                await self.sdk.send_card(applicant_id, result_card)

            await self.sdk.send_text(open_id, "❌ 审批已拒绝")

        except ValueError as e:
            logger.error(f"[ApprovalHandler] 审批拒绝失败: {e}")
            await self.sdk.send_text(open_id, f"❌ 操作失败: {e}")
        except Exception as e:
            logger.error(f"[ApprovalHandler] 审批拒绝异常: {e}")

        return {"code": 0}

    async def handle_cancel(self, event: Dict[str, Any]) -> Dict:
        """
        处理取消审批表单
        """
        open_id = self._extract_open_id(event)
        await self.sdk.send_text(open_id, "已取消")
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

def get_approval_handler() -> ApprovalHandler:
    """获取 ApprovalHandler 单例"""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = ApprovalHandler()
    return _handler_instance
