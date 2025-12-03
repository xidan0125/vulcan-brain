"""
项目模型 - 含OKR
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ProjectStatus(str, Enum):
    """项目状态"""
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    AT_RISK = "at_risk"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class KeyResult(BaseModel):
    """关键结果 (OKR的R)"""
    id: str
    description: str
    target_value: float
    current_value: float = 0
    unit: str = "%"  # %, 个, 天, 分
    weight: float = 1.0  # 权重
    
    @property
    def progress(self) -> float:
        if self.target_value == 0:
            return 0
        return min(100, (self.current_value / self.target_value) * 100)


class Phase(BaseModel):
    """项目阶段 (WBS第一层)"""
    id: str
    name: str
    order: int = 0
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ReminderPolicy(BaseModel):
    """提醒策略 - GPT建议的可配置项"""
    daily_report_time: str = "09:00"        # 每日汇报时间
    warn_hours_before_deadline: int = 48    # DDL前多少小时预警
    urgent_hours_before_deadline: int = 24  # DDL前多少小时紧急提醒
    max_remind_per_task: int = 5            # 每个任务最多提醒次数


class Project(BaseModel):
    """项目模型"""
    id: str
    name: str
    description: str = ""
    
    # 归属
    owner_id: str                          # 项目Owner/PM的用户ID
    owner_name: Optional[str] = None       # 冗余便于展示
    
    # OKR
    objective: str = ""                    # 目标 (O)
    key_results: List[KeyResult] = Field(default_factory=list)  # 关键结果 (KRs)
    
    # WBS
    phases: List[Phase] = Field(default_factory=list)
    
    # 状态
    status: ProjectStatus = ProjectStatus.PLANNING
    progress: int = 0                      # 0-100 (由任务计算得出)
    health_score: int = 100               # 0-100 (由KPI计算得出)
    
    # 风险
    risks: List[str] = Field(default_factory=list)
    
    # 时间
    start_date: Optional[str] = None
    target_end_date: Optional[str] = None
    actual_end_date: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # 飞书关联
    feishu_chat_id: Optional[str] = None   # 项目群ID
    
    # 提醒策略
    reminder_policy: ReminderPolicy = Field(default_factory=ReminderPolicy)
    
    # 标签
    tags: List[str] = Field(default_factory=list)
    
    @property
    def okr_progress(self) -> float:
        """OKR整体完成度"""
        if not self.key_results:
            return 0
        total_weight = sum(kr.weight for kr in self.key_results)
        if total_weight == 0:
            return 0
        weighted_progress = sum(kr.progress * kr.weight for kr in self.key_results)
        return weighted_progress / total_weight
