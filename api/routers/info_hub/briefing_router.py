"""
信息中心 - 紧急简报 API
"""

from datetime import datetime
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any
from ._common import get_db

from agents.briefing import generate_briefing, chat_about_briefing

router = APIRouter(tags=["InfoHub-Briefing"])


class BriefingChatRequest(BaseModel):
    query: str
    briefing: Optional[Dict[str, Any]] = None


@router.get("/briefing/urgent")
async def get_urgent_briefing(
    date: str = Query(None, description="日期 YYYY-MM-DD，默认今天"),
    regenerate: bool = Query(False, description="是否重新生成")
):
    """
    获取紧急简报 - 用LLM分析日报，按紧急度排序
    """
    db = get_db()

    # 如果没有指定日期，查找最近有数据的日报
    if not date:
        latest_report = await db.daily_reports.find_one(
            {"email.total": {"$gt": 0}},  # 有邮件数据的日报
            sort=[("date", -1)]
        )
        if latest_report:
            date = latest_report["date"]
        else:
            date = datetime.now().strftime("%Y-%m-%d")

    # 检查 DB 缓存
    if not regenerate:
        cached = await db.urgency_briefings.find_one({"date": date})
        if cached:
            return {
                "date": date,
                "cached": True,
                "generated_at": cached.get("generated_at"),
                "briefing": cached.get("briefing")
            }

    # 获取日报
    report = await db.daily_reports.find_one({"date": date})
    if not report:
        return {
            "date": date,
            "error": "该日期暂无日报数据",
            "briefing": None
        }

    # 调用 Agent 生成简报
    today = datetime.now().strftime("%Y-%m-%d")
    result = await generate_briefing(report, today, force_refresh=regenerate)

    if result.get("error"):
        return {
            "date": date,
            "error": result["error"],
            "briefing": None
        }

    # 缓存到 DB
    await db.urgency_briefings.update_one(
        {"date": date},
        {"$set": {
            "date": date,
            "generated_at": result.get("generated_at"),
            "briefing": result
        }},
        upsert=True
    )

    return {
        "date": date,
        "cached": False,
        "generated_at": result.get("generated_at"),
        "briefing": result
    }


@router.post("/briefing/chat")
async def chat_about_briefing_endpoint(request: BriefingChatRequest):
    """
    基于紧急简报进行对话
    """
    if not request.briefing:
        return {"error": "请先生成简报", "answer": None}

    answer = await chat_about_briefing(request.query, request.briefing)
    return {"answer": answer}
