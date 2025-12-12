"""
Vulcan Brain 审批服务 - 基于飞书机器人

流程：
1. 员工私聊机器人发起审批（或通过Web界面）
2. 系统记录审批请求，发卡片给审批人
3. 审批人点击卡片操作（通过/拒绝）
4. 系统通知申请人结果

审批类型：
- leave: 请假
- expense: 报销
- purchase: 采购
- overtime: 加班
- other: 其他
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger("ApprovalBot")
_service = None

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "vulcan_brain")

_client = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(MONGO_URI)
        _db = _client[DB_NAME]
    return _db


# ===== 审批类型配置 (从新模块导入) =====
try:
    from feishu.cards.approval_cards import APPROVAL_TYPES
except ImportError:
    # 兼容：如果新模块不可用，使用本地定义
    APPROVAL_TYPES = {
        "leave": {
            "name": "请假申请",
            "icon": "📅",
            "color": "blue",
            "fields": ["leave_type", "start_date", "end_date", "reason"],
            "approvers": ["manager"],
        },
        "expense": {
            "name": "费用报销",
            "icon": "💰",
            "color": "green",
            "fields": ["amount", "category", "description", "attachments"],
            "approvers": ["finance", "manager"],
        },
        "purchase": {
            "name": "采购申请",
            "icon": "🛒",
            "color": "orange",
            "fields": ["item_name", "quantity", "unit_price", "reason"],
            "approvers": ["manager"],
        },
        "overtime": {
            "name": "加班申请",
            "icon": "⏰",
            "color": "purple",
            "fields": ["date", "hours", "reason"],
            "approvers": ["manager"],
        },
        "other": {
            "name": "其他申请",
            "icon": "📝",
            "color": "grey",
            "fields": ["title", "content"],
            "approvers": ["manager"],
        },
    }


class ApprovalBotService:
    """审批机器人服务"""

    def __init__(self):
        self.db = get_db()
        self.collection = self.db.bot_approvals

    async def create_approval(
        self,
        approval_type: str,
        applicant_id: str,  # 飞书 open_id
        applicant_name: str,
        form_data: Dict[str, Any],
        approver_ids: List[str] = None,  # 指定审批人的 open_id 列表
    ) -> Dict:
        """
        创建审批申请

        Args:
            approval_type: 审批类型 (leave/expense/purchase/overtime/other)
            applicant_id: 申请人飞书 open_id
            applicant_name: 申请人姓名
            form_data: 表单数据
            approver_ids: 审批人列表，不指定则使用默认配置

        Returns:
            创建的审批记录
        """
        type_config = APPROVAL_TYPES.get(approval_type, APPROVAL_TYPES["other"])

        approval = {
            "type": approval_type,
            "type_name": type_config["name"],
            "type_icon": type_config["icon"],
            "applicant_id": applicant_id,
            "applicant_name": applicant_name,
            "form_data": form_data,
            "approver_ids": approver_ids or [],
            "status": "pending",  # pending/approved/rejected/canceled
            "current_step": 0,
            "approval_records": [],  # 审批记录
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        result = await self.collection.insert_one(approval)
        approval["_id"] = str(result.inserted_id)

        logger.info(f"[ApprovalBot] 创建审批: {approval['_id']} - {type_config['name']} by {applicant_name}")
        return approval

    async def get_approval(self, approval_id: str) -> Optional[Dict]:
        """获取审批详情"""
        try:
            doc = await self.collection.find_one({"_id": ObjectId(approval_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except:
            return None

    async def list_approvals(
        self,
        status: str = None,
        applicant_id: str = None,
        approver_id: str = None,
        approval_type: str = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict]:
        """查询审批列表"""
        query = {}

        if status:
            query["status"] = status
        if applicant_id:
            query["applicant_id"] = applicant_id
        if approver_id:
            query["approver_ids"] = approver_id
        if approval_type:
            query["type"] = approval_type

        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)

        return results

    async def get_pending_for_approver(self, approver_id: str) -> List[Dict]:
        """获取某审批人的待处理审批"""
        return await self.list_approvals(status="pending", approver_id=approver_id)

    async def approve(
        self,
        approval_id: str,
        approver_id: str,
        approver_name: str,
        comment: str = "",
    ) -> Dict:
        """通过审批"""
        approval = await self.get_approval(approval_id)
        if not approval:
            raise ValueError("审批不存在")

        if approval["status"] != "pending":
            raise ValueError(f"审批状态不是待处理: {approval['status']}")

        # 记录审批
        record = {
            "action": "approve",
            "approver_id": approver_id,
            "approver_name": approver_name,
            "comment": comment,
            "timestamp": datetime.now(),
        }

        await self.collection.update_one(
            {"_id": ObjectId(approval_id)},
            {
                "$set": {
                    "status": "approved",
                    "updated_at": datetime.now(),
                },
                "$push": {"approval_records": record},
            },
        )

        approval["status"] = "approved"
        approval["approval_records"].append(record)

        logger.info(f"[ApprovalBot] 审批通过: {approval_id} by {approver_name}")
        return approval

    async def reject(
        self,
        approval_id: str,
        approver_id: str,
        approver_name: str,
        reason: str = "",
    ) -> Dict:
        """拒绝审批"""
        approval = await self.get_approval(approval_id)
        if not approval:
            raise ValueError("审批不存在")

        if approval["status"] != "pending":
            raise ValueError(f"审批状态不是待处理: {approval['status']}")

        record = {
            "action": "reject",
            "approver_id": approver_id,
            "approver_name": approver_name,
            "reason": reason,
            "timestamp": datetime.now(),
        }

        await self.collection.update_one(
            {"_id": ObjectId(approval_id)},
            {
                "$set": {
                    "status": "rejected",
                    "updated_at": datetime.now(),
                },
                "$push": {"approval_records": record},
            },
        )

        approval["status"] = "rejected"
        approval["approval_records"].append(record)

        logger.info(f"[ApprovalBot] 审批拒绝: {approval_id} by {approver_name} - {reason}")
        return approval

    async def cancel(self, approval_id: str, applicant_id: str) -> Dict:
        """申请人撤销审批"""
        approval = await self.get_approval(approval_id)
        if not approval:
            raise ValueError("审批不存在")

        if approval["applicant_id"] != applicant_id:
            raise ValueError("只有申请人可以撤销")

        if approval["status"] != "pending":
            raise ValueError("只能撤销待处理的审批")

        await self.collection.update_one(
            {"_id": ObjectId(approval_id)},
            {
                "$set": {
                    "status": "canceled",
                    "updated_at": datetime.now(),
                },
            },
        )

        approval["status"] = "canceled"
        logger.info(f"[ApprovalBot] 审批撤销: {approval_id}")
        return approval

    async def get_stats(self, days: int = 7) -> Dict:
        """获取统计数据"""
        since = datetime.now() - timedelta(days=days)

        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                }
            },
        ]

        results = {}
        async for doc in self.collection.aggregate(pipeline):
            results[doc["_id"]] = doc["count"]

        # 按类型统计
        type_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": "$type",
                    "count": {"$sum": 1},
                }
            },
        ]

        by_type = {}
        async for doc in self.collection.aggregate(type_pipeline):
            by_type[doc["_id"]] = doc["count"]

        return {
            "total": sum(results.values()),
            "pending": results.get("pending", 0),
            "approved": results.get("approved", 0),
            "rejected": results.get("rejected", 0),
            "canceled": results.get("canceled", 0),
            "by_type": by_type,
            "period_days": days,
        }


# ===== 飞书卡片生成 (使用新模块) =====

def build_approval_request_card(approval: Dict) -> Dict:
    """生成审批请求卡片（发给审批人）"""
    try:
        from feishu.cards.approval_cards import build_approval_request_card as _build
        return _build(approval)
    except ImportError:
        # 兼容：如果新模块不可用，使用本地实现
        return _build_approval_request_card_legacy(approval)


def build_approval_result_card(approval: Dict, action: str, operator_name: str, comment: str = "") -> Dict:
    """生成审批结果卡片（发给申请人）"""
    try:
        from feishu.cards.approval_cards import build_approval_result_card as _build
        return _build(approval, action, operator_name, comment)
    except ImportError:
        return _build_approval_result_card_legacy(approval, action, operator_name, comment)


def build_approval_submit_card(approval_type: str = "other") -> Dict:
    """生成审批提交表单卡片（发给申请人填写）"""
    try:
        from feishu.cards.approval_cards import build_approval_form_card as _build
        return _build(approval_type)
    except ImportError:
        return _build_approval_submit_card_legacy(approval_type)


# ===== Legacy 实现 (兼容) =====

def _build_approval_request_card_legacy(approval: Dict) -> Dict:
    """Legacy: 生成审批请求卡片"""
    type_config = APPROVAL_TYPES.get(approval["type"], APPROVAL_TYPES["other"])

    form_lines = []
    for key, value in approval.get("form_data", {}).items():
        form_lines.append(f"**{key}**: {value}")

    form_content = "\n".join(form_lines) if form_lines else "无详细信息"

    created_at = approval.get("created_at")
    if isinstance(created_at, datetime):
        created_str = created_at.strftime('%Y-%m-%d %H:%M')
    else:
        created_str = str(created_at)[:16] if created_at else ""

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{type_config['icon']} {type_config['name']}"},
            "template": type_config["color"],
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**申请人**: {approval['applicant_name']}\n**提交时间**: {created_str}\n\n---\n\n{form_content}",
                },
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 通过"},
                        "type": "primary",
                        "value": {"action": "bot_approval_approve", "approval_id": str(approval["_id"])},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                        "type": "danger",
                        "value": {"action": "bot_approval_reject", "approval_id": str(approval["_id"])},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "💬 查看详情"},
                        "type": "default",
                        "url": f"https://vsg-brain.com/approval/{approval['_id']}",
                    },
                ],
            },
        ],
    }


def _build_approval_result_card_legacy(approval: Dict, action: str, operator_name: str, comment: str = "") -> Dict:
    """Legacy: 生成审批结果卡片"""
    type_config = APPROVAL_TYPES.get(approval["type"], APPROVAL_TYPES["other"])

    if action == "approved":
        header_template = "green"
        status_text = "✅ 已通过"
    elif action == "rejected":
        header_template = "red"
        status_text = "❌ 已拒绝"
    else:
        header_template = "grey"
        status_text = "⚪ 已处理"

    content = f"**审批结果**: {status_text}\n**审批人**: {operator_name}"
    if comment:
        content += f"\n**备注**: {comment}"

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{type_config['icon']} {type_config['name']} - 审批结果"},
            "template": header_template,
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": content},
            },
        ],
    }


def _build_approval_submit_card_legacy(approval_type: str = "other") -> Dict:
    """Legacy: 生成审批提交表单卡片"""
    type_config = APPROVAL_TYPES.get(approval_type, APPROVAL_TYPES["other"])

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{type_config['icon']} 发起{type_config['name']}"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "form",
                "name": "approval_form_submit",
                "elements": [
                    {
                        "tag": "input",
                        "name": "approval_title",
                        "placeholder": {"tag": "plain_text", "content": "请输入审批标题"},
                    },
                    {
                        "tag": "input",
                        "name": "approval_content",
                        "placeholder": {"tag": "plain_text", "content": "请输入详细说明"},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "提交审批"},
                        "type": "primary",
                        "action_type": "form_submit",
                        "name": "submit_btn",
                    },
                ],
            },
        ],
    }


# ===== 单例获取 =====

def get_approval_bot_service() -> ApprovalBotService:
    global _service
    if _service is None:
        _service = ApprovalBotService()
    return _service
