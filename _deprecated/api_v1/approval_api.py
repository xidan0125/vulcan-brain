"""
审批 API - 提供审批相关的 HTTP 端点

端点:
- GET /api/approval/list - 查询审批列表
- GET /api/approval/{id} - 获取审批详情
- POST /api/approval/create - 创建审批
- POST /api/approval/{id}/approve - 通过审批
- POST /api/approval/{id}/reject - 拒绝审批
- POST /api/approval/{id}/cancel - 撤销审批
- GET /api/approval/stats - 统计数据
"""

import logging
import httpx
import json
import os
from config import FEISHU_BRAIN_APP_ID, FEISHU_BRAIN_APP_SECRET
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.approval_bot_service import (
    get_approval_bot_service,
    APPROVAL_TYPES,
    build_approval_request_card,
    build_approval_result_card,
)

logger = logging.getLogger("ApprovalAPI")
router = APIRouter(prefix="/api/approval", tags=["approval"])



async def get_feishu_token():
    """获取飞书 access token"""
    async with httpx.AsyncClient(timeout=30) as hc:
        resp = await hc.post(
            "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": FEISHU_BRAIN_APP_ID, "app_secret": FEISHU_BRAIN_APP_SECRET}
        )
        return resp.json().get("tenant_access_token")


async def send_feishu_card(open_id: str, card: dict):
    """发送飞书卡片给指定用户"""
    token = await get_feishu_token()
    if not token:
        logger.error("[ApprovalAPI] 获取飞书token失败")
        return None

    async with httpx.AsyncClient(timeout=30) as hc:
        resp = await hc.post(
            "https://open.larksuite.com/open-apis/im/v1/messages",
            params={"receive_id_type": "open_id"},
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": open_id,
                "msg_type": "interactive",
                "content": json.dumps(card)
            }
        )
        return resp.json()


async def notify_approvers_via_feishu(approval: dict):
    """通过飞书通知审批人有新的审批请求"""
    approver_ids = approval.get("approver_ids", [])
    if not approver_ids:
        logger.warning(f"[ApprovalAPI] 审批人列表为空，无法通知")
        return

    try:
        # 构建审批请求卡片
        request_card = build_approval_request_card(approval)

        for approver_id in approver_ids:
            result = await send_feishu_card(approver_id, request_card)
            if result and result.get("code") == 0:
                logger.info(f"[ApprovalAPI] 审批请求已发送给审批人 {approver_id}")
            else:
                logger.error(f"[ApprovalAPI] 发送给审批人 {approver_id} 失败: {result}")

    except Exception as e:
        logger.error(f"[ApprovalAPI] 通知审批人失败: {e}")


async def notify_applicant_via_feishu(approval: dict, action: str, approver_name: str, comment: str = ""):
    """通过飞书通知申请人审批结果"""
    applicant_id = approval.get("applicant_id", "")
    if not applicant_id:
        logger.warning(f"[ApprovalAPI] 申请人ID为空，无法通知")
        return

    try:
        result_card = build_approval_result_card(approval, action, approver_name, comment)
        result = await send_feishu_card(applicant_id, result_card)
        if result and result.get("code") == 0:
            logger.info(f"[ApprovalAPI] 审批结果已通知申请人 {applicant_id}")
        else:
            logger.error(f"[ApprovalAPI] 通知申请人失败: {result}")
    except Exception as e:
        logger.error(f"[ApprovalAPI] 飞书通知失败: {e}")



# ===== Pydantic Models =====

class CreateApprovalRequest(BaseModel):
    approval_type: str = "other"
    applicant_id: str
    applicant_name: str
    form_data: dict
    approver_ids: List[str] = []


class ApproveRequest(BaseModel):
    approver_id: str
    approver_name: str
    comment: str = ""


class RejectRequest(BaseModel):
    approver_id: str
    approver_name: str
    reason: str = ""


class CancelRequest(BaseModel):
    applicant_id: str


# ===== API 端点 =====

@router.get("/types")
async def get_approval_types():
    """获取所有审批类型"""
    return {
        "types": [
            {"id": k, "name": v["name"], "icon": v["icon"], "color": v["color"], "fields": v["fields"]}
            for k, v in APPROVAL_TYPES.items()
        ]
    }


@router.get("/list")
async def list_approvals(
    status: Optional[str] = Query(None, description="pending/approved/rejected/canceled"),
    applicant_id: Optional[str] = Query(None),
    approver_id: Optional[str] = Query(None),
    approval_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """查询审批列表"""
    service = get_approval_bot_service()
    approvals = await service.list_approvals(
        status=status,
        applicant_id=applicant_id,
        approver_id=approver_id,
        approval_type=approval_type,
        limit=limit,
        skip=skip,
    )

    # 序列化 datetime
    for a in approvals:
        if "created_at" in a and isinstance(a["created_at"], datetime):
            a["created_at"] = a["created_at"].isoformat()
        if "updated_at" in a and isinstance(a["updated_at"], datetime):
            a["updated_at"] = a["updated_at"].isoformat()
        for rec in a.get("approval_records", []):
            if "timestamp" in rec and isinstance(rec["timestamp"], datetime):
                rec["timestamp"] = rec["timestamp"].isoformat()

    return {"approvals": approvals, "count": len(approvals)}


@router.get("/pending/{approver_id}")
async def get_pending_approvals(approver_id: str):
    """获取某审批人的待处理审批"""
    service = get_approval_bot_service()
    approvals = await service.get_pending_for_approver(approver_id)

    for a in approvals:
        if "created_at" in a and isinstance(a["created_at"], datetime):
            a["created_at"] = a["created_at"].isoformat()
        if "updated_at" in a and isinstance(a["updated_at"], datetime):
            a["updated_at"] = a["updated_at"].isoformat()

    return {"approvals": approvals, "count": len(approvals)}


@router.get("/detail/{approval_id}")
async def get_approval_detail(approval_id: str):
    """获取审批详情"""
    service = get_approval_bot_service()
    approval = await service.get_approval(approval_id)

    if not approval:
        raise HTTPException(status_code=404, detail="审批不存在")

    if "created_at" in approval and isinstance(approval["created_at"], datetime):
        approval["created_at"] = approval["created_at"].isoformat()
    if "updated_at" in approval and isinstance(approval["updated_at"], datetime):
        approval["updated_at"] = approval["updated_at"].isoformat()
    for rec in approval.get("approval_records", []):
        if "timestamp" in rec and isinstance(rec["timestamp"], datetime):
            rec["timestamp"] = rec["timestamp"].isoformat()

    return approval


# Tony 的飞书 open_id (固定审批人)
TONY_OPEN_ID = "ou_441c5dfc10e08385324be3ef7684e6bd"


@router.post("/create")
async def create_approval(req: CreateApprovalRequest):
    """创建审批申请"""
    service = get_approval_bot_service()

    try:
        # 如果没有指定审批人，使用 Tony 作为默认审批人
        approver_ids = req.approver_ids if req.approver_ids else [TONY_OPEN_ID]

        approval = await service.create_approval(
            approval_type=req.approval_type,
            applicant_id=req.applicant_id,
            applicant_name=req.applicant_name,
            form_data=req.form_data,
            approver_ids=approver_ids,
        )

        # 先通知审批人（在序列化之前，因为卡片需要 datetime 对象）
        await notify_approvers_via_feishu(approval)

        # 序列化（给 API 响应用）
        if "created_at" in approval and isinstance(approval["created_at"], datetime):
            approval["created_at"] = approval["created_at"].isoformat()
        if "updated_at" in approval and isinstance(approval["updated_at"], datetime):
            approval["updated_at"] = approval["updated_at"].isoformat()

        return {"success": True, "approval": approval}
    except Exception as e:
        logger.error(f"创建审批失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{approval_id}/approve")
async def approve_approval(approval_id: str, req: ApproveRequest):
    """通过审批"""
    service = get_approval_bot_service()

    try:
        approval = await service.approve(
            approval_id=approval_id,
            approver_id=req.approver_id,
            approver_name=req.approver_name,
            comment=req.comment,
        )
        # 通知申请人
        await notify_applicant_via_feishu(approval, "approved", req.approver_name, req.comment)
        return {"success": True, "message": "审批已通过", "approval_id": approval_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"审批通过失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{approval_id}/reject")
async def reject_approval(approval_id: str, req: RejectRequest):
    """拒绝审批"""
    service = get_approval_bot_service()

    try:
        approval = await service.reject(
            approval_id=approval_id,
            approver_id=req.approver_id,
            approver_name=req.approver_name,
            reason=req.reason,
        )
        # 通知申请人
        await notify_applicant_via_feishu(approval, "rejected", req.approver_name, req.reason)
        return {"success": True, "message": "审批已拒绝", "approval_id": approval_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"审批拒绝失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{approval_id}/cancel")
async def cancel_approval(approval_id: str, req: CancelRequest):
    """撤销审批"""
    service = get_approval_bot_service()

    try:
        approval = await service.cancel(
            approval_id=approval_id,
            applicant_id=req.applicant_id,
        )
        return {"success": True, "message": "审批已撤销", "approval_id": approval_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"审批撤销失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_approval_stats(days: int = Query(7, ge=1, le=365)):
    """获取审批统计"""
    service = get_approval_bot_service()
    stats = await service.get_stats(days=days)
    return stats


# ===== 飞书卡片生成 =====

@router.get("/card/request/{approval_id}")
async def get_approval_request_card(approval_id: str):
    """生成审批请求卡片（用于发送给审批人）"""
    service = get_approval_bot_service()
    approval = await service.get_approval(approval_id)

    if not approval:
        raise HTTPException(status_code=404, detail="审批不存在")

    card = build_approval_request_card(approval)
    return {"card": card}


@router.get("/card/result/{approval_id}")
async def get_approval_result_card(
    approval_id: str,
    action: str = Query(..., description="approved/rejected"),
    operator_name: str = Query(...),
    comment: str = Query(""),
):
    """生成审批结果卡片（用于通知申请人）"""
    service = get_approval_bot_service()
    approval = await service.get_approval(approval_id)

    if not approval:
        raise HTTPException(status_code=404, detail="审批不存在")

    card = build_approval_result_card(approval, action, operator_name, comment)
    return {"card": card}
