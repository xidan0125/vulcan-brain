"""
Email Intelligence V2.0 - Entity Merge Queue API
实体合并审核队列 API 端点
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, Body
from pydantic import BaseModel
from bson import ObjectId
import logging

logger = logging.getLogger("EntityMergeAPI")
router = APIRouter(prefix="/entity-merge", tags=["Entity Merge Queue"])


# ============ Request/Response Models ============

class ReviewRequest(BaseModel):
    """审核请求"""
    decision: str  # APPROVE or REJECT
    reviewer: str = "admin"
    reason: Optional[str] = None
    notes: Optional[str] = None


class BulkReviewRequest(BaseModel):
    """批量审核请求"""
    queue_ids: List[str]
    decision: str
    reviewer: str = "admin"
    reason: Optional[str] = None


# ============ Helper Functions ============

async def get_db():
    """获取数据库连接"""
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    return client.vulcan_brain


def serialize_doc(doc):
    """序列化 MongoDB 文档"""
    if doc is None:
        return None
    if isinstance(doc, dict):
        result = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                result[k] = str(v)
            elif isinstance(v, datetime):
                result[k] = v.isoformat()
            elif isinstance(v, dict):
                result[k] = serialize_doc(v)
            elif isinstance(v, list):
                result[k] = [serialize_doc(item) if isinstance(item, dict) else item for item in v]
            else:
                result[k] = v
        return result
    return doc


# ============ API Endpoints ============

@router.get("/queue")
async def get_merge_queue(
    status: str = Query("PENDING", description="状态过滤"),
    party_type: Optional[str] = Query(None, description="Party 类型 (COMPANY/PERSON)"),
    min_confidence: float = Query(0.75, description="最小置信度"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """
    获取实体合并审核队列

    返回待审核的合并建议列表
    """
    db = await get_db()

    # 构建查询
    query = {"status": status}
    if min_confidence:
        query["match_evidence.confidence"] = {"$gte": min_confidence}

    # 获取总数
    total = await db.entity_merge_queue.count_documents(query)

    # 获取列表
    cursor = db.entity_merge_queue.find(query).sort([
        ("match_evidence.confidence", -1),
        ("created_at", -1)
    ]).skip(skip).limit(limit)

    items = []
    async for doc in cursor:
        # 如果有 party_type 过滤，需要查询 source party
        if party_type:
            source_party = await db.parties.find_one(
                {"_id": ObjectId(doc["merge_suggestion"]["source_party_id"])}
            )
            if source_party and source_party.get("party_type") != party_type:
                continue
        items.append(serialize_doc(doc))

    # 统计信息
    stats = {
        "total": total,
        "pending": await db.entity_merge_queue.count_documents({"status": "PENDING"}),
        "approved": await db.entity_merge_queue.count_documents({"status": "APPROVED"}),
        "rejected": await db.entity_merge_queue.count_documents({"status": "REJECTED"}),
        "auto_merged": await db.entity_merge_queue.count_documents({"status": "AUTO_MERGED"}),
    }

    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "skip": skip,
            "limit": limit,
            "stats": stats
        }
    }


@router.get("/queue/{queue_id}")
async def get_merge_detail(queue_id: str):
    """
    获取单条合并建议详情

    包含 source 和 target party 的完整信息
    """
    db = await get_db()

    # 获取队列记录
    queue_item = await db.entity_merge_queue.find_one({"_id": ObjectId(queue_id)})
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    # 获取 source party 详情
    source_party = await db.parties.find_one({
        "_id": ObjectId(queue_item["merge_suggestion"]["source_party_id"])
    })

    # 获取 target party 详情
    target_party = await db.parties.find_one({
        "_id": ObjectId(queue_item["merge_suggestion"]["target_party_id"])
    })

    return {
        "success": True,
        "data": {
            "queue_item": serialize_doc(queue_item),
            "source_party": serialize_doc(source_party),
            "target_party": serialize_doc(target_party)
        }
    }


@router.post("/queue/{queue_id}/review")
async def review_merge(queue_id: str, request: ReviewRequest):
    """
    审核合并建议

    - APPROVE: 批准合并 (source 变成 target 的 alias)
    - REJECT: 拒绝合并 (保持独立)
    """
    db = await get_db()

    # 获取队列记录
    queue_item = await db.entity_merge_queue.find_one({"_id": ObjectId(queue_id)})
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    if queue_item["status"] != "PENDING":
        raise HTTPException(status_code=400, detail=f"Item already {queue_item['status']}")

    now = datetime.utcnow()

    if request.decision == "APPROVE":
        # 执行合并
        source_id = ObjectId(queue_item["merge_suggestion"]["source_party_id"])
        target_id = ObjectId(queue_item["merge_suggestion"]["target_party_id"])

        # 获取 source party
        source_party = await db.parties.find_one({"_id": source_id})
        if not source_party:
            raise HTTPException(status_code=404, detail="Source party not found")

        # 更新 source 为 alias
        await db.parties.update_one(
            {"_id": source_id},
            {
                "$set": {
                    "entity_resolution.canonical_id": target_id,
                    "entity_resolution.is_canonical": False,
                    "entity_resolution.resolution_status": "ALIAS",
                    "updated_at": now,
                },
                "$push": {
                    "entity_resolution.merge_history": {
                        "action": "MERGED_TO",
                        "target_id": str(target_id),
                        "reviewer": request.reviewer,
                        "timestamp": now,
                    }
                }
            }
        )

        # 更新 target 的别名
        source_aliases = source_party.get("aliases", [])
        await db.parties.update_one(
            {"_id": target_id},
            {
                "$addToSet": {"aliases": {"$each": source_aliases}},
                "$set": {"updated_at": now},
                "$push": {
                    "entity_resolution.merge_history": {
                        "action": "MERGED_FROM",
                        "source_id": str(source_id),
                        "reviewer": request.reviewer,
                        "timestamp": now,
                    }
                }
            }
        )

        # 更新队列状态
        await db.entity_merge_queue.update_one(
            {"_id": ObjectId(queue_id)},
            {
                "$set": {
                    "status": "APPROVED",
                    "review.reviewed_by": request.reviewer,
                    "review.reviewed_at": now,
                    "review.decision": "APPROVE",
                    "review.notes": request.notes,
                    "updated_at": now,
                }
            }
        )

        return {
            "success": True,
            "message": f"Merged: {queue_item['merge_suggestion']['source_name']} → {queue_item['merge_suggestion']['target_name']}"
        }

    elif request.decision == "REJECT":
        # 拒绝合并
        source_id = ObjectId(queue_item["merge_suggestion"]["source_party_id"])

        # 更新 source 状态回 CANONICAL
        await db.parties.update_one(
            {"_id": source_id},
            {
                "$set": {
                    "entity_resolution.resolution_status": "CANONICAL",
                    "updated_at": now,
                }
            }
        )

        # 更新队列状态
        await db.entity_merge_queue.update_one(
            {"_id": ObjectId(queue_id)},
            {
                "$set": {
                    "status": "REJECTED",
                    "review.reviewed_by": request.reviewer,
                    "review.reviewed_at": now,
                    "review.decision": "REJECT",
                    "review.rejection_reason": request.reason,
                    "review.notes": request.notes,
                    "updated_at": now,
                }
            }
        )

        return {
            "success": True,
            "message": f"Rejected merge: {queue_item['merge_suggestion']['source_name']}"
        }

    else:
        raise HTTPException(status_code=400, detail="Invalid decision. Use APPROVE or REJECT")


@router.post("/queue/bulk-review")
async def bulk_review(request: BulkReviewRequest):
    """
    批量审核

    一次性批准或拒绝多条记录
    """
    db = await get_db()

    results = {
        "success": 0,
        "failed": 0,
        "errors": []
    }

    for queue_id in request.queue_ids:
        try:
            review_req = ReviewRequest(
                decision=request.decision,
                reviewer=request.reviewer,
                reason=request.reason
            )
            await review_merge(queue_id, review_req)
            results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{queue_id}: {str(e)}")

    return {
        "success": True,
        "data": results
    }


@router.get("/stats")
async def get_stats():
    """
    获取统计数据

    - 各状态数量
    - 按置信度分布
    - 按 party 类型分布
    """
    db = await get_db()

    # 基础统计
    stats = {
        "queue": {
            "total": await db.entity_merge_queue.count_documents({}),
            "pending": await db.entity_merge_queue.count_documents({"status": "PENDING"}),
            "approved": await db.entity_merge_queue.count_documents({"status": "APPROVED"}),
            "rejected": await db.entity_merge_queue.count_documents({"status": "REJECTED"}),
            "auto_merged": await db.entity_merge_queue.count_documents({"status": "AUTO_MERGED"}),
        },
        "parties": {
            "total": await db.parties.count_documents({}),
            "canonical": await db.parties.count_documents({"entity_resolution.is_canonical": True}),
            "alias": await db.parties.count_documents({"entity_resolution.is_canonical": False}),
            "company": await db.parties.count_documents({"party_type": "COMPANY"}),
            "person": await db.parties.count_documents({"party_type": "PERSON"}),
        }
    }

    # 置信度分布
    confidence_pipeline = [
        {"$match": {"status": "PENDING"}},
        {"$bucket": {
            "groupBy": "$match_evidence.confidence",
            "boundaries": [0.75, 0.80, 0.85, 0.90, 0.95, 1.0],
            "default": "other",
            "output": {"count": {"$sum": 1}}
        }}
    ]
    confidence_dist = await db.entity_merge_queue.aggregate(confidence_pipeline).to_list(None)
    stats["confidence_distribution"] = confidence_dist

    return {
        "success": True,
        "data": stats
    }


@router.get("/parties")
async def get_parties(
    party_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="搜索名称"),
    is_canonical: bool = Query(True),
    skip: int = Query(0),
    limit: int = Query(20)
):
    """
    获取 Party 列表
    """
    db = await get_db()

    query = {"entity_resolution.is_canonical": is_canonical}
    if party_type:
        query["party_type"] = party_type
    if search:
        query["$or"] = [
            {"display_name": {"$regex": search, "$options": "i"}},
            {"canonical_name": {"$regex": search, "$options": "i"}},
            {"aliases": {"$regex": search, "$options": "i"}}
        ]

    total = await db.parties.count_documents(query)
    cursor = db.parties.find(query).sort("display_name", 1).skip(skip).limit(limit)

    items = []
    async for doc in cursor:
        items.append(serialize_doc(doc))

    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    }
