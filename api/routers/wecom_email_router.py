"""
企业微信邮件 API 路由
提供邮件采集、查询、统计接口
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum
from loguru import logger

from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGO_URI, MONGO_DB_NAME
from services.wecom_email_collector import (
    Company, 
    create_collector, 
    sync_all_companies,
    HARD_BLACKLIST_SENDERS,
    SOFT_FILTER_DOMAINS,
)



router = APIRouter(prefix="/wecom-email", tags=["企业微信邮件"])

# 数据库连接
_client = None
_db = None

def get_db():
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(MONGO_URI)
        _db = _client[MONGO_DB_NAME]
    return _db


@router.post("/sync/{company}")
async def sync_company_emails(
    company: Company,
    days: int = Query(default=7, ge=1, le=30),
    limit: int = Query(default=500, ge=1, le=1000),
):
    """
    同步指定公司的邮件
    
    - company: shanghai 或 guangxi
    - days: 同步最近N天
    - limit: 最多同步N封
    """
    db = get_db()
    collector = await create_collector(company, db)
    stats = await collector.sync_emails(days=days, limit=limit)
    return {
        "success": True,
        "company": company.value,
        "stats": stats,
    }


@router.post("/sync-all")
async def sync_all_emails(
    days: int = Query(default=7, ge=1, le=30),
):
    """同步所有公司的邮件"""
    db = get_db()
    results = await sync_all_companies(db, days=days)
    return {
        "success": True,
        "results": results,
    }


@router.get("/list/{company}")
async def list_emails(
    company: Company,
    days: int = Query(default=7, ge=1, le=90),
    include_filtered: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    查询邮件列表
    
    - company: 公司
    - days: 查询最近N天
    - include_filtered: 是否包含软过滤的邮件
    - limit/offset: 分页
    """
    db = get_db()
    collection = db.wecom_emails
    
    since = datetime.now() - timedelta(days=days)
    query = {
        "company": company.value,
        "received_at": {"$gte": since},
    }
    
    if not include_filtered:
        query["is_filtered"] = False
    
    cursor = collection.find(
        query,
        {"body": 0}  # 不返回完整正文
    ).sort("received_at", -1).skip(offset).limit(limit)
    
    emails = await cursor.to_list(length=limit)
    total = await collection.count_documents(query)
    
    # 转换ObjectId
    for e in emails:
        e["_id"] = str(e["_id"])
        if e.get("received_at"):
            e["received_at"] = e["received_at"].isoformat()
        if e.get("synced_at"):
            e["synced_at"] = e["synced_at"].isoformat()
    
    return {
        "company": company.value,
        "total": total,
        "limit": limit,
        "offset": offset,
        "emails": emails,
    }


@router.get("/stats")
async def get_stats(
    days: int = Query(default=7, ge=1, le=90),
):
    """获取邮件统计信息"""
    db = get_db()
    collection = db.wecom_emails
    since = datetime.now() - timedelta(days=days)
    
    # 按公司统计
    pipeline = [
        {"$match": {"received_at": {"$gte": since}}},
        {"$group": {
            "_id": {
                "company": "$company",
                "is_filtered": "$is_filtered",
            },
            "count": {"$sum": 1},
        }},
    ]
    
    results = await collection.aggregate(pipeline).to_list(length=100)
    
    stats = {
        "shanghai": {"total": 0, "filtered": 0, "valid": 0},
        "guangxi": {"total": 0, "filtered": 0, "valid": 0},
    }
    
    for r in results:
        company = r["_id"]["company"]
        is_filtered = r["_id"]["is_filtered"]
        count = r["count"]
        
        if company in stats:
            stats[company]["total"] += count
            if is_filtered:
                stats[company]["filtered"] += count
            else:
                stats[company]["valid"] += count
    
    return {
        "period_days": days,
        "stats": stats,
    }


@router.get("/stats/senders/{company}")
async def get_sender_stats(
    company: Company,
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=20, ge=1, le=100),
):
    """获取发件人统计 - 用于分析和优化过滤规则"""
    db = get_db()
    collection = db.wecom_emails
    since = datetime.now() - timedelta(days=days)
    
    pipeline = [
        {"$match": {
            "company": company.value,
            "received_at": {"$gte": since},
        }},
        {"$group": {
            "_id": "$from_email",
            "count": {"$sum": 1},
            "subjects": {"$push": "$subject"},
            "is_filtered": {"$first": "$is_filtered"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    
    results = await collection.aggregate(pipeline).to_list(length=limit)
    
    # 只保留前3个主题示例
    for r in results:
        r["subject_samples"] = r["subjects"][:3]
        del r["subjects"]
    
    return {
        "company": company.value,
        "period_days": days,
        "senders": results,
    }


@router.get("/filter-rules")
async def get_filter_rules():
    """获取当前过滤规则配置"""
    return {
        "hard_blacklist_senders": list(HARD_BLACKLIST_SENDERS),
        "soft_filter_domains": list(SOFT_FILTER_DOMAINS),
    }


@router.get("/email/{email_id}")
async def get_email_detail(email_id: str):
    """获取邮件详情"""
    db = get_db()
    collection = db.wecom_emails
    
    doc = await collection.find_one({"email_id": email_id})
    if not doc:
        raise HTTPException(status_code=404, detail="邮件不存在")
    
    doc["_id"] = str(doc["_id"])
    if doc.get("received_at"):
        doc["received_at"] = doc["received_at"].isoformat()
    if doc.get("synced_at"):
        doc["synced_at"] = doc["synced_at"].isoformat()
    
    return doc


# ==================== 日报生成接口 ====================

from services.wecom_email_summarizer import generate_wecom_email_summary


@router.get("/summary/{company}/{date}")
async def get_email_summary(
    company: Company,
    date: str,
):
    """
    获取指定日期的邮件日报
    
    - company: shanghai 或 guangxi
    - date: 日期，格式 YYYY-MM-DD
    """
    from datetime import datetime
    
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")
    
    summary = await generate_wecom_email_summary(company.value, target_date)
    return summary


@router.get("/summary/{company}")
async def get_today_summary(company: Company):
    """获取今日邮件日报"""
    from datetime import datetime
    
    summary = await generate_wecom_email_summary(company.value, datetime.now())
    return summary


@router.get("/attachment/{company}/{date_folder}/{email_id}/{filename}")
async def download_attachment(
    company: str,
    date_folder: str,
    email_id: str,
    filename: str,
):
    """下载附件文件"""
    from fastapi.responses import FileResponse
    from pathlib import Path
    
    file_path = Path(f"/home/xinyue/vulcan-brain/data/attachments/{company}/{date_folder}/{email_id}/{filename}")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="附件不存在")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )
# ==================== 日报 V2 接口 ====================

@router.get("/report-v2/{company}/{date}")
async def get_email_report_v2(
    company: Company,
    date: str,
):
    """获取 v2 日报（从 MongoDB 读取）"""
    db = get_db()
    
    report = await db.wecom_daily_reports.find_one({
        "company": company.value,
        "date": date
    })
    
    if not report:
        raise HTTPException(status_code=404, detail=f"日报不存在: {company.value} {date}")
    
    result = report.get("report", {})
    result["generated_at"] = report.get("generated_at").isoformat() if report.get("generated_at") else None
    return result


@router.get("/report-v2/{company}")
async def get_today_report_v2(company: Company):
    """获取今日 v2 日报"""
    today = datetime.now().strftime("%Y-%m-%d")
    return await get_email_report_v2(company, today)
