"""
邮件 API 模块
/api/info-hub/email/*
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorClient
import os

router = APIRouter(prefix="/email", tags=["Email"])

# MongoDB 连接
_client = None
def get_db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    return _client.vulcan_brain


@router.get("/list")
async def list_emails(
    folder: str = Query(None, description="文件夹: inbox, sentitems"),
    category: str = Query(None, description="分类"),
    date: str = Query(None, description="日期 YYYY-MM-DD"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取邮件列表"""
    db = get_db()
    
    query = {}
    if folder:
        query["folder"] = folder
    if category:
        query["category"] = category
    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            query["received_at"] = {
                "$gte": date_obj.replace(hour=0, minute=0, second=0),
                "$lte": date_obj.replace(hour=23, minute=59, second=59)
            }
        except:
            pass
    
    cursor = db.emails.find(
        query,
        {"email_id": 1, "subject": 1, "from": 1, "to": 1, "received_at": 1, 
         "folder": 1, "category": 1, "importance": 1, "is_read": 1, 
         "has_attachments": 1, "body_preview": 1}
    ).sort("received_at", -1).skip(offset).limit(limit)
    
    emails = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if "received_at" in doc and isinstance(doc["received_at"], datetime):
            doc["received_at"] = doc["received_at"].isoformat()
        emails.append(doc)
    
    total = await db.emails.count_documents(query)
    
    return {
        "emails": emails,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/contacts")
async def list_contacts(
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(50, ge=1, le=100)
):
    """获取常用联系人"""
    db = get_db()
    
    since = datetime.now().replace(hour=0, minute=0, second=0)
    from datetime import timedelta
    since = since - timedelta(days=days)
    
    # 聚合联系人
    pipeline = [
        {"$match": {"received_at": {"$gte": since}}},
        {"$group": {
            "_id": "$from.address",
            "name": {"$first": "$from.name"},
            "count": {"$sum": 1},
            "last_email": {"$max": "$received_at"}
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit}
    ]
    
    contacts = []
    async for doc in db.emails.aggregate(pipeline):
        contacts.append({
            "address": doc["_id"],
            "name": doc.get("name", ""),
            "count": doc["count"],
            "last_email": doc["last_email"].isoformat() if doc.get("last_email") else None
        })
    
    return {"contacts": contacts, "count": len(contacts)}


@router.post("/sync")
async def sync_emails(
    background_tasks: BackgroundTasks,
    days: int = Query(7, ge=1, le=30)
):
    """同步邮件"""
    async def do_sync():
        try:
            from services.email_store import get_email_store
            store = get_email_store()
            from datetime import timedelta; since = datetime.now() - timedelta(days=days); await store.sync_all_users(since=since)
            print(f"[Email] ✅ 邮件同步完成 (最近 {days} 天)")
        except Exception as e:
            print(f"[Email] ❌ 邮件同步失败: {e}")
    
    background_tasks.add_task(do_sync)
    return {"success": True, "message": f"邮件同步已启动 (最近 {days} 天)"}


@router.get("/{email_id}")
async def get_email_detail(email_id: str):
    """获取邮件详情"""
    db = get_db()
    email = await db.emails.find_one({"email_id": email_id})
    if not email:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Email not found")
    
    email["_id"] = str(email["_id"])
    if "received_at" in email and isinstance(email["received_at"], datetime):
        email["received_at"] = email["received_at"].isoformat()
    
    return {"email": email}
