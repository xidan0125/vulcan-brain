"""
信息中心 - 日报 API
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from ._common import get_db, GenerateReportRequest

router = APIRouter(tags=["InfoHub-Daily"])

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
        # 从 dimensions 结构读取数据，如果没有则从根级别读取
        dims = report.get("dimensions", {})
        chat_data = dims.get("chat") or report.get("chat", {})
        email_data = dims.get("email") or report.get("email", {})
        project_data = dims.get("project") or report.get("projects", {})
        approval_data = dims.get("approval") or report.get("approval", {})
        people_data = dims.get("people") or report.get("people", {})
        
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

