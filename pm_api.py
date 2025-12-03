"""
项目管理 API
/api/pm/...

注意: 员工(pm_employees)独立于系统用户(users)
- 系统用户: admin/jasonsun/tonysun (管理员，有系统登录权限)
- 员工: 存储飞书open_id，只用于任务分配和通知
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from services.project_store import get_project_store

router = APIRouter(prefix="/api/pm", tags=["Project Management"])


# ==================== Request/Response Models ====================

class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    objective: str = ""
    owner_id: str
    owner_name: str = ""
    deadline: Optional[str] = None

class CreateTaskRequest(BaseModel):
    project_id: str
    title: str
    assignee_feishu_id: str  # 直接用飞书open_id
    assignee_name: str = ""  # 可选的显示名
    deadline: Optional[str] = None
    priority: int = 3
    description: str = ""
    notify: bool = True  # 是否发送飞书通知

class UpdateTaskStatusRequest(BaseModel):
    status: str  # pending/in_progress/blocked/completed
    progress: Optional[int] = None
    blocker_reason: Optional[str] = None

class CreateReportRequest(BaseModel):
    task_id: str
    status: str
    progress: int
    notes: str = ""
    blockers: List[str] = []
    message_id: Optional[str] = None  # 飞书消息ID(幂等)

class CreateEmployeeRequest(BaseModel):
    feishu_open_id: str
    name: str
    department: str = ""
    role: str = "member"


# ==================== Project APIs ====================

@router.get("/projects")
async def list_projects(owner_id: Optional[str] = None, status: Optional[str] = None):
    """获取项目列表"""
    store = get_project_store()
    projects = await store.list_projects(owner_id=owner_id, status=status)
    
    result = []
    for p in projects:
        tasks = await store.list_tasks(project_id=p["id"])
        p["task_count"] = len(tasks)
        p["completed_count"] = len([t for t in tasks if t.get("status") == "completed"])
        p["at_risk_count"] = len([t for t in tasks if t.get("status") in ["blocked", "overdue"]])
        result.append(p)
    
    return {"projects": result}


@router.post("/projects")
async def create_project(req: CreateProjectRequest):
    """创建项目"""
    store = get_project_store()
    project_data = {
        "id": f"proj-{uuid.uuid4().hex[:8]}",
        "name": req.name,
        "description": req.description,
        "objective": req.objective,
        "owner_id": req.owner_id,
        "owner_name": req.owner_name,
        "deadline": req.deadline,
        "status": "in_progress",
        "progress": 0,
        "health_score": 100,
        "created_at": datetime.now().isoformat()
    }
    result = await store.create_project(project_data)
    return {"success": True, "project": result}


@router.get("/projects/{project_id}")
async def get_project(project_id: str, with_tasks: bool = False):
    """获取项目详情"""
    store = get_project_store()
    project = await store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    result = {"project": project}
    
    if with_tasks:
        tasks = await store.list_tasks(project_id=project_id)
        result["tasks"] = tasks
    
    return result


@router.put("/projects/{project_id}")
async def update_project(project_id: str, updates: dict):
    """更新项目"""
    store = get_project_store()
    result = await store.update_project(project_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True, "project": result}


# ==================== Task APIs ====================

@router.get("/tasks")
async def list_tasks(
    project_id: Optional[str] = None,
    assignee_feishu_id: Optional[str] = None,
    status: Optional[str] = None
):
    """获取任务列表"""
    store = get_project_store()
    tasks = await store.list_tasks(
        project_id=project_id,
        assignee_feishu_id=assignee_feishu_id,
        status=status
    )
    return {"tasks": tasks}


@router.post("/tasks")
async def create_task(req: CreateTaskRequest, background_tasks: BackgroundTasks):
    """创建任务 - 自动发送飞书通知"""
    store = get_project_store()
    
    # 验证项目存在
    project = await store.get_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 如果提供了飞书ID但没有名字，尝试从员工表获取
    assignee_name = req.assignee_name
    if not assignee_name and req.assignee_feishu_id:
        employee = await store.get_employee(req.assignee_feishu_id)
        if employee:
            assignee_name = employee.get("name", "未知")
    
    task_data = {
        "id": f"task-{uuid.uuid4().hex[:8]}",
        "project_id": req.project_id,
        "title": req.title,
        "description": req.description,
        "assignee_feishu_id": req.assignee_feishu_id,  # 直接存飞书ID
        "assignee_name": assignee_name,
        "deadline": req.deadline,
        "priority": req.priority,
        "status": "pending",
        "progress": 0,
        "created_at": datetime.now().isoformat()
    }
    result = await store.create_task(task_data)
    
    # 后台发送飞书通知
    if req.notify:
        background_tasks.add_task(
            _send_task_notification,
            task_data,
            project.get("name", "")
        )
    
    return {"success": True, "task": result, "notification_queued": req.notify}


async def _send_task_notification(task: dict, project_name: str):
    """后台发送任务分配通知"""
    try:
        from tools.feishu_tools import notify_task_assignment
        result = await notify_task_assignment(task, project_name)
        print(f"[PM API] 任务通知结果: {result}")
    except Exception as e:
        print(f"[PM API] 任务通知失败: {e}")
        import traceback
        traceback.print_exc()


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情"""
    store = get_project_store()
    task = await store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task}


@router.put("/tasks/{task_id}/status")
async def update_task_status(task_id: str, req: UpdateTaskStatusRequest):
    """更新任务状态"""
    store = get_project_store()
    result = await store.update_task_status(
        task_id,
        req.status,
        req.progress,
        req.blocker_reason
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task": result}


@router.post("/tasks/{task_id}/notify")
async def send_task_notification(task_id: str):
    """手动发送/重发任务通知"""
    store = get_project_store()
    
    task = await store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = await store.get_project(task.get("project_id", ""))
    project_name = project.get("name", "") if project else ""
    
    try:
        from tools.feishu_tools import notify_task_assignment
        result = await notify_task_assignment(task, project_name)
        return {"success": result.get("success", False), "detail": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== Report APIs ====================

@router.post("/reports")
async def create_report(req: CreateReportRequest):
    """创建汇报"""
    store = get_project_store()
    
    task = await store.get_task(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    report_data = {
        "id": f"report-{uuid.uuid4().hex[:8]}",
        "task_id": req.task_id,
        "project_id": task.get("project_id"),
        "reporter_feishu_id": task.get("assignee_feishu_id"),
        "status": req.status,
        "progress": req.progress,
        "notes": req.notes,
        "blockers": req.blockers,
        "message_id": req.message_id,
        "reported_at": datetime.now().isoformat()
    }
    
    result = await store.add_report(report_data)
    return {"success": True, "report": result}


@router.get("/reports")
async def list_reports(
    task_id: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 50
):
    """获取汇报列表"""
    store = get_project_store()
    reports = await store.get_reports(task_id=task_id, project_id=project_id, limit=limit)
    return {"reports": reports}


# ==================== Dashboard APIs ====================

@router.get("/dashboard")
async def get_dashboard():
    """获取看板数据 - War Room用"""
    store = get_project_store()
    
    projects = await store.list_projects()
    all_tasks = await store.list_tasks()
    recent_reports = await store.get_reports(limit=20)
    
    total_projects = len(projects)
    total_tasks = len(all_tasks)
    
    task_stats = {
        "pending": len([t for t in all_tasks if t.get("status") == "pending"]),
        "in_progress": len([t for t in all_tasks if t.get("status") == "in_progress"]),
        "blocked": len([t for t in all_tasks if t.get("status") == "blocked"]),
        "completed": len([t for t in all_tasks if t.get("status") == "completed"]),
    }
    
    on_track = len([p for p in projects if p.get("status") in ["in_progress", "completed"]])
    at_risk = len([p for p in projects if p.get("status") == "at_risk"])
    
    overdue_tasks = await store.get_overdue_tasks()
    blocked_tasks = await store.get_blocked_tasks()
    
    return {
        "summary": {
            "total_projects": total_projects,
            "total_tasks": total_tasks,
            "on_track": on_track,
            "at_risk": at_risk,
        },
        "task_stats": task_stats,
        "overdue_tasks": overdue_tasks,
        "blocked_tasks": blocked_tasks,
        "recent_reports": recent_reports,
        "projects": projects
    }


# ==================== Employee APIs (独立于系统用户) ====================

@router.get("/employees")
async def list_employees(department: Optional[str] = None):
    """获取员工列表 - 这些是飞书员工，不是系统用户"""
    store = get_project_store()
    employees = await store.list_employees(department=department)
    return {"employees": employees}


@router.post("/employees")
async def create_employee(req: CreateEmployeeRequest):
    """添加员工 - 存储飞书ID用于任务分配"""
    store = get_project_store()
    
    employee_data = {
        "feishu_open_id": req.feishu_open_id,
        "name": req.name,
        "department": req.department,
        "role": req.role
    }
    
    result = await store.create_employee(employee_data)
    return {"success": True, "employee": result}


@router.get("/employees/{feishu_open_id}")
async def get_employee(feishu_open_id: str):
    """获取员工信息"""
    store = get_project_store()
    employee = await store.get_employee(feishu_open_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"employee": employee}


@router.delete("/employees/{feishu_open_id}")
async def delete_employee(feishu_open_id: str):
    """删除员工"""
    store = get_project_store()
    success = await store.delete_employee(feishu_open_id)
    if not success:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"success": True}


# ==================== Progress Check API ====================

@router.post("/tasks/{task_id}/progress-check")
async def send_progress_check(task_id: str):
    """发送进度确认卡片（绿黄红三灯）"""
    store = get_project_store()
    
    task = await store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = await store.get_project(task.get("project_id", ""))
    project_name = project.get("name", "") if project else ""
    
    try:
        from tools.feishu_tools import send_progress_check
        result = await send_progress_check(task, project_name)
        return {"success": result.get("success", False), "detail": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ===== Users API (前端兼容) =====
@router.get("/users")
async def get_users():
    """获取用户列表（前端兼容接口）"""
    store = get_project_store()
    employees = await store.list_employees()
    users = [
        {
            "id": emp.get("feishu_open_id"),
            "name": emp.get("name", "未知"),
            "role": emp.get("role", "member")
        }
        for emp in employees
    ]
    return {"users": users}
