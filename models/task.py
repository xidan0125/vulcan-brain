"""
任务模型 - 含状态机
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"           # 待开始
    IN_PROGRESS = "in_progress"   # 进行中
    BLOCKED = "blocked"           # 阻塞
    COMPLETED = "completed"       # 已完成
    OVERDUE = "overdue"           # 已逾期(未完成)


# 状态转换表 - GPT建议的状态机
TASK_TRANSITIONS = {
    TaskStatus.PENDING: [TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED],
    TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.BLOCKED, TaskStatus.OVERDUE],
    TaskStatus.BLOCKED: [TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE],
    TaskStatus.COMPLETED: [],  # 终态
    TaskStatus.OVERDUE: [TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED],  # 可恢复
}


class Task(BaseModel):
    """任务模型"""
    id: str
    project_id: str
    phase: str = "default"         # 所属阶段
    title: str
    description: str = ""
    
    # 分配
    assignee_id: Optional[str] = None   # 负责人ID
    assignee_name: Optional[str] = None # 负责人姓名(冗余便于展示)
    
    # 时间
    deadline: Optional[str] = None      # DDL (ISO格式)
    estimated_hours: float = 0          # 预估工时
    actual_hours: float = 0             # 实际工时
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None    # 开始时间
    completed_at: Optional[str] = None  # 完成时间
    
    # 状态
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0                   # 0-100
    priority: int = 3                   # 1-5, 1最高
    
    # 依赖
    dependencies: List[str] = Field(default_factory=list)  # 依赖的任务ID
    
    # 阻塞信息
    blocker_reason: Optional[str] = None
    blocker_reported_at: Optional[str] = None
    
    # 提醒
    last_reminded_at: Optional[str] = None
    remind_count: int = 0               # 被提醒次数
    
    def can_transition_to(self, new_status: TaskStatus) -> bool:
        """检查是否可以转换到新状态"""
        allowed = TASK_TRANSITIONS.get(self.status, [])
        return new_status in allowed
    
    def transition_to(self, new_status: TaskStatus) -> bool:
        """执行状态转换"""
        if not self.can_transition_to(new_status):
            return False
        
        old_status = self.status
        self.status = new_status
        
        # 状态变更时的副作用
        if new_status == TaskStatus.IN_PROGRESS and old_status == TaskStatus.PENDING:
            self.started_at = datetime.now().isoformat()
        elif new_status == TaskStatus.COMPLETED:
            self.completed_at = datetime.now().isoformat()
            self.progress = 100
        elif new_status == TaskStatus.BLOCKED:
            self.blocker_reported_at = datetime.now().isoformat()
        
        return True
    
    def is_overdue(self) -> bool:
        """检查是否已逾期"""
        if not self.deadline or self.status == TaskStatus.COMPLETED:
            return False
        return datetime.now().isoformat() > self.deadline
    
    def hours_until_deadline(self) -> Optional[float]:
        """距离DDL还有多少小时"""
        if not self.deadline:
            return None
        try:
            ddl = datetime.fromisoformat(self.deadline.replace('Z', '+00:00'))
            now = datetime.now(ddl.tzinfo) if ddl.tzinfo else datetime.now()
            delta = ddl - now
            return delta.total_seconds() / 3600
        except:
            return None


class TaskReport(BaseModel):
    """任务汇报记录"""
    id: str
    task_id: str
    project_id: str
    reporter_id: str
    reporter_name: Optional[str] = None
    
    # 汇报内容
    status: TaskStatus                  # 汇报的状态
    progress: int                       # 汇报的进度 0-100
    notes: str = ""                     # 文字说明
    blockers: List[str] = Field(default_factory=list)  # 阻塞原因列表
    
    # 元数据
    reported_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    source: str = "feishu"              # feishu / web / api
    message_id: Optional[str] = None    # 飞书消息ID(用于幂等)
    
    # AI分析结果
    ai_analysis: Optional[Dict[str, Any]] = None
