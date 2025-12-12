"""
人员 API 模块 V4
/api/info-hub/people/*

数据源:
- people 集合: Graph API 获取的真正员工列表 (42人)
- contacts 集合: 邮件智能数据 (健康度、互动量等)

通过 email 做 join，只展示真正的员工
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from pymongo import MongoClient
import os

from services.people_store import get_people_store

router = APIRouter(prefix="/people", tags=["People"])

# MongoDB 连接
_mongo_client = None
def get_mongo_db():
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017'))
    return _mongo_client['vulcan_brain']


# ========== 角色定位分析 ==========

def analyze_role(sent: int, received: int, total: int) -> Dict[str, Any]:
    """
    基于邮件收发比例分析人员角色定位
    """
    if total < 100:
        return {"role": "peripheral", "role_cn": "边缘角色", "confidence": "low"}

    ratio = sent / received if received > 0 else float('inf')

    if total > 5000:
        if 0.3 <= ratio <= 3:
            return {"role": "hub", "role_cn": "信息枢纽", "confidence": "high"}
        elif ratio > 3:
            return {"role": "broadcaster", "role_cn": "信息发布者", "confidence": "high"}
        else:
            return {"role": "receiver", "role_cn": "信息接收者", "confidence": "high"}
    elif total > 1000:
        if 0.5 <= ratio <= 2:
            return {"role": "coordinator", "role_cn": "协调沟通者", "confidence": "medium"}
        elif ratio > 2:
            return {"role": "broadcaster", "role_cn": "信息发布者", "confidence": "medium"}
        else:
            return {"role": "receiver", "role_cn": "信息接收者", "confidence": "medium"}
    else:
        if 0.3 <= ratio <= 3:
            return {"role": "coordinator", "role_cn": "协调沟通者", "confidence": "low"}
        elif ratio > 3:
            return {"role": "broadcaster", "role_cn": "信息发布者", "confidence": "low"}
        else:
            return {"role": "receiver", "role_cn": "信息接收者", "confidence": "low"}


def get_activity_level(health_score: int, health_trend: str) -> Dict[str, Any]:
    """基于健康度评分确定活跃等级"""
    if health_score >= 80:
        level = "high"
        level_cn = "高度活跃"
    elif health_score >= 60:
        level = "medium"
        level_cn = "中度活跃"
    elif health_score >= 40:
        level = "low"
        level_cn = "低活跃"
    else:
        level = "inactive"
        level_cn = "不活跃"

    trend_cn = {
        "active": "上升",
        "stable": "稳定",
        "inactive": "下降",
        "declining": "下降"
    }.get(health_trend, "未知")

    return {
        "activity_level": level,
        "activity_level_cn": level_cn,
        "activity_trend": health_trend,
        "activity_trend_cn": trend_cn
    }


# ========== 数据整合 ==========

def enrich_person_with_contact(person: dict, contact: dict = None) -> dict:
    """整合 people 和 contacts 数据"""
    email = person.get("email", "").lower()

    # 基础信息 (来自 people 集合 / Graph API)
    result = {
        "user_id": person.get("user_id") or person.get("_id"),
        "name": person.get("name") or person.get("displayName", ""),
        "email": email,
        "department": person.get("department", "未定义"),
        "job_title": person.get("job_title") or person.get("jobTitle", ""),
        "job_category": person.get("job_category", ""),  # 职能分类
        "manager_name": person.get("manager_name", ""),
        "projects": person.get("projects", []),
        "responsibilities": person.get("responsibilities", []),
    }

    # 整合邮件智能数据 (来自 contacts 集合)
    if contact:
        sent = contact.get("sent_count", 0) or contact.get("email_sent_total", 0)
        received = contact.get("received_count", 0) or contact.get("email_received_total", 0)
        total = contact.get("total_interactions", 0) or (sent + received)
        health_score = contact.get("health_score", 0)
        health_trend = contact.get("health_trend", "unknown")

        # 角色分析
        role_info = analyze_role(sent, received, total)
        # 活跃度
        activity_info = get_activity_level(health_score, health_trend)

        result.update({
            "email_sent_total": sent,
            "email_received_total": received,
            "total_interactions": total,
            "first_contact": contact.get("first_contact").isoformat() if contact.get("first_contact") else None,
            "last_sent": contact.get("last_sent").isoformat() if contact.get("last_sent") else None,
            "last_received": contact.get("last_received").isoformat() if contact.get("last_received") else None,
            "health_score": health_score,
            "health_trend": health_trend,
            **role_info,
            **activity_info,
        })
    else:
        # 没有邮件数据
        result.update({
            "email_sent_total": 0,
            "email_received_total": 0,
            "total_interactions": 0,
            "first_contact": None,
            "last_sent": None,
            "last_received": None,
            "health_score": 0,
            "health_trend": "unknown",
            "role": "peripheral",
            "role_cn": "边缘角色",
            "confidence": "low",
            "activity_level": "inactive",
            "activity_level_cn": "不活跃",
            "activity_trend": "unknown",
            "activity_trend_cn": "未知",
        })

    return result


# ========== API 端点 ==========

class UpdatePersonRequest(BaseModel):
    department: Optional[str] = None
    job_title: Optional[str] = None
    job_category: Optional[str] = None
    projects: Optional[List[str]] = None
    responsibilities: Optional[List[str]] = None


@router.get("/dashboard")
async def get_people_dashboard(date: str = Query(None)):
    """获取人员仪表盘"""
    db = get_mongo_db()

    # 从 people 集合获取真正的员工
    employees = list(db.people.find({}, {"_id": 0}))
    employee_emails = {p.get("email", "").lower() for p in employees}

    # 获取这些员工的 contacts 数据
    contacts_map = {}
    for contact in db.contacts.find({"email": {"$in": list(employee_emails)}}):
        contacts_map[contact.get("email", "").lower()] = contact

    # 统计
    role_stats = {"hub": 0, "broadcaster": 0, "receiver": 0, "coordinator": 0, "peripheral": 0}
    activity_stats = {"high": 0, "medium": 0, "low": 0, "inactive": 0}
    total_health = 0
    active_count = 0

    enriched_employees = []
    for person in employees:
        email = person.get("email", "").lower()
        contact = contacts_map.get(email)
        enriched = enrich_person_with_contact(person, contact)
        enriched_employees.append(enriched)

        role_stats[enriched.get("role", "peripheral")] += 1
        activity_stats[enriched.get("activity_level", "inactive")] += 1
        total_health += enriched.get("health_score", 0)

        if enriched.get("activity_level") in ["high", "medium"]:
            active_count += 1

    avg_health = total_health / len(employees) if employees else 0

    # Top communicators
    enriched_employees.sort(key=lambda x: x.get("total_interactions", 0), reverse=True)

    return {
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "total_count": len(employees),
        "active_count": active_count,
        "avg_health_score": round(avg_health, 1),
        "role_distribution": role_stats,
        "activity_distribution": activity_stats,
        "top_communicators": enriched_employees[:10],
    }


@router.get("/list")
async def list_people(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    sort_by: str = Query("interactions", regex="^(name|interactions|health|department)$"),
    search: str = Query(None),
    department: str = Query(None),
    job_category: str = Query(None),
    role: str = Query(None, description="通信角色: hub, broadcaster, receiver, coordinator, peripheral"),
    active_only: bool = Query(False),
):
    """获取员工列表 - 基于 people 集合，join contacts 数据"""
    db = get_mongo_db()

    # 1. 从 people 集合获取真正的员工
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    if department:
        query["department"] = department

    employees = list(db.people.find(query, {"_id": 0}))
    employee_emails = [p.get("email", "").lower() for p in employees]

    # 2. 批量获取 contacts 数据
    contacts_map = {}
    for contact in db.contacts.find({"email": {"$in": employee_emails}}):
        contacts_map[contact.get("email", "").lower()] = contact

    # 3. 整合数据
    result = []
    for person in employees:
        email = person.get("email", "").lower()
        contact = contacts_map.get(email)
        enriched = enrich_person_with_contact(person, contact)

        # 职能分类过滤
        if job_category and enriched.get("job_category", "").lower() != job_category.lower():
            continue

        # 角色过滤
        if role and enriched.get("role") != role:
            continue

        # 活跃度过滤
        if active_only and enriched.get("activity_level") == "inactive":
            continue

        result.append(enriched)

    # 4. 排序
    sort_key = {
        "name": lambda x: x.get("name", "").lower(),
        "interactions": lambda x: x.get("total_interactions", 0),
        "health": lambda x: x.get("health_score", 0),
        "department": lambda x: x.get("department", ""),
    }.get(sort_by, lambda x: x.get("total_interactions", 0))

    reverse = sort_by in ["interactions", "health"]
    result.sort(key=sort_key, reverse=reverse)

    # 5. 分页
    total = len(result)
    result = result[skip:skip + limit]

    return {"people": result, "total": total}


@router.get("/roles/stats")
async def get_role_stats():
    """获取角色分布统计"""
    db = get_mongo_db()

    # 从 people 获取员工
    employees = list(db.people.find({}, {"_id": 0}))
    employee_emails = [p.get("email", "").lower() for p in employees]

    # 获取 contacts
    contacts_map = {}
    for contact in db.contacts.find({"email": {"$in": employee_emails}}):
        contacts_map[contact.get("email", "").lower()] = contact

    roles = {"hub": [], "broadcaster": [], "receiver": [], "coordinator": [], "peripheral": []}

    for person in employees:
        email = person.get("email", "").lower()
        contact = contacts_map.get(email)
        enriched = enrich_person_with_contact(person, contact)

        role = enriched.get("role", "peripheral")
        roles[role].append({
            "name": enriched.get("name"),
            "email": email,
            "job_title": enriched.get("job_title"),
            "total_interactions": enriched.get("total_interactions"),
            "health_score": enriched.get("health_score"),
        })

    # 按互动量排序
    for role in roles:
        roles[role].sort(key=lambda x: x.get("total_interactions", 0), reverse=True)

    return {
        "total": len(employees),
        "by_role": {
            "hub": {"count": len(roles["hub"]), "description": "信息枢纽 - 大量双向沟通", "members": roles["hub"][:5]},
            "broadcaster": {"count": len(roles["broadcaster"]), "description": "信息发布者 - 主要输出信息", "members": roles["broadcaster"][:5]},
            "receiver": {"count": len(roles["receiver"]), "description": "信息接收者 - 主要获取信息", "members": roles["receiver"][:5]},
            "coordinator": {"count": len(roles["coordinator"]), "description": "协调沟通者 - 均衡双向沟通", "members": roles["coordinator"][:5]},
            "peripheral": {"count": len(roles["peripheral"]), "description": "边缘角色 - 沟通量较少", "members": roles["peripheral"][:5]},
        }
    }


@router.get("/network")
async def get_people_network(limit: int = Query(20, ge=5, le=50)):
    """获取人员关系网络 (用于可视化)"""
    db = get_mongo_db()

    # 从 people 获取员工
    employees = list(db.people.find({}, {"_id": 0}))
    employee_emails = [p.get("email", "").lower() for p in employees]

    # 获取 contacts
    contacts_map = {}
    for contact in db.contacts.find({"email": {"$in": employee_emails}}):
        contacts_map[contact.get("email", "").lower()] = contact

    # 整合并排序
    enriched = []
    for person in employees:
        email = person.get("email", "").lower()
        contact = contacts_map.get(email)
        enriched.append(enrich_person_with_contact(person, contact))

    enriched.sort(key=lambda x: x.get("total_interactions", 0), reverse=True)
    top = enriched[:limit]

    nodes = []
    for p in top:
        nodes.append({
            "id": p.get("email"),
            "name": p.get("name"),
            "role": p.get("role"),
            "job_title": p.get("job_title"),
            "health_score": p.get("health_score", 0),
            "total_interactions": p.get("total_interactions", 0),
            "size": min(50, max(10, p.get("total_interactions", 0) / 500))
        })

    return {
        "nodes": nodes,
        "edges": [],  # TODO: 从邮件 thread 分析互动关系
        "stats": {
            "total_nodes": len(nodes),
            "avg_interactions": sum(n["total_interactions"] for n in nodes) / len(nodes) if nodes else 0
        }
    }


@router.get("/{user_id}")
async def get_person(user_id: str):
    """获取人员详情"""
    db = get_mongo_db()

    # 先从 people 集合查
    person = db.people.find_one({"user_id": user_id}, {"_id": 0})
    if not person:
        person = db.people.find_one({"email": {"$regex": user_id, "$options": "i"}}, {"_id": 0})

    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    email = person.get("email", "").lower()
    contact = db.contacts.find_one({"email": email})
    enriched = enrich_person_with_contact(person, contact)

    return {"person": enriched}


@router.get("/by-email/{email:path}")
async def get_person_by_email(email: str):
    """通过邮箱获取人员详情"""
    db = get_mongo_db()

    email_lower = email.lower()
    person = db.people.find_one({"email": {"$regex": f"^{email_lower}$", "$options": "i"}}, {"_id": 0})

    if not person:
        raise HTTPException(status_code=404, detail="Person not found in employee list")

    contact = db.contacts.find_one({"email": email_lower})
    enriched = enrich_person_with_contact(person, contact)

    return {"person": enriched}


@router.patch("/{user_id}")
async def update_person(user_id: str, req: UpdatePersonRequest):
    """更新人员信息"""
    db = get_mongo_db()
    updates = req.dict(exclude_none=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    result = db.people.update_one({"user_id": user_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Person not found")

    return {"success": True, "modified_count": result.modified_count}


@router.post("/sync")
async def sync_people(background_tasks: BackgroundTasks):
    """从 MS365 Graph API 同步人员数据"""
    async def do_sync():
        store = get_people_store()
        await store.init_indexes()
        await store.sync_from_ms365()
        print("[People] ✅ 人员同步完成")

    background_tasks.add_task(do_sync)
    return {"success": True, "message": "人员同步已启动"}
