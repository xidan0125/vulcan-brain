"""
日报 API 模块
/api/info-hub/daily/*
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Query
from motor.motor_asyncio import AsyncIOMotorClient
import os

from .schemas.daily import DailyReport, DailyReportResponse, ReportOverview
from .schemas.common import GenerateRequest
from .schemas.chat import ChatDimensionData, ChatSummary, ChatAIAnalysis
from .schemas.email import EmailDimensionData, EmailAIAnalysis
from .schemas.people import PeopleDimensionData
from .schemas.approval import ApprovalDimensionData
from .schemas.daily import ProjectDimensionData

router = APIRouter(prefix="/daily", tags=["Daily Report"])

# MongoDB 连接
_client = None
def get_db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    return _client.vulcan_brain


def _build_daily_report(date: str, db_report: dict = None) -> DailyReport:
    """从数据库记录构建统一格式的 DailyReport"""
    if not db_report:
        return DailyReport(date=date)
    
    dims = db_report.get("dimensions", {})
    
    # 解析聊天数据
    chat_data = dims.get("chat", {})
    chat_totals = chat_data.get("totals", {})
    chat_summaries = []
    for c in chat_data.get("chats", []):
        analysis = c.get("analysis", {})
        chat_summaries.append(ChatSummary(
            chat_id=c.get("chat_id", ""),
            chat_name=c.get("chat_name", ""),
            message_count=c.get("msg_count", 0),
            analysis=ChatAIAnalysis(
                summary=analysis.get("summary", ""),
                decisions=analysis.get("decisions", []),
                action_items=analysis.get("action_items", []),
                risks=analysis.get("risks", []),
                topics=analysis.get("topics", []),
                activity_level=analysis.get("activity_level", "medium"),
                sentiment=analysis.get("sentiment", "neutral")
            )
        ))
    
    chat = ChatDimensionData(
        total_chats=len(chat_summaries),
        total_messages=chat_totals.get("total_messages", 0),
        total_decisions=chat_totals.get("total_decisions", 0),
        total_action_items=chat_totals.get("total_action_items", 0),
        total_risks=chat_totals.get("total_risks", 0),
        summaries=chat_summaries
    )
    
    # 解析邮件数据
    email_data = dims.get("email", {})
    email_ai = email_data.get("ai_analysis", {})
    email = EmailDimensionData(
        total=email_data.get("total", 0),
        received=email_data.get("received", 0),
        sent=email_data.get("sent", 0),
        important=email_data.get("important", 0),
        external_count=email_data.get("external_count", 0),
        top_contacts=email_data.get("top_contacts", []),
        ai_analysis=EmailAIAnalysis(
            summary=email_ai.get("summary", ""),
            action_items=email_ai.get("action_items", []),
            risks=email_ai.get("risks", []),
            vip_updates=email_ai.get("vip_updates", []),
            urgent_matters=email_ai.get("urgent_matters", []),
            key_topics=email_ai.get("key_topics", [])
        )
    )
    
    # 解析人员数据
    people_data = dims.get("people", {})
    people = PeopleDimensionData(
        total_count=people_data.get("total_count", 0),
        active_count=people_data.get("active_count", 0)
    )
    
    # 解析审批数据
    approval_data = dims.get("approval", {})
    approval = ApprovalDimensionData(
        total_count=approval_data.get("pending", 0) + approval_data.get("approved", 0),
        pending_count=approval_data.get("pending", 0),
        approved_count=approval_data.get("approved", 0)
    )
    
    # 解析项目数据
    project_data = dims.get("project", {})
    tasks_data = project_data.get("tasks", {})
    project = ProjectDimensionData(
        total_count=project_data.get("total_count", 0),
        in_progress=project_data.get("in_progress", 0),
        completed=project_data.get("completed", 0),
        blocked=project_data.get("blocked", 0)
    )

    return DailyReport(
        date=date,
        generated_at=db_report.get("created_at").isoformat() if db_report.get("created_at") else None,
        chat=chat,
        email=email,
        people=people,
        approval=approval,
        project=project
    )


@router.get("/{date}", response_model=DailyReportResponse)
async def get_daily_report(date: str):
    """获取指定日期的日报"""
    db = get_db()
    report = await db.daily_reports.find_one({"date": date})
    daily_report = _build_daily_report(date, report)
    return DailyReportResponse(report=daily_report)


@router.get("/latest", response_model=DailyReportResponse)
async def get_latest_report():
    """获取最新日报"""
    db = get_db()
    report = await db.daily_reports.find_one(sort=[("date", -1)])
    if report:
        return await get_daily_report(report["date"])
    # 无数据时返回今天的空报告
    today = datetime.now().strftime("%Y-%m-%d")
    return DailyReportResponse(report=DailyReport(date=today))


@router.post("/generate")
async def generate_report(req: GenerateRequest, background_tasks: BackgroundTasks):
    """
    生成日报
    - 默认生成昨天的日报
    - force=True 时覆盖已有日报
    """
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
            print(f"[DailyReport] 邮件摘要生成失败: {e}")
        
        # 先从飞书采集消息 (步骤0)
        try:
            from services.message_store import get_message_collector
            collector = get_message_collector()
            chat_ids = await collector.get_configured_chat_ids()
            print(f"[DailyReport] 开始采集 {len(chat_ids)} 个群聊的消息...")
            for chat_id in chat_ids:
                try:
                    result = await collector.collect_chat_messages(
                        chat_id,
                        since=date_obj.replace(hour=0, minute=0, second=0)
                    )
                    print(f"[DailyReport] 群聊 {chat_id[-8:]} 采集完成: 新增 {result.get('inserted', 0)} 条")
                except Exception as e:
                    print(f"[DailyReport] 群聊 {chat_id[-8:]} 采集失败: {e}")
        except Exception as e:
            print(f"[DailyReport] 消息采集失败: {e}")
        
        # 生成聊天摘要
        chat_data = {"chats": [], "totals": {}}
        try:
            chat_data = await generate_chat_summary(date_obj)
        except Exception as e:
            print(f"[DailyReport] 聊天摘要生成失败: {e}")
        
        # 先更新人员活跃度数据
        try:
            from services.people_store import get_people_store
            store = get_people_store()
            await store.update_email_activity(date_obj)
        except Exception as e:
            print(f"[DailyReport] 人员活跃度更新失败: {e}")
        
        # 获取人员统计
        people_data = {"total_count": 0, "active_count": 0}
        try:
            from services.people_store import get_people_store
            store = get_people_store()
            dashboard = await store.get_dashboard(date_obj)
            stats = dashboard.get("stats", {})
            people_data = {
                "total_count": stats.get("total_people", 0),
                "active_count": stats.get("active_today", 0)
            }
        except Exception as e:
            print(f"[DailyReport] 人员统计失败: {e}")
        
        # 获取审批统计
        approval_data = {"pending": 0, "approved": 0}
        try:
            from services.approval_store import get_approval_store
            store = get_approval_store()
            start = date_obj.replace(hour=0, minute=0, second=0)
            end = date_obj.replace(hour=23, minute=59, second=59)
            stats = await store.get_stats(since=start, until=end)
            approval_data = {
                "pending": stats.get("pending_count", 0),
                "approved": stats.get("by_status", {}).get("APPROVED", 0)
            }
        except Exception as e:
            print(f"[DailyReport] 审批统计失败: {e}")
        

        # 获取项目统计
        project_data = {
            "total_count": 0,
            "in_progress": 0,
            "completed": 0,
            "blocked": 0,
            "tasks": {
                "total": 0,
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "blocked": 0,
                "overdue": 0
            },
            "highlights": [],
            "risks": []
        }
        try:
            from services.project_store import get_project_store
            pm_store = get_project_store()

            # 获取项目列表
            projects = await pm_store.list_projects()
            project_data["total_count"] = len(projects)

            for p in projects:
                status = p.get("status", "in_progress")
                if status == "in_progress":
                    project_data["in_progress"] += 1
                elif status == "completed":
                    project_data["completed"] += 1
                elif status == "blocked":
                    project_data["blocked"] += 1

            # 获取任务列表
            tasks = await pm_store.list_tasks()
            project_data["tasks"]["total"] = len(tasks)

            for t in tasks:
                status = t.get("status", "pending")
                if status == "pending":
                    project_data["tasks"]["pending"] += 1
                elif status == "in_progress":
                    project_data["tasks"]["in_progress"] += 1
                elif status == "completed":
                    project_data["tasks"]["completed"] += 1
                elif status == "blocked":
                    project_data["tasks"]["blocked"] += 1

            # 获取逾期和阻塞任务
            overdue_tasks = await pm_store.get_overdue_tasks()
            blocked_tasks = await pm_store.get_blocked_tasks()

            project_data["tasks"]["overdue"] = len(overdue_tasks)
            project_data["tasks"]["blocked"] = len(blocked_tasks)

            # 生成风险提示
            if overdue_tasks:
                project_data["risks"].append(f"{len(overdue_tasks)}个任务已逾期")
            if blocked_tasks:
                project_data["risks"].append(f"{len(blocked_tasks)}个任务被阻塞")

            print(f"[DailyReport] 项目统计: {project_data['total_count']}个项目, {project_data['tasks']['total']}个任务")
        except Exception as e:
            print(f"[DailyReport] 项目统计失败: {e}")

        # 构建完整日报
        report = {
            "date": date_str,
            "created_at": datetime.now(),
            "dimensions": {
                "chat": chat_data,
                "email": email_data,
                "people": people_data,
                "approval": approval_data,
                "project": project_data
            }
        }
        
        await db.daily_reports.update_one(
            {"date": date_str},
            {"$set": report},
            upsert=True
        )
        print(f"[DailyReport] ✅ {date_str} 日报生成完成")
    
    background_tasks.add_task(do_generate)
    
    return {
        "success": True,
        "message": f"日报生成已启动: {date_str}",
        "date": date_str
    }


@router.get("/overview", response_model=ReportOverview)
async def get_overview():
    """获取日报概览"""
    db = get_db()
    reports = await db.daily_reports.find().sort("date", -1).limit(7).to_list(7)
    return ReportOverview(
        latest_report_date=reports[0]["date"] if reports else None,
        report_count=len(reports),
        dates=[r["date"] for r in reports]
    )
