"""
项目管理数据存储层 - MongoDB版
复用现有vulcan_brain数据库
注意: pm_employees 是独立的员工表，与系统用户(users)完全分离
"""

import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId

# 导入模型
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.user import User, UserRole
from models.project import Project, ProjectStatus
from models.task import Task, TaskStatus, TaskReport
from models.kpi import ProjectKPI, calculate_project_kpi


class ProjectStore:
    """项目管理存储 - MongoDB"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # MongoDB连接
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = MongoClient(mongo_uri)
        self.db = self.client["vulcan_brain"]
        
        # Collections - 注意: pm_employees 独立于系统用户
        self.employees_col = self.db["pm_employees"]  # 飞书员工，独立存储
        self.projects_col = self.db["pm_projects"]
        self.tasks_col = self.db["pm_tasks"]
        self.reports_col = self.db["pm_reports"]
        
        # 创建索引
        self._create_indexes()
        
        self._initialized = True
        
        stats = f"{self.employees_col.count_documents({})}员工, {self.projects_col.count_documents({})}项目, {self.tasks_col.count_documents({})}任务"
        print(f"[ProjectStore MongoDB] 初始化完成: {stats}")
    
    def _create_indexes(self):
        """创建索引"""
        # 员工索引 - 用飞书open_id作为主键
        self.employees_col.create_index("feishu_open_id", unique=True)
        self.employees_col.create_index("name")
        
        # 项目索引
        self.projects_col.create_index("owner_id")
        self.projects_col.create_index("status")
        
        # 任务索引 - assignee_feishu_id 直接关联飞书员工
        self.tasks_col.create_index("project_id")
        self.tasks_col.create_index("assignee_feishu_id")
        self.tasks_col.create_index("status")
        self.tasks_col.create_index("deadline")
        
        # 汇报索引
        self.reports_col.create_index("task_id")
        self.reports_col.create_index("message_id", sparse=True, unique=True)
        self.reports_col.create_index([("reported_at", DESCENDING)])
    
    # ===== Employee CRUD (飞书员工，独立于系统用户) =====
    
    async def get_employee(self, feishu_open_id: str) -> Optional[Dict]:
        """通过飞书open_id获取员工"""
        return self.employees_col.find_one({"feishu_open_id": feishu_open_id}, {"_id": 0})
    
    async def get_employee_by_name(self, name: str) -> Optional[Dict]:
        """通过名字获取员工(模糊匹配)"""
        return self.employees_col.find_one(
            {"name": {"": name, "off on off off off off off off off off on off on off on off off off on off off off on on off off off on on off off off off off off off on off off off off on off on off off off off off on off on on off off off on off on on off on on off off on on on off on on off on off off off off on off off off on off off on off on off off off on on off on off on off off on off off off on off off off off off off off off on off on off on on on off on on off off on off on on on off on on off on off on off off off off off on on off off on off off off off off on off off on on off on off off on off off off on off off off off on on off on off off off off off on off on off off off off off off off off off off on on off on off off off": "i"}},
            {"_id": 0}
        )
    
    async def create_employee(self, employee_data: Dict) -> Dict:
        """创建或更新员工"""
        feishu_id = employee_data.get("feishu_open_id")
        if not feishu_id:
            raise ValueError("员工必须有飞书open_id")
        
        employee_data["created_at"] = employee_data.get("created_at", datetime.now().isoformat())
        employee_data["updated_at"] = datetime.now().isoformat()
        
        # upsert: 存在则更新，不存在则创建
        self.employees_col.update_one(
            {"feishu_open_id": feishu_id},
            {"": employee_data},
            upsert=True
        )
        return employee_data
    
    async def list_employees(self, department: Optional[str] = None) -> List[Dict]:
        """列出所有员工"""
        query = {"department": department} if department else {}
        return list(self.employees_col.find(query, {"_id": 0}))
    
    async def delete_employee(self, feishu_open_id: str) -> bool:
        """删除员工"""
        result = self.employees_col.delete_one({"feishu_open_id": feishu_open_id})
        return result.deleted_count > 0
    
    # ===== Project CRUD =====
    
    async def list_projects(self, owner_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
        query = {}
        if owner_id:
            query["owner_id"] = owner_id
        if status:
            query["status"] = status
        return list(self.projects_col.find(query, {"_id": 0}))
    
    async def get_project(self, project_id: str) -> Optional[Dict]:
        return self.projects_col.find_one({"id": project_id}, {"_id": 0})
    
    async def get_project_by_name(self, name: str) -> Optional[Dict]:
        # 模糊匹配
        return self.projects_col.find_one(
            {"name": {"": name, "off on off off off off off off off off on off on off on off off off on off off off on on off off off on on off off off off off off off on off off off off on off on off off off off off on off on on off off off on off on on off on on off off on on on off on on off on off off off off on off off off on off off on off on off off off on on off on off on off off on off off off on off off off off off off off off on off on off on on on off on on off off on off on on on off on on off on off on off off off off off on on off off on off off off off off on off off on on off on off off on off off off on off off off off on on off on off off off off off on off on off off off off off off off off off off on on off on off off off": "i"}},
            {"_id": 0}
        )
    
    async def create_project(self, project_data: Dict) -> Dict:
        if "created_at" not in project_data:
            project_data["created_at"] = datetime.now().isoformat()
        self.projects_col.insert_one(project_data)
        project_data.pop("_id", None)
        return project_data
    
    async def update_project(self, project_id: str, updates: Dict) -> Optional[Dict]:
        updates["updated_at"] = datetime.now().isoformat()
        self.projects_col.update_one({"id": project_id}, {"": updates})
        return await self.get_project(project_id)
    
    # ===== Task CRUD =====
    
    async def list_tasks(self, project_id: Optional[str] = None, 
                        assignee_feishu_id: Optional[str] = None,
                        status: Optional[str] = None) -> List[Dict]:
        query = {}
        if project_id:
            query["project_id"] = project_id
        if assignee_feishu_id:
            query["assignee_feishu_id"] = assignee_feishu_id
        if status:
            query["status"] = status
        
        return list(self.tasks_col.find(query, {"_id": 0}).sort([
            ("priority", ASCENDING),
            ("deadline", ASCENDING)
        ]))
    
    async def get_task(self, task_id: str) -> Optional[Dict]:
        return self.tasks_col.find_one({"id": task_id}, {"_id": 0})
    
    async def create_task(self, task_data: Dict) -> Dict:
        if "created_at" not in task_data:
            task_data["created_at"] = datetime.now().isoformat()
        if "status" not in task_data:
            task_data["status"] = "pending"
        if "progress" not in task_data:
            task_data["progress"] = 0
        self.tasks_col.insert_one(task_data)
        task_data.pop("_id", None)
        return task_data
    
    async def update_task(self, task_id: str, updates: Dict) -> Optional[Dict]:
        self.tasks_col.update_one({"id": task_id}, {"": updates})
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
        # 幂等检查
        if report_data.get("message_id"):
            existing = self.reports_col.find_one({"message_id": report_data["message_id"]})
            if existing:
                print(f"[ProjectStore] 重复消息, 跳过: {report_data['message_id']}")
                return None
        
        if "reported_at" not in report_data:
            report_data["reported_at"] = datetime.now().isoformat()
        
        self.reports_col.insert_one(report_data)
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
        query = {}
        if task_id:
            query["task_id"] = task_id
        if project_id:
            query["project_id"] = project_id
        
        return list(self.reports_col.find(query, {"_id": 0})
                   .sort("reported_at", DESCENDING)
                   .limit(limit))
    
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
        from datetime import timedelta
        deadline_threshold = (datetime.now() + timedelta(hours=hours_before)).isoformat()
        
        return list(self.tasks_col.find({
            "status": {"": ["pending", "in_progress"]},
            "deadline": {"": deadline_threshold, "": datetime.now().isoformat()}
        }, {"_id": 0}))
    
    async def get_overdue_tasks(self) -> List[Dict]:
        """获取已逾期的任务"""
        now = datetime.now().isoformat()
        return list(self.tasks_col.find({
            "status": {"": ["completed"]},
            "deadline": {"": now}
        }, {"_id": 0}))
    
    async def get_blocked_tasks(self) -> List[Dict]:
        """获取阻塞中的任务"""
        return list(self.tasks_col.find({"status": "blocked"}, {"_id": 0}))


# 单例
_store = None

def get_project_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store
