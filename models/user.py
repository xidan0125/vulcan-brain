"""
用户模型 - 权限控制
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class UserRole(str, Enum):
    """用户角色"""
    BOSS = "boss"      # 老板：跨项目查看&操作
    PM = "pm"          # 项目经理：管理自己负责的项目
    MEMBER = "member"  # 成员：只能看到/汇报自己的任务


class User(BaseModel):
    """用户模型"""
    id: str                          # 用户ID (可用飞书open_id)
    name: str                        # 姓名
    feishu_open_id: Optional[str] = None   # 飞书Open ID
    feishu_user_id: Optional[str] = None   # 飞书User ID  
    role: UserRole = UserRole.MEMBER
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = True
    
    # 统计
    total_tasks: int = 0
    completed_tasks: int = 0
    report_rate: float = 1.0  # 汇报率 0-1
    
    def can_view_all_projects(self) -> bool:
        return self.role == UserRole.BOSS
    
    def can_manage_project(self, project_owner_id: str) -> bool:
        return self.role == UserRole.BOSS or self.id == project_owner_id
    
    def can_view_task(self, task_assignee_id: str) -> bool:
        return self.role in [UserRole.BOSS, UserRole.PM] or self.id == task_assignee_id
