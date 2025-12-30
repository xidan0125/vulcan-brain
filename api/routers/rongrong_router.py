"""
榕融日报 API 路由 v8
优先读取 JSON 文件，回退到 MongoDB
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import json
from loguru import logger

from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, MONGO_DB_NAME

router = APIRouter(prefix="/rongrong", tags=["榕融日报"])

# 数据目录
DATA_DIR = Path.home() / "vulcan-brain" / "data" / "rongrong"

# 数据库连接
_client = None
_db = None

def get_db():
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(MONGO_URI)
        _db = _client[MONGO_DB_NAME]
    return _db


def load_json_file(company: str, date: str, filename: str) -> Optional[Dict]:
    """加载 JSON 文件"""
    filepath = DATA_DIR / company / date / filename
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {filepath}: {e}")
    return None


@router.get("/report/{date}")
async def get_rongrong_report(date: str, company: str = "shanghai"):
    """
    获取指定日期的榕融日报

    优先级:
    1. JSON 文件 (data/rongrong/{company}/{date}/*.json)
    2. MongoDB rongrong_reports
    3. MongoDB rongrong_filter_runs
    """
    db = get_db()

    # === 优先从 JSON 文件读取 ===
    insights_json = load_json_file(company, date, "03_insights.json")
    extraction_json = load_json_file(company, date, "02_extraction.json")
    filter_json = load_json_file(company, date, "01_filter.json")

    if insights_json or extraction_json:
        logger.info(f"Loading from JSON files: {company}/{date}")

        # 构建 insights
        insights = get_empty_insights()
        if insights_json:
            insights = {
                "executive_summary": insights_json.get("executive_summary", "暂无执行摘要"),
                "tension_points": insights_json.get("tension_points", []),
                "financial_summary": insights_json.get("financial_summary", {"inflows": [], "outflows": [], "comment": ""}),
                "key_people": insights_json.get("key_people", []),
                "watchlist": insights_json.get("watchlist", [])
            }

        # 构建 extraction - 直接使用JSON数据，保留所有字段
        extraction_results = {}
        if extraction_json:
            events = extraction_json.get("events", {})
            for category in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS", "ADMIN", "FILE"]:
                items = events.get(category, [])
                flat_list = []
                for item in items:
                    # 保留所有字段，确保前端需要的字段都存在
                    flat_item = {
                        "tag": item.get("tag", ""),
                        "style": item.get("style", "LOG"),
                        "summary": item.get("summary", ""),
                        "highlights": item.get("highlights", {"entities": [], "numbers": []}),
                        "source_id": item.get("email_id", item.get("source_id", ""))
                    }
                    flat_list.append(flat_item)
                extraction_results[category] = flat_list
        else:
            extraction_results = {cat: [] for cat in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS", "ADMIN", "FILE"]}

        # 统计
        total_emails = 0
        if filter_json:
            total_emails = filter_json.get("stats", {}).get("keep", 0)
        elif extraction_json:
            total_emails = extraction_json.get("stats", {}).get("input_emails", 0)

        total_items = sum(len(extraction_results.get(cat, [])) for cat in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS", "ADMIN", "FILE"])

        return {
            "date": date,
            "source": "json",
            "stats": {
                "total_emails": total_emails,
                "tension_count": len(insights.get("tension_points", [])),
                "watchlist_count": len(insights.get("watchlist", [])),
                "total_items": total_items
            },
            "insights": insights,
            "extraction_results": extraction_results
        }

    # === 回退到 MongoDB rongrong_reports ===
    report = await db.rongrong_reports.find_one({
        "company": company,
        "date": date
    })

    if report and report.get("agent_version") == "v7":
        return {
            "date": report["date"],
            "source": "mongodb_reports",
            "stats": report.get("stats", {
                "total_emails": 0,
                "tension_count": 0,
                "watchlist_count": 0,
                "total_items": 0
            }),
            "insights": report.get("insights", get_empty_insights()),
            "extraction_results": report.get("extraction", get_empty_extraction())
        }

    # === 回退到 MongoDB rongrong_filter_runs ===
    doc = await db.rongrong_filter_runs.find_one({
        "company": company,
        "date": date
    })

    if not doc:
        raise HTTPException(status_code=404, detail=f"未找到 {date} 的日报数据")

    # v7 报告
    if doc.get("report_v7"):
        report = doc["report_v7"]
        return {
            "date": report["date"],
            "source": "mongodb_filter_runs_v7",
            "stats": report.get("stats", {}),
            "insights": report.get("insights", get_empty_insights()),
            "extraction_results": report.get("extraction", get_empty_extraction())
        }

    # v6 insights
    insights = None
    if doc.get("insights_v6"):
        raw_v6 = doc["insights_v6"]
        insights = {
            "executive_summary": raw_v6.get("executive_summary", "暂无执行摘要"),
            "tension_points": raw_v6.get("tension_points", []),
            "financial_summary": raw_v6.get("financial_summary", {"inflows": [], "outflows": [], "comment": ""}),
            "key_people": raw_v6.get("key_people", []),
            "watchlist": raw_v6.get("watchlist", [])
        }
    else:
        for version in ["insights_v5", "insights_v4", "insights_v3", "insights"]:
            if doc.get(version):
                insights = transform_old_insights(doc[version])
                break

    if not insights:
        insights = get_empty_insights()

    # extraction
    extraction = get_empty_extraction()
    raw_extraction = doc.get("deduped_extraction") or doc.get("extraction_results", {})

    for category in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS", "ADMIN", "FILE"]:
        items = raw_extraction.get(category, [])
        for item in items:
            style = item.get("style", "LOG")
            if style not in ["RISK", "GAIN", "INSIGHT", "LOG"]:
                style = "LOG"

            key_number = None
            if isinstance(item, dict):
                key_number = item.get("key_number")
                if not key_number:
                    numbers = item.get("numbers", [])
                    if numbers:
                        key_number = numbers[0] if isinstance(numbers[0], str) else str(numbers[0])
                if not key_number:
                    highlights = item.get("highlights", {})
                    numbers = highlights.get("numbers", [])
                    if numbers:
                        key_number = str(numbers[0])

            # 输出扁平数组格式 (前端兼容)
            extraction[category].append({
                "tag": item.get("tag", ""),
                "style": style,
                "summary": item.get("summary", ""),
                "highlights": item.get("highlights", {"entities": [], "numbers": []}),
                "source_id": item.get("email_id", item.get("source_id", ""))
            })

    total_emails = len(doc.get("binary_filter_result", {}).get("KEEP", []))
    total_items = sum(len(extraction[cat]) for cat in ["SALES", "GOVERNANCE", "DELIVERY", "OPERATIONS", "ADMIN", "FILE"])

    return {
        "date": date,
        "source": "mongodb_filter_runs",
        "stats": {
            "total_emails": total_emails,
            "tension_count": len(insights.get("tension_points", [])),
            "watchlist_count": len(insights.get("watchlist", [])),
            "total_items": total_items
        },
        "insights": insights,
        "extraction_results": extraction
    }


def get_empty_insights() -> Dict:
    """返回空的 insights 结构"""
    return {
        "executive_summary": "暂无执行摘要",
        "tension_points": [],
        "financial_summary": {
            "inflows": [],
            "outflows": [],
            "comment": "今日无显著财务变动"
        },
        "key_people": [],
        "watchlist": []
    }


def get_empty_extraction() -> Dict:
    """返回空的 extraction 结构 (扁平数组格式，前端兼容)"""
    return {
        "SALES": [],
        "GOVERNANCE": [],
        "DELIVERY": [],
        "OPERATIONS": [],
        "ADMIN": [],
        "FILE": []
    }


def transform_old_insights(raw: Dict) -> Dict:
    """将旧版 insights 转换为新格式"""
    result = get_empty_insights()

    situation = raw.get("company_situation", {})
    focus = raw.get("attention_focus", {})

    summary_parts = []
    if situation.get("description"):
        summary_parts.append(situation["description"])
    if focus.get("which_point"):
        summary_parts.append(f"当前最需关注：{focus.get("which_point", "")}")
    result["executive_summary"] = " ".join(summary_parts) if summary_parts else "暂无执行摘要"

    for tp in situation.get("tension_points", []):
        result["tension_points"].append({
            "point": tp.get("point", ""),
            "implication": tp.get("implication", "")
        })

    fp = raw.get("financial_pulse", {})
    for inflow in fp.get("inflows", []):
        result["financial_summary"]["inflows"].append({
            "amount": inflow.get("amount", ""),
            "source": inflow.get("source", ""),
            "event": inflow.get("status", "")
        })
    for outflow in fp.get("outflows", []):
        result["financial_summary"]["outflows"].append({
            "amount": outflow.get("amount", ""),
            "destination": outflow.get("destination", ""),
            "event": outflow.get("status", "")
        })

    snapshots = raw.get("functional_snapshots", {})
    people_set = {}
    for func_name, func_data in snapshots.items():
        if isinstance(func_data, dict):
            for person in func_data.get("key_people", []):
                if person not in people_set:
                    people_set[person] = {"name": person, "count": 1, "activities": [func_name]}
                else:
                    people_set[person]["count"] += 1
                    if func_name not in people_set[person]["activities"]:
                        people_set[person]["activities"].append(func_name)

    result["key_people"] = sorted(people_set.values(), key=lambda x: x["count"], reverse=True)[:6]

    for item in raw.get("owner_watchlist", []):
        result["watchlist"].append({
            "item": item.get("item", ""),
            "timeframe": item.get("timeframe", ""),
            "why": item.get("why", "")
        })

    return result


@router.get("/dates")
async def get_available_dates(company: str = "shanghai"):
    """获取有数据的日期列表"""
    db = get_db()

    # 先检查 JSON 目录
    json_dates = []
    company_dir = DATA_DIR / company
    if company_dir.exists():
        for date_dir in company_dir.iterdir():
            if date_dir.is_dir():
                # 检查是否有任何 JSON 文件
                json_files = list(date_dir.glob("*.json"))
                if json_files:
                    json_dates.append(date_dir.name)

    # 从 MongoDB 获取
    cursor = db.rongrong_filter_runs.find(
        {"company": company},
        {"date": 1, "_id": 0}
    ).sort("date", -1).limit(30)

    mongo_dates = []
    async for doc in cursor:
        mongo_dates.append(doc["date"])

    # 合并并去重
    all_dates = sorted(set(json_dates + mongo_dates), reverse=True)

    return {"dates": all_dates[:30]}
