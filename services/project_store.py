"""
项目管理数据存储层 - MongoDB版 (Motor Async)
复用现有vulcan_brain数据库
注意: pm_employees 是独立的员工表，与系统用户(users)完全分离

v2.0 - 2026-01-13: 从 PyMongo (sync) 迁移到 Motor (async)
解决了事件循环阻塞问题，提升并发性能
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

# 导入模型
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.user import User, UserRole
from models.project import Project, ProjectStatus
from models.task import Task, TaskStatus, TaskReport
from models.kpi import ProjectKPI, calculate_project_kpi


class ProjectStore:
    """项目管理存储 - MongoDB (Async Motor)"""
    
    _instance = None
    _indexes_created = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # MongoDB连接 - Motor async client
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client["vulcan_brain"]
        
        # Collections - 注意: pm_employees 独立于系统用户
        self.employees_col = self.db["pm_employees"]  # 飞书员工，独立存储
        self.projects_col = self.db["pm_projects"]
        self.tasks_col = self.db["pm_tasks"]
        self.reports_col = self.db["pm_reports"]
        
        self._initialized = True
        print(f"[ProjectStore Motor] 异步客户端初始化完成")
    
    async def ensure_indexes(self):
        """创建索引 (首次查询时调用)"""
        if ProjectStore._indexes_created:
            return
        
        # 员工索引 - 用飞书open_id作为主键
        await self.employees_col.create_index("feishu_open_id", unique=True)
        await self.employees_col.create_index("name")
        
        # 项目索引
        await self.projects_col.create_index("owner_id")
        await self.projects_col.create_index("status")
        
        # 任务索引 - assignee_feishu_id 直接关联飞书员工
        await self.tasks_col.create_index("project_id")
        await self.tasks_col.create_index("assignee_feishu_id")
        await self.tasks_col.create_index("status")
        await self.tasks_col.create_index("deadline")
        
        # 汇报索引
        await self.reports_col.create_index("task_id")
        await self.reports_col.create_index("message_id", sparse=True, unique=True)
        await self.reports_col.create_index([("reported_at", DESCENDING)])
        
        ProjectStore._indexes_created = True
        
        # 打印统计
        emp_count = await self.employees_col.count_documents({})
        proj_count = await self.projects_col.count_documents({})
        task_count = await self.tasks_col.count_documents({})
        print(f"[ProjectStore Motor] 索引创建完成: {emp_count}员工, {proj_count}项目, {task_count}任务")
    
    # ===== Employee CRUD (飞书员工，独立于系统用户) =====
    
    async def update_employee(self, feishu_open_id: str, updates: dict):
        """更新员工信息"""
        await self.ensure_indexes()
        updates["updated_at"] = datetime.now().isoformat()
        result = await self.employees_col.update_one(
            {"feishu_open_id": feishu_open_id},
            {"$set": updates}
        )
        return result.modified_count > 0

    async def get_employee(self, feishu_open_id: str) -> Optional[Dict]:
        """通过飞书open_id获取员工"""
        await self.ensure_indexes()
        return await self.employees_col.find_one({"feishu_open_id": feishu_open_id}, {"_id": 0})
    
    async def get_employee_by_name(self, name: str) -> Optional[Dict]:
        """通过名字获取员工(模糊匹配)"""
        await self.ensure_indexes()
        return await self.employees_col.find_one(
            {"name": {"$regex": name, "$options": "i"}},
            {"_id": 0}
        )
    
    async def create_employee(self, employee_data: Dict) -> Dict:
        """创建或更新员工"""
        await self.ensure_indexes()
        feishu_id = employee_data.get("feishu_open_id")
        if not feishu_id:
            raise ValueError("员工必须有飞书open_id")
        
        employee_data["created_at"] = employee_data.get("created_at", datetime.now().isoformat())
        employee_data["updated_at"] = datetime.now().isoformat()
        
        # upsert: 存在则更新，不存在则创建
        await self.employees_col.update_one(
            {"feishu_open_id": feishu_id},
            {"$set": employee_data},
            upsert=True
        )
        return employee_data
    
    async def list_employees(self, department: Optional[str] = None) -> List[Dict]:
        """列出所有员工"""
        await self.ensure_indexes()
        query = {"department": department} if department else {}
        cursor = self.employees_col.find(query, {"_id": 0})
        return await cursor.to_list(length=None)
    
    async def delete_employee(self, feishu_open_id: str) -> bool:
        """删除员工"""
        await self.ensure_indexes()
        result = await self.employees_col.delete_one({"feishu_open_id": feishu_open_id})
        return result.deleted_count > 0
    
    # ===== Project CRUD =====
    
    async def list_projects(self, owner_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
        await self.ensure_indexes()
        query = {}
        if owner_id:
            query["owner_id"] = owner_id
        if status:
            query["status"] = status
        cursor = self.projects_col.find(query, {"_id": 0})
        return await cursor.to_list(length=None)
    
    async def get_project(self, project_id: str) -> Optional[Dict]:
        await self.ensure_indexes()
        return await self.projects_col.find_one({"id": project_id}, {"_id": 0})
    
    async def get_project_by_name(self, name: str) -> Optional[Dict]:
        """模糊匹配项目名"""
        await self.ensure_indexes()
        return await self.projects_col.find_one(
            {"name": {"$regex": name, "$options": "i"}},
            {"_id": 0}
        )
    
    async def create_project(self, project_data: Dict) -> Dict:
        await self.ensure_indexes()
        if "created_at" not in project_data:
            project_data["created_at"] = datetime.now().isoformat()
        await self.projects_col.insert_one(project_data)
        project_data.pop("_id", None)
        return project_data
    
    async def update_project(self, project_id: str, updates: Dict) -> Optional[Dict]:
        await self.ensure_indexes()
        updates["updated_at"] = datetime.now().isoformat()
        await self.projects_col.update_one({"id": project_id}, {"$set": updates})
        return await self.get_project(project_id)
    
    async def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        await self.ensure_indexes()
        result = await self.projects_col.delete_one({"id": project_id})
        return result.deleted_count > 0
    
    # ===== Task CRUD =====
    
    async def list_tasks(self, project_id: Optional[str] = None, 
                        assignee_feishu_id: Optional[str] = None,
                        status: Optional[str] = None) -> List[Dict]:
        await self.ensure_indexes()
        query = {}
        if project_id:
            query["project_id"] = project_id
        if assignee_feishu_id:
            query["assignee_feishu_id"] = assignee_feishu_id
        if status:
            query["status"] = status
        
        cursor = self.tasks_col.find(query, {"_id": 0}).sort([
            ("priority", ASCENDING),
            ("deadline", ASCENDING)
        ])
        return await cursor.to_list(length=None)
    
    async def get_task(self, task_id: str) -> Optional[Dict]:
        await self.ensure_indexes()
        return await self.tasks_col.find_one({"id": task_id}, {"_id": 0})

    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        await self.ensure_indexes()
        result = await self.tasks_col.delete_one({"id": task_id})
        return result.deleted_count > 0
    
    async def create_task(self, task_data: Dict) -> Dict:
        await self.ensure_indexes()
        if "created_at" not in task_data:
            task_data["created_at"] = datetime.now().isoformat()
        if "status" not in task_data:
            task_data["status"] = "pending"
        if "progress" not in task_data:
            task_data["progress"] = 0
        await self.tasks_col.insert_one(task_data)
        task_data.pop("_id", None)
        return task_data
    
    async def update_task(self, task_id: str, updates: Dict) -> Optional[Dict]:
        await self.ensure_indexes()
        await self.tasks_col.update_one({"id": task_id}, {"$set": updates})
        return await self.get_task(task_id)
    
    async def update_task_status(self, task_id: str, new_status: str,
                                progress: Optional[int] = None,
                                blocker_reason: Optional[str] = None) -> Optional[Dict]:
        """更新任务状态"""
        updates = {"status": new_status}
        if progress is not None:
            updates["progress"] = progress
        if blocker_reason:
            updates["blocker_reason"] = blocker_reason
        if new_status == "completed":
            updates["completed_at"] = datetime.now().isoformat()
            updates["progress"] = 100
        elif new_status == "in_progress":
            task = await self.get_task(task_id)
            if task and not task.get("started_at"):
                updates["started_at"] = datetime.now().isoformat()
        
        return await self.update_task(task_id, updates)
    
    # ===== Report CRUD =====
    
    async def add_report(self, report_data: Dict) -> Optional[Dict]:
        """添加汇报(带幂等)"""
        await self.ensure_indexes()
        # 幂等检查
        if report_data.get("message_id"):
            existing = await self.reports_col.find_one({"message_id": report_data["message_id"]})
            if existing:
                print(f"[ProjectStore] 重复消息, 跳过: {report_data['message_id']}")
                return None
        
        if "reported_at" not in report_data:
            report_data["reported_at"] = datetime.now().isoformat()
        
        await self.reports_col.insert_one(report_data)
        report_data.pop("_id", None)
        
        # 同步更新任务状态
        if report_data.get("task_id"):
            await self.update_task_status(
                report_data["task_id"],
                report_data.get("status", "in_progress"),
                report_data.get("progress"),
                "; ".join(report_data.get("blockers", []))
            )
        
        return report_data
    
    async def get_reports(self, task_id: Optional[str] = None,
                         project_id: Optional[str] = None,
                         limit: int = 50) -> List[Dict]:
        await self.ensure_indexes()
        query = {}
        if task_id:
            query["task_id"] = task_id
        if project_id:
            query["project_id"] = project_id
        
        cursor = self.reports_col.find(query, {"_id": 0}).sort("reported_at", DESCENDING).limit(limit)
        return await cursor.to_list(length=None)
    
    # ===== KPI =====
    
    async def get_project_kpi(self, project_id: str) -> Optional[Dict]:
        project = await self.get_project(project_id)
        if not project:
            return None
        
        tasks = await self.list_tasks(project_id=project_id)
        reports = await self.get_reports(project_id=project_id)
        
        # 转换为Task对象计算KPI
        task_objects = [Task(**t) for t in tasks]
        kpi = calculate_project_kpi(project_id, task_objects, len(reports))
        
        return kpi.dict()
    
    # ===== 便捷查询 =====
    
    async def get_tasks_needing_reminder(self, hours_before: int = 24) -> List[Dict]:
        """获取需要提醒的任务"""
        await self.ensure_indexes()
        deadline_threshold = (datetime.now() + timedelta(hours=hours_before)).isoformat()
        now = datetime.now().isoformat()
        
        cursor = self.tasks_col.find({
            "status": {"$in": ["pending", "in_progress"]},
            "deadline": {"$lte": deadline_threshold, "$gte": now}
        }, {"_id": 0})
        return await cursor.to_list(length=None)
    
    async def get_overdue_tasks(self) -> List[Dict]:
        """获取已逾期的任务"""
        await self.ensure_indexes()
        now = datetime.now().isoformat()
        cursor = self.tasks_col.find({
            "status": {"$nin": ["completed"]},
            "deadline": {"$lt": now}
        }, {"_id": 0})
        return await cursor.to_list(length=None)
    
    async def get_blocked_tasks(self) -> List[Dict]:
        """获取阻塞中的任务"""
        await self.ensure_indexes()
        cursor = self.tasks_col.find({"status": "blocked"}, {"_id": 0})
        return await cursor.to_list(length=None)


# 单例
_store = None

def get_project_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store
