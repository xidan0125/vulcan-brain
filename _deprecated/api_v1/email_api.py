"""
邮件 API - 五纬度信息收集系统 (维度3)

端点:
- GET /email/stats - 邮件统计
- GET /email/summary/{date} - AI 邮件摘要
- POST /email/sync - 触发邮件同步
- POST /email/sync-all - 全量同步（含完整正文）
- POST /email/backfill - 补充已有邮件正文
- GET /email/backfill-status - 正文补充进度
- GET /email/list - 邮件列表
- GET /email/contacts - 联系人统计
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
import asyncio
import logging

logger = logging.getLogger("EmailAPI")
router = APIRouter(prefix="/info-hub/email", tags=["Email"])

# 同步状态
_sync_status = {"running": False, "progress": "", "started_at": None}


@router.get("/stats")
async def get_email_stats(
    date: str = Query(None, description="日期 YYYY-MM-DD，默认今天")
):
    """获取邮件统计数据"""
    from services.email_store import get_email_store

    store = get_email_store()

    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")
    else:
        date_obj = datetime.now()

    stats = await store.get_email_stats(date_obj)
    top_contacts = await store.get_top_contacts(date_obj, limit=5)

    return {
        "date": date_obj.strftime("%Y-%m-%d"),
        "stats": stats,
        "top_contacts": top_contacts
    }


@router.get("/summary/{date}")
async def get_email_summary(date: str):
    """获取指定日期的邮件 AI 摘要"""
    from services.email_summarizer import generate_email_summary

    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误")

    try:
        summary = await generate_email_summary(date_obj)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成摘要失败: {str(e)}")


@router.post("/sync")
async def sync_emails(
    background_tasks: BackgroundTasks,
    days: int = Query(7, ge=1, le=365, description="同步最近N天")
):
    """触发邮件同步（后台执行）- 增量同步"""
    global _sync_status
    
    if _sync_status["running"]:
        return {
            "success": False,
            "message": "同步正在进行中",
            "status": _sync_status
        }
    
    from services.email_store import get_email_store

    store = get_email_store()
    since = datetime.now() - timedelta(days=days)

    async def do_sync():
        global _sync_status
        _sync_status = {"running": True, "progress": "正在同步...", "started_at": datetime.now().isoformat()}
        
        try:
            users = await store.get_all_users()
            total_users = len(users)
            
            for idx, user in enumerate(users):
                if user.get("mail"):
                    _sync_status["progress"] = f"同步用户 {idx+1}/{total_users}: {user['mail']}"
                    await store.sync_user_emails(user["mail"], since=since, folder="inbox", max_emails=10000)
                    await store.sync_user_emails(user["mail"], since=since, folder="sentItems", max_emails=10000)
            
            _sync_status["progress"] = "同步完成"
        except Exception as e:
            logger.error(f"邮件同步失败: {e}")
            _sync_status["progress"] = f"同步失败: {e}"
        finally:
            _sync_status["running"] = False

    background_tasks.add_task(do_sync)

    return {
        "success": True,
        "message": f"邮件同步已启动（最近 {days} 天）",
        "since": since.isoformat()
    }


@router.post("/sync-all")
async def sync_all_emails(
    background_tasks: BackgroundTasks,
    days: int = Query(365, ge=1, le=1095, description="同步最近N天（默认1年）")
):
    """全量邮件同步（含完整正文和附件元数据）"""
    global _sync_status
    
    if _sync_status["running"]:
        return {
            "success": False,
            "message": "同步正在进行中",
            "status": _sync_status
        }
    
    from services.email_store import get_email_store

    store = get_email_store()
    since = datetime.now() - timedelta(days=days)

    async def do_full_sync():
        global _sync_status
        _sync_status = {"running": True, "progress": "开始全量同步...", "started_at": datetime.now().isoformat()}
        
        try:
            result = await store.sync_all_users(since=since, max_per_folder=50000)
            _sync_status["progress"] = f"全量同步完成: {result}"
            logger.info(f"全量同步完成: {result}")
        except Exception as e:
            logger.error(f"全量同步失败: {e}")
            _sync_status["progress"] = f"同步失败: {e}"
        finally:
            _sync_status["running"] = False

    background_tasks.add_task(do_full_sync)

    return {
        "success": True,
        "message": f"全量同步已启动（最近 {days} 天，含完整正文）",
        "since": since.isoformat()
    }


@router.post("/backfill")
async def backfill_email_bodies(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(100, ge=10, le=500, description="每批处理数量")
):
    """补充已有邮件的完整正文和附件元数据"""
    global _sync_status
    
    if _sync_status["running"]:
        return {
            "success": False,
            "message": "有任务正在进行中",
            "status": _sync_status
        }
    
    from services.email_store import get_email_store
    store = get_email_store()

    async def do_backfill():
        global _sync_status
        _sync_status = {"running": True, "progress": "开始补充正文...", "started_at": datetime.now().isoformat()}
        
        try:
            total_updated = 0
            total_failed = 0
            
            while True:
                status = await store.get_backfill_status()
                if status["without_full_body"] == 0:
                    break
                
                _sync_status["progress"] = f"补充正文中... 剩余 {status['without_full_body']} 封"
                
                result = await store.backfill_email_bodies(batch_size=batch_size)
                total_updated += result["updated"]
                total_failed += result["failed"]
                
                if result["total"] == 0:
                    break
                
                # 小批次间隔
                await asyncio.sleep(1)
            
            _sync_status["progress"] = f"正文补充完成: 成功 {total_updated}, 失败 {total_failed}"
            logger.info(f"正文补充完成: 成功 {total_updated}, 失败 {total_failed}")
            
        except Exception as e:
            logger.error(f"正文补充失败: {e}")
            _sync_status["progress"] = f"补充失败: {e}"
        finally:
            _sync_status["running"] = False

    background_tasks.add_task(do_backfill)

    return {
        "success": True,
        "message": "正文补充任务已启动"
    }


@router.get("/backfill-status")
async def get_backfill_status():
    """获取正文补充进度"""
    from services.email_store import get_email_store
    store = get_email_store()
    
    db_status = await store.get_backfill_status()
    
    return {
        "sync_status": _sync_status,
        "database_status": db_status
    }


@router.get("/sync-status")
async def get_sync_status():
    """获取同步状态"""
    from services.email_store import get_email_store
    store = get_email_store()
    
    total = await store.emails.count_documents({})
    
    return {
        "sync_status": _sync_status,
        "total_emails": total
    }


@router.get("/list")
async def list_emails(
    date: str = Query(None, description="日期 YYYY-MM-DD"),
    folder: str = Query(None, description="文件夹: inbox/sentItems，不填则全部"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """获取邮件列表（分页）"""
    from services.email_store import get_email_store

    store = get_email_store()

    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")
        emails = await store.get_emails_by_date(date_obj)
        if folder:
            emails = [e for e in emails if e.get("folder") == folder]
        total = len(emails)
        emails = emails[offset:offset+limit]
        
        # 格式化
        formatted = []
        for e in emails:
            formatted.append({
                "email_id": str(e.get("_id", "")),
                "from": e.get("from", {}),
                "to": e.get("to", []),
                "subject": e.get("subject", ""),
                "body_preview": e.get("body_preview", "")[:200],
                "body": e.get("body", "")[:500] if e.get("body") else "",
                "importance": e.get("importance", "normal"),
                "is_read": e.get("is_read", True),
                "has_attachments": e.get("has_attachments", False),
                "attachments": e.get("attachments", []),
                "received_at": e.get("received_at").isoformat() if e.get("received_at") else None,
                "folder": e.get("folder", "inbox"),
                "user_id": e.get("user_id", "")
            })
    else:
        # 获取全部邮件（分页）
        formatted, total = await store.get_emails_paginated(folder=folder, limit=limit, offset=offset)

    return {
        "emails": formatted,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.get("/contacts")
async def list_contacts(
    days: int = Query(30, ge=1, le=90, description="统计最近N天"),
    limit: int = Query(20, ge=1, le=100)
):
    """获取联系人统计"""
    from services.email_store import get_email_store

    store = get_email_store()
    since = datetime.now() - timedelta(days=days)
    
    contacts = await store.get_top_contacts(since, limit=limit)

    return {
        "contacts": contacts,
        "days": days
    }
