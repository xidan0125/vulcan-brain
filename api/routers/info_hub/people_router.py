"""
信息中心 - 人员 API
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from ._common import get_db, UpdatePersonRequest
from pydantic import BaseModel
from services.people_store import get_people_store
import os

router = APIRouter(tags=["InfoHub-People"])

@router.get("/people/dashboard")
async def get_people_dashboard(date: str = Query(None)):
    """获取人员管理仪表盘"""
    store = get_people_store()

    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        date_obj = datetime.now()

    dashboard = await store.get_dashboard(date_obj)
    return dashboard


@router.get("/people")
async def list_people(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    sort_by: str = Query("activity", regex="^(name|activity|department)$"),
    search: str = Query(None),
    department: str = Query(None),
    function: str = Query(None),
    project: str = Query(None),
):
    """获取人员列表，支持筛选"""
    store = get_people_store()
    people, total = await store.get_people(
        limit=limit,
        skip=skip,
        sort_by=sort_by,
        search=search,
        department=department if department != "all" else None,
        function=function if function != "all" else None,
        project=project if project != "all" else None,
    )

    # 格式化输出
    result = []
    for p in people:
        result.append({
            "user_id": p.get("user_id"),
            "name": p.get("name"),
            "email": p.get("email"),
            "department": p.get("department", "未定义"),
            "function": p.get("function", "未定义"),
            "projects": p.get("projects", []),
            "ms365_job_title": p.get("ms365_job_title"),
            "email_sent_total": p.get("total_emails_sent", 0),
            "email_received_total": p.get("total_emails_received", 0),
            "last_active": p.get("last_active").isoformat() if p.get("last_active") else None,
            "daily_activity": p.get("daily_activity", {}),
        })

    return {"people": result, "total": total}


@router.get("/people/{user_id}")
async def get_person(user_id: str):
    """获取人员详情"""
    store = get_people_store()
    person = await store.get_person(user_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return {"person": person}


@router.get("/people/{user_id}/chat-activity")
async def get_person_chat_activity(user_id: str):
    """获取人员的群聊参与情况"""
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client.vulcan_brain

    # 先获取用户信息
    person = await db.people.find_one({"user_id": user_id})
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    person_name = person.get("name")
    if not person_name:
        return {"chats": []}

    # 聚合该用户在各群聊的消息数量
    pipeline = [
        {"$match": {"sender.name": person_name}},
        {"$group": {
            "_id": "$chat_id",
            "message_count": {"$sum": 1},
            "last_message": {"$last": "$content"},
            "last_timestamp": {"$max": "$timestamp"}
        }},
        {"$sort": {"last_timestamp": -1}},
        {"$limit": 20}
    ]

    chat_stats = []
    async for doc in db.feishu_messages.aggregate(pipeline):
        chat_id = doc["_id"]
        # 获取群聊名称
        chat_info = await db.feishu_chats.find_one({"chat_id": chat_id})
        chat_name = chat_info.get("name", "未知群聊") if chat_info else "未知群聊"

        chat_stats.append({
            "chat_id": chat_id,
            "chat_name": chat_name,
            "message_count": doc["message_count"],
            "last_message": doc.get("last_message", "")[:100] if doc.get("last_message") else None,
        })

    return {"chats": chat_stats}


@router.patch("/people/{user_id}")
async def update_person(user_id: str, req: UpdatePersonRequest):
    """更新人员信息 (手动分配部门/职能/项目)"""
    store = get_people_store()
    updates = req.dict(exclude_none=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    success = await store.update_person(user_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Person not found or no changes")

    return {"success": True}


@router.post("/people/sync")
async def sync_people(background_tasks: BackgroundTasks):
    """从 MS365 同步人员数据"""
    async def do_sync():
        store = get_people_store()
        await store.init_indexes()
        await store.sync_from_ms365()
        # 更新最近 7 天的活跃度
        for i in range(7):
            date = datetime.now() - timedelta(days=i)
            await store.update_email_activity(date)

    background_tasks.add_task(do_sync)
    return {"success": True, "message": "人员同步已启动"}

# ===== 审批管理 API =====
from services.approval_store import get_approval_store
from services.approval_service import get_approval_service, collect_all_approvals, trigger_approval_analysis

class CollectApprovalsRequest(BaseModel):
    approval_codes: Optional[List[str]] = None  # 指定审批类型，None则采集全部
    since_hours: int = 24  # 采集多少小时内的审批


