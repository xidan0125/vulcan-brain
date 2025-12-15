"""
信息中心 API - 直接读取数据库
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
import os

router = APIRouter(prefix="/info-hub", tags=["InfoHub"])

# MongoDB 连接
_client = None
def get_db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    return _client.vulcan_brain


class GenerateReportRequest(BaseModel):
    date: Optional[str] = None



# ===== V2 API: 统一日报接口 =====

@router.get("/daily/latest-by-dimension")
async def get_latest_by_dimension():
    """获取每个维度最近有数据的日期

    用于演示场景：不同维度的测试数据可能在不同日期
    返回: { chat: "2025-12-02", email: "2025-12-09", approval: "2025-12-10", ... }
    """
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    result = {
        "chat": today,
        "email": today,
        "projects": today,
        "approval": today,
        "people": today,
    }

    # Chat: 查找有 chat 消息的日报
    chat_report = await db.daily_reports.find_one(
        {"$or": [
            {"chat.total_messages": {"$gt": 0}},
            {"dimensions.chat.totals.total_messages": {"$gt": 0}}
        ]},
        sort=[("date", -1)]
    )
    if chat_report:
        result["chat"] = chat_report["date"]

    # Email: 查找有邮件的日报
    email_report = await db.daily_reports.find_one(
        {"$or": [
            {"email.total": {"$gt": 0}},
            {"dimensions.email.total": {"$gt": 0}}
        ]},
        sort=[("date", -1)]
    )
    if email_report:
        result["email"] = email_report["date"]

    # Projects: 查找有项目摘要的日期
    project_summary = await db.project_summaries.find_one(
        {},
        sort=[("date", -1)]
    )
    if project_summary:
        result["projects"] = project_summary["date"]

    # Approval: 查找有审批数据的日期 (bot_approvals)
    latest_approval = await db.bot_approvals.find_one(
        {},
        sort=[("created_at", -1)]
    )
    if latest_approval and latest_approval.get("created_at"):
        result["approval"] = latest_approval["created_at"].strftime("%Y-%m-%d")

    # People: 查找有活跃度数据的日期
    people_report = await db.daily_reports.find_one(
        {"$or": [
            {"dimensions.people.total_count": {"$gt": 0}},
            {"people.total_count": {"$gt": 0}}
        ]},
        sort=[("date", -1)]
    )
    if people_report:
        result["people"] = people_report["date"]

    return result


@router.get("/daily/latest-available")
async def get_latest_available_date():
    """获取最近有有效数据的日期
    
    逻辑: 找到最近一个 email.total > 0 或 chat.total_messages > 0 的日报
    """
    db = get_db()
    
    # 查找最近有数据的日报 (email.total > 0 或有 chat 数据)
    report = await db.daily_reports.find_one(
        {"$or": [
            {"email.total": {"$gt": 0}},
            {"dimensions.email.total": {"$gt": 0}},
            {"chat.total_messages": {"$gt": 0}},
            {"dimensions.chat.totals.total_messages": {"$gt": 0}}
        ]},
        sort=[("date", -1)]
    )
    
    if report:
        return {
            "date": report["date"],
            "has_email": report.get("email", {}).get("total", 0) > 0 or report.get("dimensions", {}).get("email", {}).get("total", 0) > 0,
            "has_chat": report.get("chat", {}).get("total_messages", 0) > 0 or report.get("dimensions", {}).get("chat", {}).get("totals", {}).get("total_messages", 0) > 0
        }
    
    # 如果没有任何有数据的日报，返回昨天
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return {
        "date": yesterday,
        "has_email": False,
        "has_chat": False
    }


@router.get("/daily/v2/{date}")
async def get_daily_v2(date: str):
    """V2 统一日报接口 - 一次返回所有五维度数据
    
    返回结构:
    {
        "date": "2025-12-09",
        "generated_at": "...",
        "summary": {  # 卡片摘要数字
            "chat": { "count": 156, "highlights": 3 },
            "email": { "count": 228, "urgent": 2, "vip": 5 },
            "projects": { "count": 45, "at_risk": 3, "blocked": 1 },
            "approval": { "count": 12, "pending": 5 },
            "people": { "count": 42, "active": 38 }
        },
        "chat": { ... 完整聊天数据 ... },
        "email": { ... 完整邮件数据 ... },
        "projects": { ... 完整项目数据 ... },
        "approval": { ... 完整审批数据 ... },
        "people": { ... 完整人员数据 ... }
    }
    """
    db = get_db()
    
    # 1. 获取基础日报
    report = await db.daily_reports.find_one({"date": date})
    
    # 2. 获取项目简报
    project_summary = await db.project_summaries.find_one({"date": date})
    
    # 3. 获取审批统计 (使用 bot_approvals 集合)
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        start = date_obj.replace(hour=0, minute=0, second=0)
        end = date_obj.replace(hour=23, minute=59, second=59)

        # 审批统计 - 从 bot_approvals 集合按 created_at 查询
        approval_pipeline = [
            {"$match": {"created_at": {"$gte": start, "$lte": end}}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        approval_stats_cursor = db.bot_approvals.aggregate(approval_pipeline)
        approval_by_status = {}
        approval_total = 0
        async for doc in approval_stats_cursor:
            status = doc["_id"].upper() if doc["_id"] else "UNKNOWN"
            approval_by_status[status] = doc["count"]
            approval_total += doc["count"]

        approval_pending = approval_by_status.get("PENDING", 0)
    except Exception as e:
        print(f"审批统计失败: {e}")
        approval_total = 0
        approval_pending = 0
        approval_by_status = {}
    
    # 4. 获取人员统计
    try:
        people_count = await db.people.count_documents({})
        # 活跃人员 = 最近7天有邮件活动
        active_threshold = datetime.now() - timedelta(days=7)
        active_count = await db.people.count_documents({
            "last_active": {"$gte": active_threshold}
        })
    except Exception as e:
        print(f"人员统计失败: {e}")
        people_count = 0
        active_count = 0
    
    # 5. 解析日报数据
    if report:
        dims = report.get("dimensions", {})
        chat_data = dims.get("chat", report.get("chat", {}))
        email_data = dims.get("email", report.get("email", {}))
        
        # 解析 chat
        chat_totals = chat_data.get("totals", {})

        # 从 chat_metadata 获取真正的群名映射
        chat_ids = [c.get("chat_id") for c in chat_data.get("chats", []) if c.get("chat_id")]
        chat_name_map = {}
        if chat_ids:
            metadata_cursor = db.chat_metadata.find({"chat_id": {"$in": chat_ids}})
            async for meta in metadata_cursor:
                chat_name_map[meta["chat_id"]] = meta.get("chat_name", "")

        chat_summaries = []
        for c in chat_data.get("chats", []):
            analysis = c.get("analysis", {})
            chat_id = c.get("chat_id")
            # 优先使用 chat_metadata 的群名，其次使用日报中的群名
            real_chat_name = chat_name_map.get(chat_id) or c.get("chat_name") or f"群聊_{chat_id[-8:]}"
            chat_summaries.append({
                "chat_id": chat_id,
                "chat_name": real_chat_name,
                "message_count": c.get("msg_count", 0),
                "summary": analysis.get("summary", ""),
                "decisions": analysis.get("decisions", []),
                "action_items": analysis.get("action_items", []),
                "risks": analysis.get("risks", []),
                "topics": analysis.get("topics", []),
                "activity_level": analysis.get("activity_level", "medium"),
                "sentiment": analysis.get("sentiment", "neutral")
            })
        
        # 汇总所有群的 risks/action_items/decisions（带来源群名）
        all_risks = []
        all_action_items = []
        all_decisions = []
        active_chats = []  # 按消息数排序的群组

        for s in chat_summaries:
            chat_name = s.get("chat_name", "未知群")
            msg_count = s.get("message_count", 0)
            if msg_count > 0:
                active_chats.append({"name": chat_name, "count": msg_count, "chat_id": s.get("chat_id")})
            for r in s.get("risks", []):
                all_risks.append({"content": r, "source": chat_name, "chat_id": s.get("chat_id")})
            for a in s.get("action_items", []):
                all_action_items.append({"content": a, "source": chat_name, "chat_id": s.get("chat_id")})
            for d in s.get("decisions", []):
                all_decisions.append({"content": d, "source": chat_name, "chat_id": s.get("chat_id")})

        # 按消息数排序活跃群组
        active_chats.sort(key=lambda x: x["count"], reverse=True)

        # 生成全局摘要（合并所有群的摘要）
        summaries_text = [s.get("summary", "") for s in chat_summaries if s.get("summary")]
        global_summary = ""
        if summaries_text:
            # 简单合并，取前3个群的摘要要点
            global_summary = "；".join(summaries_text[:3])
            if len(summaries_text) > 3:
                global_summary += f"...等{len(summaries_text)}个群组"

        chat_result = {
            "total_chats": len(chat_data.get("chats", [])),
            "total_messages": chat_totals.get("total_messages", chat_data.get("total_messages", 0)),
            "global_summary": global_summary,
            "all_risks": all_risks,
            "all_action_items": all_action_items,
            "all_decisions": all_decisions,
            "active_chats": active_chats[:5],  # 只取前5个活跃群
            "summaries": chat_summaries
        }
        
        # 解析 email
        email_result = email_data if email_data else {
            "total": 0, "received": 0, "sent": 0, "important": 0,
            "external_count": 0, "top_contacts": [], "vip_emails": [],
            "ai_analysis": {}
        }
        
        generated_at = report.get("created_at")
        if generated_at:
            generated_at = generated_at.isoformat() if hasattr(generated_at, 'isoformat') else str(generated_at)
    else:
        chat_result = {
            "total_chats": 0, "total_messages": 0, "summaries": [],
            "global_summary": "", "all_risks": [], "all_action_items": [],
            "all_decisions": [], "active_chats": []
        }
        email_result = {
            "total": 0, "received": 0, "sent": 0, "important": 0,
            "external_count": 0, "top_contacts": [], "vip_emails": [],
            "ai_analysis": {}
        }
        generated_at = None
    
    # 6. 解析项目数据
    if project_summary:
        stats = project_summary.get("stats", {})
        projects_result = {
            "stats": stats,
            "analysis": project_summary.get("analysis", {}),
            "generated_at": project_summary.get("generated_at")
        }
        project_count = stats.get("total_tasks", 0)
        project_at_risk = stats.get("at_risk_tasks", 0)
        project_blocked = stats.get("blocked_tasks", 0)
    else:
        projects_result = None
        project_count = 0
        project_at_risk = 0
        project_blocked = 0
    
    # 7. 构建 summary (卡片数字)
    email_ai = email_result.get("ai_analysis", {})
    urgent_matters = email_ai.get("urgent_matters", [])
    urgent_count = len(urgent_matters) if isinstance(urgent_matters, list) else (1 if urgent_matters else 0)
    
    summary = {
        "chat": {
            "count": chat_result.get("total_messages", 0),
            "chats": chat_result.get("total_chats", 0),
            "highlights": sum(len(s.get("decisions", [])) + len(s.get("action_items", [])) for s in chat_result.get("summaries", []))
        },
        "email": {
            "count": email_result.get("total", 0),
            "urgent": urgent_count,
            "vip": len(email_result.get("vip_emails", []))
        },
        "projects": {
            "count": project_count,
            "at_risk": project_at_risk,
            "blocked": project_blocked
        },
        "approval": {
            "count": approval_total,
            "pending": approval_pending
        },
        "people": {
            "count": people_count,
            "active": active_count
        }
    }
    
    return {
        "date": date,
        "generated_at": generated_at,
        "summary": summary,
        "chat": chat_result,
        "email": email_result,
        "projects": projects_result,
        "approval": {
            "total": approval_total,
            "pending": approval_pending,
            "by_status": approval_by_status
        },
        "people": {
            "total": people_count,
            "active": active_count
        }
    }

@router.get("/daily/{date}")
async def get_daily_by_date(date: str):
    """直接从数据库读取日报"""
    db = get_db()
    
    # 从数据库读取
    report = await db.daily_reports.find_one({"date": date})
    
    if report:
        # 从 dimensions 结构读取数据
        dims = report.get("dimensions", {})
        chat_data = dims.get("chat", {})
        email_data = dims.get("email", {})
        project_data = dims.get("project", {})
        approval_data = dims.get("approval", {})
        people_data = dims.get("people", {})
        
        # 转换 chat 格式
        chat_totals = chat_data.get("totals", {})
        chat_result = {
            "total_chats": len(chat_data.get("chats", [])),
            "total_messages": chat_totals.get("total_messages", 0),
            "summaries": []
        }
        for c in chat_data.get("chats", []):
            analysis = c.get("analysis", {})
            chat_result["summaries"].append({
                "chat_id": c.get("chat_id"),
                "chat_name": c.get("chat_name"),
                "message_count": c.get("msg_count", 0),
                "summary": analysis.get("summary", ""),
                "decisions": analysis.get("decisions", []),
                "action_items": analysis.get("action_items", []),
                "risks": analysis.get("risks", []),
                "topics": analysis.get("topics", []),
                "activity_level": analysis.get("activity_level", "medium"),
                "sentiment": analysis.get("sentiment", "neutral")
            })
        
        return {
            "report": {
                "date": report.get("date"),
                "generated_at": report.get("created_at").isoformat() if report.get("created_at") else None,
                "chat": chat_result,
                "email": email_data,
                "projects": {"total_count": project_data.get("in_progress", 0) + project_data.get("completed", 0)},
                "approval": {"total_count": approval_data.get("pending", 0) + approval_data.get("approved", 0)},
                "people": {"total_count": people_data.get("total_count", 0)}
            }
        }
    else:
        # 无数据，返回空结构
        return {
            "report": {
                "date": date,
                "generated_at": None,
                "chat": {"total_chats": 0, "total_messages": 0, "summaries": []},
                "email": {"total": 0, "received": 0, "sent": 0, "important": 0, "external_count": 0, "top_contacts": [], "vip_emails": [], "ai_analysis": {}},
                "projects": {"total_count": 0},
                "approval": {"total_count": 0},
                "people": {"total_count": 0}
            }
        }


@router.get("/daily/latest")
async def get_latest_daily():
    """获取最新日报"""
    db = get_db()
    report = await db.daily_reports.find_one(sort=[("date", -1)])
    if report:
        return await get_daily_by_date(report["date"])
    return await get_daily_by_date(datetime.now().strftime("%Y-%m-%d"))


@router.post("/daily/generate")
async def generate_report(req: GenerateReportRequest, background_tasks: BackgroundTasks):
    """后台生成日报并存储"""
    date_str = req.date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async def do_generate():
        from services.email_summarizer import generate_email_summary
        from services.chat_summarizer import generate_chat_summary
        
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        db = get_db()
        
        # 生成邮件摘要
        email_data = {}
        try:
            email_data = await generate_email_summary(date_obj)
        except Exception as e:
            print(f"邮件摘要生成失败: {e}")
        
        # 生成聊天摘要
        chat_data = {"total_chats": 0, "total_messages": 0, "summaries": []}
        try:
            chat_data = await generate_chat_summary(date_obj)
        except Exception as e:
            print(f"聊天摘要生成失败: {e}")
        
        # 存储
        report = {
            "date": date_str,
            "created_at": datetime.now(),
            "email": email_data,
            "chat": chat_data,
            "projects": {"total_count": 0},
            "approval": {"total_count": 0},
            "people": {"total_count": 0}
        }
        
        await db.daily_reports.update_one(
            {"date": date_str},
            {"$set": report},
            upsert=True
        )
        print(f"✅ 日报已生成并存储: {date_str}")
    
    background_tasks.add_task(do_generate)
    
    return {
        "success": True,
        "message": f"日报生成已启动: {date_str}"
    }


# ===== 分维度生成 API =====

@router.post("/daily/generate/chat")
async def generate_chat_report(req: GenerateReportRequest, background_tasks: BackgroundTasks):
    """仅生成聊天摘要"""
    date_str = req.date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async def do_generate():
        from services.chat_summarizer import generate_chat_summary
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        db = get_db()
        
        try:
            chat_data = await generate_chat_summary(date_obj)
        except Exception as e:
            print(f"聊天摘要生成失败: {e}")
            chat_data = {"total_chats": 0, "total_messages": 0, "summaries": []}
        
        # 更新数据库中的聊天维度
        await db.daily_reports.update_one(
            {"date": date_str},
            {"$set": {"chat": chat_data, "dimensions.chat": chat_data, "updated_at": datetime.now()}},
            upsert=True
        )
        print(f"✅ 聊天摘要已生成: {date_str}")
    
    background_tasks.add_task(do_generate)
    return {"success": True, "message": f"聊天摘要生成已启动: {date_str}"}


@router.post("/daily/generate/email")
async def generate_email_report(req: GenerateReportRequest, background_tasks: BackgroundTasks):
    """仅生成邮件摘要"""
    date_str = req.date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async def do_generate():
        from services.email_summarizer import generate_email_summary
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        db = get_db()
        
        try:
            email_data = await generate_email_summary(date_obj)
        except Exception as e:
            print(f"邮件摘要生成失败: {e}")
            email_data = {}
        
        await db.daily_reports.update_one(
            {"date": date_str},
            {"$set": {"email": email_data, "dimensions.email": email_data, "updated_at": datetime.now()}},
            upsert=True
        )
        print(f"✅ 邮件摘要已生成: {date_str}")
    
    background_tasks.add_task(do_generate)
    return {"success": True, "message": f"邮件摘要生成已启动: {date_str}"}


@router.post("/daily/generate/approval")
async def generate_approval_report(req: GenerateReportRequest, background_tasks: BackgroundTasks):
    """仅生成审批摘要"""
    date_str = req.date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async def do_generate():
        from services.approval_service import trigger_approval_analysis, collect_all_approvals
        db = get_db()
        
        try:
            # 先采集审批
            await collect_all_approvals(since_hours=48)
            # 再生成分析
            result = await trigger_approval_analysis(date_str)
            approval_data = result if result else {}
        except Exception as e:
            print(f"审批摘要生成失败: {e}")
            approval_data = {}
        
        await db.daily_reports.update_one(
            {"date": date_str},
            {"$set": {"approval": approval_data, "dimensions.approval": approval_data, "updated_at": datetime.now()}},
            upsert=True
        )
        print(f"✅ 审批摘要已生成: {date_str}")
    
    background_tasks.add_task(do_generate)
    return {"success": True, "message": f"审批摘要生成已启动: {date_str}"}


@router.post("/daily/generate/people")
async def generate_people_report(req: GenerateReportRequest, background_tasks: BackgroundTasks):
    """仅生成人员活跃度"""
    date_str = req.date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async def do_generate():
        from services.people_store import get_people_store
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        db = get_db()
        
        try:
            store = get_people_store()
            # 同步MS365人员
            await store.sync_from_ms365()
            # 更新活跃度
            await store.update_email_activity(date_obj)
            # 获取仪表盘数据
            dashboard = await store.get_dashboard(date_obj)
            people_data = dashboard.get("stats", {})
        except Exception as e:
            print(f"人员活跃度生成失败: {e}")
            people_data = {}
        
        await db.daily_reports.update_one(
            {"date": date_str},
            {"$set": {"people": people_data, "dimensions.people": people_data, "updated_at": datetime.now()}},
            upsert=True
        )
        print(f"✅ 人员活跃度已生成: {date_str}")
    
    background_tasks.add_task(do_generate)
    return {"success": True, "message": f"人员活跃度生成已启动: {date_str}"}


@router.post("/daily/generate/projects")
async def generate_projects_report(req: GenerateReportRequest, background_tasks: BackgroundTasks):
    """仅生成项目摘要（预留）"""
    date_str = req.date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async def do_generate():
        db = get_db()
        # 项目数据暂时是占位符
        projects_data = {"total_count": 0, "message": "项目维度开发中"}
        
        await db.daily_reports.update_one(
            {"date": date_str},
            {"$set": {"projects": projects_data, "dimensions.projects": projects_data, "updated_at": datetime.now()}},
            upsert=True
        )
        print(f"✅ 项目摘要已生成: {date_str}")
    
    background_tasks.add_task(do_generate)
    return {"success": True, "message": f"项目摘要生成已启动: {date_str}"}



@router.get("/overview")
async def get_overview():
    """概览"""
    db = get_db()
    reports = await db.daily_reports.find().sort("date", -1).limit(7).to_list(7)
    return {
        "latest_report_date": reports[0]["date"] if reports else None,
        "report_count": len(reports),
        "dates": [r["date"] for r in reports]
    }


# ===== 群聊相关 API (保留原有功能) =====
from services.message_store import get_message_store
from services.chat_summary_store import get_chat_summary_store
from services.realtime_analyzer import trigger_chat_analysis

class AnalyzeChatRequest(BaseModel):
    date: Optional[str] = None

@router.get("/chats")
async def list_chats():
    summary_store = get_chat_summary_store()
    msg_store = get_message_store()
    stats = await msg_store.get_stats()
    chats = []
    for stat in stats:
        chat_id = stat.get("_id")
        if not chat_id:
            continue
        metadata = await summary_store.get_chat_metadata(chat_id)
        chats.append({
            "chat_id": chat_id,
            "chat_name": metadata.get("chat_name", f"群聊_{chat_id[-8:]}") if metadata else f"群聊_{chat_id[-8:]}",
            "total_messages": stat.get("total", 0),
        })
    return {"chats": chats, "count": len(chats)}

@router.get("/chat/{chat_id}")
async def get_chat_detail(chat_id: str, days: int = Query(7, ge=1, le=30)):
    summary_store = get_chat_summary_store()
    msg_store = get_message_store()
    metadata = await summary_store.get_chat_metadata(chat_id)
    stats_list = await msg_store.get_stats(chat_id)
    stats = stats_list[0] if stats_list else {}
    summaries = await summary_store.get_chat_history_summaries(chat_id, days)
    history = []
    for s in summaries:
        analysis = s.get("analysis", {})
        history.append({
            "date": s["date"],
            "messages_analyzed": s.get("messages_analyzed", 0),
            "summary": analysis.get("summary", ""),
            "decisions": analysis.get("decisions", []),
            "action_items": analysis.get("action_items", []),
            "risks": analysis.get("risks", []),
            "topics": analysis.get("topics", []),
        })
    return {
        "chat_id": chat_id,
        "chat_name": metadata.get("chat_name", f"群聊_{chat_id[-8:]}") if metadata else f"群聊_{chat_id[-8:]}",
        "total_messages": stats.get("total", 0),
        "history": history
    }


def _format_sender(s):
    """Map sender.id to sender.open_id for frontend compatibility"""
    return {
        "open_id": s.get("id"),
        "name": s.get("name"),
        "sender_type": s.get("sender_type"),
    }

@router.get("/chat/{chat_id}/messages")
async def get_chat_messages(chat_id: str, date: str = Query(None), limit: int = Query(50), offset: int = Query(0)):
    msg_store = get_message_store()
    since, until = None, None
    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            since = date_obj.replace(hour=0, minute=0, second=0)
            until = date_obj.replace(hour=23, minute=59, second=59)
        except:
            pass
    messages = await msg_store.get_chat_history(chat_id=chat_id, limit=limit + offset, since=since, until=until)
    messages = messages[offset:offset+limit]
    formatted = [{"message_id": m.get("message_id"), "sender": _format_sender(m.get("sender", {})), "content": m.get("content", ""), "timestamp": m.get("timestamp").isoformat() if isinstance(m.get("timestamp"), datetime) else m.get("timestamp")} for m in messages]
    return {"messages": formatted, "count": len(formatted)}

@router.post("/chat/{chat_id}/analyze")
async def analyze_chat(chat_id: str, req: AnalyzeChatRequest):
    date = req.date or datetime.now().strftime("%Y-%m-%d")
    try:
        result = await trigger_chat_analysis(chat_id, date)
        return {"success": bool(result), "analysis": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ===== 人员管理 API V2 =====
from services.people_store import get_people_store

class UpdatePersonRequest(BaseModel):
    department: Optional[str] = None
    function: Optional[str] = None
    projects: Optional[List[str]] = None


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


@router.get("/approval/dashboard")
async def get_approval_dashboard(date: str = Query(None)):
    """获取审批仪表盘"""
    store = get_approval_store()

    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        date_obj = datetime.now()

    # 获取当日统计
    start = date_obj.replace(hour=0, minute=0, second=0)
    end = date_obj.replace(hour=23, minute=59, second=59)
    stats = await store.get_stats(since=start, until=end)

    # 获取日报汇总
    summary = await store.get_summary(date_obj.strftime("%Y-%m-%d"))

    return {
        "date": date_obj.strftime("%Y-%m-%d"),
        "stats": stats,
        "summary": summary,
        "pending_count": stats.get("pending_count", 0)
    }


@router.get("/approval/list")
async def list_approvals(
    status: str = Query(None, description="状态筛选: PENDING/APPROVED/REJECTED/CANCELED"),
    approval_code: str = Query(None, description="审批类型code"),
    date: str = Query(None, description="日期筛选 YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0)
):
    """获取审批列表"""
    store = get_approval_store()

    since, until = None, None
    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            since = date_obj.replace(hour=0, minute=0, second=0)
            until = date_obj.replace(hour=23, minute=59, second=59)
        except:
            pass

    approvals = await store.list_approvals(
        approval_code=approval_code,
        status=status,
        since=since,
        until=until,
        limit=limit + skip
    )

    # 分页
    approvals = approvals[skip:skip + limit]

    # 格式化输出
    result = []
    for ap in approvals:
        result.append({
            "instance_code": ap.get("instance_code"),
            "approval_code": ap.get("approval_code"),
            "approval_name": ap.get("approval_name"),
            "status": ap.get("status"),
            "user_id": ap.get("user_id"),
            "open_id": ap.get("open_id"),
            "start_time": ap.get("start_time"),
            "end_time": ap.get("end_time"),
            "serial_number": ap.get("serial_number")
        })

    return {"approvals": result, "count": len(result)}


@router.get("/approval/definitions")
async def list_approval_definitions():
    """获取审批定义列表（审批类型）"""
    store = get_approval_store()
    definitions = await store.list_definitions()
    return {"definitions": definitions, "count": len(definitions)}


@router.post("/approval/collect")
async def collect_approvals(req: CollectApprovalsRequest, background_tasks: BackgroundTasks):
    """采集飞书审批数据"""
    async def do_collect():
        try:
            result = await collect_all_approvals(since_hours=req.since_hours)
            print(f"✅ 审批采集完成: {result}")
        except Exception as e:
            print(f"❌ 审批采集失败: {e}")

    background_tasks.add_task(do_collect)

    return {
        "success": True,
        "message": f"审批采集已启动，采集范围: {req.since_hours}小时"
    }


@router.post("/approval/analyze")
async def analyze_approvals(date: str = Query(None)):
    """生成审批日报分析"""
    date_str = date or datetime.now().strftime("%Y-%m-%d")

    try:
        result = await trigger_approval_analysis(date_str)
        return {"success": True, "summary": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approval/pending")
async def get_pending_approvals(user_id: str = Query(None)):
    """获取待处理审批"""
    store = get_approval_store()
    approvals = await store.get_pending_approvals(user_id)

    return {
        "approvals": approvals,
        "count": len(approvals)
    }


@router.get("/approval/summaries")
async def get_approval_summaries(days: int = Query(7, ge=1, le=30)):
    """获取最近N天的审批汇总"""
    store = get_approval_store()
    summaries = await store.list_summaries(days)
    return {"summaries": summaries, "count": len(summaries)}


@router.get("/approval/{instance_code}")
async def get_approval_detail(instance_code: str):
    """获取审批详情"""
    store = get_approval_store()
    approval = await store.get_approval(instance_code)

    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    return {"approval": approval}




# ===== 语义搜索 API =====
from services.embedding_service import get_embedding_service

@router.get("/search")
async def semantic_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Query(None, description="限定用户 ID")
):
    """语义搜索邮件
    
    支持中英文自然语言搜索，返回相关度最高的邮件。
    """
    try:
        svc = get_embedding_service()
        results = svc.search(q, limit=limit, user_id=user_id)
        
        return {
            "query": q,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/search/stats")
async def search_stats():
    """获取搜索索引统计"""
    try:
        svc = get_embedding_service()
        stats = svc.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")

# ===== 实体抽取 API (Phase 2) =====
from services.entity_service import get_entity_service

@router.get("/entities/stats")
async def get_entity_stats():
    """获取实体抽取统计"""
    svc = get_entity_service()
    return await svc.get_entity_stats()


@router.get("/entities/search")
async def search_entities(
    type: str = Query(None, description="实体类型: person, company, project, money, date, product, location"),
    text: str = Query(None, description="搜索文本"),
    limit: int = Query(50, ge=1, le=200),
):
    """搜索实体"""
    svc = get_entity_service()
    results = await svc.search_entities(entity_type=type, text=text, limit=limit)
    return {"results": results, "count": len(results)}


@router.get("/entities/email/{email_id}")
async def get_email_entities(email_id: str):
    """获取单封邮件的实体"""
    svc = get_entity_service()
    doc = await svc.entities.find_one({"email_id": email_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Email entities not found")
    doc["_id"] = str(doc["_id"])
    return doc


@router.post("/entities/extract")
async def extract_entities_batch(
    background_tasks: BackgroundTasks,
    limit: int = Query(500, ge=1, le=5000),
):
    """批量抽取实体（后台任务）"""
    async def do_extract():
        svc = get_entity_service()
        await svc.process_batch(limit=limit)
    
    background_tasks.add_task(do_extract)
    return {"success": True, "message": f"开始抽取，最多处理 {limit} 封邮件"}


# ===== 邮件浏览 API =====

@router.get("/emails")
async def list_emails(
    folder: str = Query(None, description="文件夹: inbox, sentitems"),
    category: str = Query(None, description="分类: external, internal, finance, sales, hr, technical, legal, marketing, procurement"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取邮件列表，支持分类筛选"""
    db = get_db()
    
    query = {}
    if folder:
        query["folder"] = folder
    if category:
        query["category"] = category
    
    cursor = db.emails.find(
        query,
        {"email_id": 1, "subject": 1, "from": 1, "to": 1, "received_at": 1, "folder": 1, "category": 1, "entities": 1}
    ).sort("received_at", -1).skip(offset).limit(limit)
    
    emails = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        emails.append(doc)
    
    total = await db.emails.count_documents(query)
    
    return {
        "emails": emails,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


# ===== LightRAG Q&A API (Phase 4) =====
from services.lightrag_service import get_lightrag_service

@router.get("/lightrag/stats")
async def get_lightrag_stats():
    """获取 LightRAG 索引统计"""
    svc = get_lightrag_service()
    return await svc.get_stats()


@router.post("/lightrag/index")
async def index_emails_to_lightrag(
    background_tasks: BackgroundTasks,
    limit: int = Query(500, ge=1, le=5000),
    days: int = Query(90, ge=1, le=365),
):
    """批量索引邮件到知识图谱（后台任务）"""
    async def do_index():
        svc = get_lightrag_service()
        await svc.index_emails(limit=limit, days=days)

    background_tasks.add_task(do_index)
    return {"success": True, "message": f"开始索引，最多处理 {limit} 封邮件（{days}天内）"}


@router.post("/lightrag/query")
async def query_lightrag(
    question: str = Query(..., description="问题"),
    mode: str = Query("hybrid", description="查询模式: naive/local/global/hybrid"),
):
    """知识图谱问答"""
    svc = get_lightrag_service()
    return await svc.query(question=question, mode=mode)


@router.post("/lightrag/summarize")
async def summarize_recent_emails(
    days: int = Query(1, ge=1, le=30),
):
    """总结最近邮件"""
    svc = get_lightrag_service()
    return await svc.summarize_recent(days=days)


# ===== 项目日报 API =====
from services.project_summarizer import generate_project_summary

@router.get("/projects/summary")
async def get_project_summary(date: str = Query(None)):
    """获取项目工作简报"""
    date_str = date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    db = get_db()
    
    # 先从缓存读取
    cached = await db.project_summaries.find_one({"date": date_str})
    if cached:
        cached["_id"] = str(cached["_id"])
        return {"summary": cached, "cached": True}
    
    # 无缓存，返回空
    return {
        "summary": None,
        "cached": False,
        "message": f"日期 {date_str} 无缓存数据，请先生成"
    }


@router.post("/projects/summary/generate")
async def generate_projects_summary(req: GenerateReportRequest, background_tasks: BackgroundTasks):
    """生成项目工作简报（调用LLM分析）"""
    date_str = req.date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async def do_generate():
        db = get_db()
        try:
            result = await generate_project_summary(date_str)
            
            # 存储到数据库
            await db.project_summaries.update_one(
                {"date": date_str},
                {"$set": result},
                upsert=True
            )
            print(f"✅ 项目简报已生成: {date_str}")
        except Exception as e:
            print(f"❌ 项目简报生成失败: {e}")
            import traceback
            traceback.print_exc()
    
    background_tasks.add_task(do_generate)
    return {"success": True, "message": f"项目简报生成已启动: {date_str}"}


@router.get("/projects/raw")
async def get_projects_raw():
    """获取原始项目数据（不经过LLM分析）"""
    from services.project_store import get_project_store
    
    store = get_project_store()
    projects = await store.list_projects()
    tasks = await store.list_tasks()
    
    # 按项目分组任务
    project_tasks = {}
    for t in tasks:
        pid = t.get("project_id")
        if pid not in project_tasks:
            project_tasks[pid] = []
        project_tasks[pid].append(t)
    
    # 统计
    stats = {
        "total_projects": len(projects),
        "total_tasks": len(tasks),
        "by_status": {},
        "by_assignee": {}
    }
    
    for t in tasks:
        status = t.get("status", "unknown")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        
        assignee = t.get("assignee_name", "未分配")
        if assignee not in stats["by_assignee"]:
            stats["by_assignee"][assignee] = {"count": 0, "projects": set()}
        stats["by_assignee"][assignee]["count"] += 1
        stats["by_assignee"][assignee]["projects"].add(t.get("project_id"))
    
    # 转换set为list
    for a in stats["by_assignee"]:
        stats["by_assignee"][a]["projects"] = list(stats["by_assignee"][a]["projects"])
    
    return {
        "projects": projects,
        "tasks": tasks,
        "project_tasks": project_tasks,
        "stats": stats
    }
