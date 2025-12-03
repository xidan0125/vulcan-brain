"""
人员数据服务 V2 - 五纬度信息收集系统 (维度5)

功能:
1. 从 MS365 同步员工列表
2. 支持三维度组织架构: 部门/职能/项目
3. 聚合邮件活跃度数据
4. 提供组织架构视图和人员检索
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
import os

from services.ms365_service import get_ms365_service

logger = logging.getLogger("PeopleStore")

# 职能映射规则 (从 jobTitle 推断)
FUNCTION_MAPPING = {
    "chairman": "Executive",
    "director": "Director",
    "manager": "Manager",
    "engineer": "Engineer",
    "developer": "Engineer",
    "sales": "Sales",
    "marketing": "Marketing",
    "hr": "HR",
    "finance": "Finance",
    "admin": "Admin",
}

UNDEFINED = "未定义"


class PeopleStore:
    """人员数据存储 V2"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, mongo_uri: str = None):
        if hasattr(self, "_initialized"):
            return

        self.uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client.vulcan_brain
        self.people = self.db.people
        self.ms365 = get_ms365_service()
        self._initialized = True
        logger.info("PeopleStore V2 initialized")

    async def init_indexes(self):
        """初始化索引"""
        await self.people.create_index("user_id", unique=True)
        await self.people.create_index("email")
        await self.people.create_index("name")
        await self.people.create_index("department")
        await self.people.create_index("function")
        await self.people.create_index("projects")
        await self.people.create_index([("total_emails_sent", DESCENDING)])
        logger.info("People indexes created")

    def _infer_function(self, job_title: str) -> str:
        """从职位名称推断职能分类"""
        if not job_title:
            return UNDEFINED

        title_lower = job_title.lower()
        for keyword, func in FUNCTION_MAPPING.items():
            if keyword in title_lower:
                return func
        return UNDEFINED

    def _normalize_department(self, dept: str) -> str:
        """规范化部门名称"""
        if not dept:
            return UNDEFINED
        # 去除多余空格
        dept = dept.strip()
        # 统一格式
        if "sales" in dept.lower() or "marketing" in dept.lower():
            return "Sales & Marketing"
        if "hr" in dept.lower() or "human" in dept.lower():
            return "HR"
        if "tech" in dept.lower() or "engineer" in dept.lower() or "dev" in dept.lower():
            return "Technology"
        if "finance" in dept.lower() or "account" in dept.lower():
            return "Finance"
        return dept

    async def sync_from_ms365(self) -> Dict[str, int]:
        """从 MS365 同步用户列表"""
        logger.info("开始从 MS365 同步用户...")

        try:
            users = await self.ms365.get_users(top=200)
        except Exception as e:
            logger.error(f"获取 MS365 用户失败: {e}")
            return {"error": str(e)}

        inserted = 0
        updated = 0

        for user in users:
            user_id = user.get("id")
            if not user_id:
                continue

            # 跳过会议室等非人员账号
            display_name = user.get("displayName", "")
            if any(x in display_name.lower() for x in ["room", "board", "office", "conference"]):
                continue

            # 提取并规范化组织架构
            raw_dept = user.get("department", "")
            raw_title = user.get("jobTitle", "")

            person = {
                "user_id": user_id,
                "name": display_name,
                "email": user.get("mail", "").lower() if user.get("mail") else None,

                # 三维度组织架构
                "department": self._normalize_department(raw_dept),
                "function": self._infer_function(raw_title),
                "projects": [],  # 默认空，后续可手动分配

                # 保留原始数据
                "ms365_job_title": raw_title or None,
                "ms365_department": raw_dept or None,

                # 元数据
                "source": "ms365",
                "synced_at": datetime.now(),
            }

            result = await self.people.update_one(
                {"user_id": user_id},
                {
                    "$set": person,
                    "$setOnInsert": {
                        "created_at": datetime.now(),
                        "total_emails_sent": 0,
                        "total_emails_received": 0,
                        "daily_activity": {},
                    }
                },
                upsert=True
            )

            if result.upserted_id:
                inserted += 1
            elif result.modified_count:
                updated += 1

        logger.info(f"MS365 同步完成: 新增 {inserted}, 更新 {updated}")
        return {"inserted": inserted, "updated": updated, "total": len(users)}

    async def update_email_activity(self, date: datetime = None) -> Dict:
        """更新邮件活跃度数据"""
        if date is None:
            date = datetime.now() - timedelta(days=1)

        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        date_str = date.strftime("%Y-%m-%d")

        logger.info(f"更新 {date_str} 邮件活跃度...")

        # 聚合发件统计
        sent_pipeline = [
            {"$match": {
                "folder": "sentItems",
                "received_at": {"$gte": start, "$lt": end}
            }},
            {"$group": {
                "_id": {"$toLower": "$from.address"},
                "sent_count": {"$sum": 1}
            }}
        ]

        # 聚合收件统计
        received_pipeline = [
            {"$match": {
                "folder": "inbox",
                "received_at": {"$gte": start, "$lt": end}
            }},
            {"$unwind": "$to"},
            {"$group": {
                "_id": {"$toLower": "$to.address"},
                "received_count": {"$sum": 1}
            }}
        ]

        sent_stats = {doc["_id"]: doc["sent_count"]
                      async for doc in self.db.emails.aggregate(sent_pipeline)}
        received_stats = {doc["_id"]: doc["received_count"]
                          async for doc in self.db.emails.aggregate(received_pipeline)}

        # 更新每个人的活跃度
        updated = 0
        async for person in self.people.find({"email": {"$ne": None}}):
            email = person.get("email", "").lower()
            if not email:
                continue

            sent = sent_stats.get(email, 0)
            received = received_stats.get(email, 0)

            if sent > 0 or received > 0:
                await self.people.update_one(
                    {"_id": person["_id"]},
                    {
                        "$set": {
                            f"daily_activity.{date_str}": {
                                "email_sent": sent,
                                "email_received": received,
                                "total": sent + received
                            },
                            "last_active": date,
                        },
                        "$inc": {
                            "total_emails_sent": sent,
                            "total_emails_received": received,
                        }
                    }
                )
                updated += 1

        logger.info(f"活跃度更新完成: {updated} 人有活动")
        return {"date": date_str, "updated": updated}

    async def get_dashboard(self, date: datetime = None) -> Dict:
        """
        获取人员管理仪表盘数据

        返回三维度组织架构视图 + 活跃度统计
        """
        if date is None:
            date = datetime.now()

        date_str = date.strftime("%Y-%m-%d")

        # 总人数
        total_people = await self.people.count_documents({})

        # 当日活跃人数
        active_query = {f"daily_activity.{date_str}": {"$exists": True}}
        active_count = await self.people.count_documents(active_query)

        # 按部门分组
        dept_pipeline = [
            {"$group": {
                "_id": "$department",
                "count": {"$sum": 1},
                "emails": {"$sum": {"$ifNull": [f"$daily_activity.{date_str}.total", 0]}}
            }},
            {"$sort": {"count": -1}}
        ]
        by_department = []
        async for doc in self.people.aggregate(dept_pipeline):
            dept_name = doc["_id"] or UNDEFINED
            # 计算该部门活跃人数
            dept_active = await self.people.count_documents({
                "department": doc["_id"],
                f"daily_activity.{date_str}": {"$exists": True}
            })
            by_department.append({
                "name": dept_name,
                "count": doc["count"],
                "active_count": dept_active,
                "email_count": doc["emails"]
            })

        # 按职能分组
        func_pipeline = [
            {"$group": {
                "_id": "$function",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        by_function = []
        async for doc in self.people.aggregate(func_pipeline):
            func_name = doc["_id"] or UNDEFINED
            func_active = await self.people.count_documents({
                "function": doc["_id"],
                f"daily_activity.{date_str}": {"$exists": True}
            })
            by_function.append({
                "name": func_name,
                "count": doc["count"],
                "active_count": func_active
            })

        # 按项目分组 (展开 projects 数组)
        proj_pipeline = [
            {"$unwind": {"path": "$projects", "preserveNullAndEmptyArrays": True}},
            {"$group": {
                "_id": {"$ifNull": ["$projects", UNDEFINED]},
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        by_project = []
        async for doc in self.people.aggregate(proj_pipeline):
            by_project.append({
                "name": doc["_id"],
                "count": doc["count"],
                "active_count": 0  # TODO: 计算项目活跃度
            })

        # 统计维度数量
        dept_count = len([d for d in by_department if d["name"] != UNDEFINED])
        func_count = len([f for f in by_function if f["name"] != UNDEFINED])
        proj_count = len([p for p in by_project if p["name"] != UNDEFINED])

        return {
            "date": date_str,
            "stats": {
                "total_people": total_people,
                "active_today": active_count,
                "department_count": dept_count,
                "function_count": func_count,
                "project_count": proj_count,
            },
            "by_department": by_department,
            "by_function": by_function,
            "by_project": by_project,
        }

    async def get_people(
        self,
        limit: int = 100,
        skip: int = 0,
        sort_by: str = "name",
        search: str = None,
        department: str = None,
        function: str = None,
        project: str = None,
    ) -> tuple[List[Dict], int]:
        """获取人员列表，支持筛选"""
        query = {}

        # 筛选条件
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
            ]

        if department:
            query["department"] = department
        if function:
            query["function"] = function
        if project:
            query["projects"] = project

        # 排序
        sort_field = "name"
        sort_order = ASCENDING
        if sort_by == "activity":
            sort_field = "total_emails_sent"
            sort_order = DESCENDING
        elif sort_by == "department":
            sort_field = "department"

        total = await self.people.count_documents(query)
        cursor = self.people.find(query).sort(sort_field, sort_order).skip(skip).limit(limit)

        people = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            people.append(doc)

        return people, total

    async def get_person(self, user_id: str) -> Optional[Dict]:
        """获取单个人员详情"""
        doc = await self.people.find_one({"user_id": user_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def update_person(self, user_id: str, updates: Dict) -> bool:
        """更新人员信息 (手动分配部门/职能/项目)"""
        allowed_fields = ["department", "function", "projects"]
        safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not safe_updates:
            return False

        result = await self.people.update_one(
            {"user_id": user_id},
            {"$set": safe_updates}
        )
        return result.modified_count > 0


# ===== 便捷函数 =====

_store = None

def get_people_store() -> PeopleStore:
    """获取人员存储实例"""
    global _store
    if _store is None:
        _store = PeopleStore()
    return _store


async def sync_people_from_ms365() -> Dict:
    """同步人员 (便捷函数)"""
    store = get_people_store()
    return await store.sync_from_ms365()


async def get_people_dashboard(date: datetime = None) -> Dict:
    """获取人员仪表盘 (便捷函数)"""
    store = get_people_store()
    return await store.get_dashboard(date)
