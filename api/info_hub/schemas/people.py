"""
人员维度数据模型 V2
增强版 - 添加静态档案和活跃度评分
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PersonProfile(BaseModel):
    """人员档案 - 完整版"""
    user_id: str
    name: str
    email: Optional[str] = None

    # 组织架构
    department: str = "未分配"
    function: str = "未定义"
    projects: List[str] = []

    # 静态档案 (来自 MS365 或手动设置)
    job_title: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    hire_date: Optional[str] = None  # 入职日期
    manager_id: Optional[str] = None  # 上级 ID
    manager_name: Optional[str] = None  # 上级姓名

    # 活跃度指标
    email_sent_total: int = 0
    email_received_total: int = 0
    email_sent_7d: int = 0  # 近7天发送
    email_received_7d: int = 0  # 近7天接收
    last_active: Optional[str] = None

    # 活跃度评分 (0-100)
    activity_score: int = 0
    activity_level: str = "inactive"  # inactive, low, medium, high
    activity_trend: str = "stable"  # up, down, stable

    # 当日活跃详情
    daily_activity: Dict[str, Dict[str, int]] = {}

    # 元数据
    source: str = "ms365"
    synced_at: Optional[str] = None


class PersonSummary(BaseModel):
    """人员摘要 - 列表展示用"""
    user_id: str
    name: str
    email: Optional[str] = None
    department: str = "未分配"
    function: str = "未定义"
    job_title: Optional[str] = None
    avatar_url: Optional[str] = None

    # 活跃度
    activity_score: int = 0
    activity_level: str = "inactive"
    email_sent_total: int = 0
    email_received_total: int = 0
    last_active: Optional[str] = None


class DepartmentStats(BaseModel):
    """部门统计"""
    name: str
    count: int = 0
    active_count: int = 0
    email_count: int = 0
    avg_activity_score: float = 0.0


class FunctionStats(BaseModel):
    """职能统计"""
    name: str
    count: int = 0
    active_count: int = 0
    avg_activity_score: float = 0.0


class ProjectStats(BaseModel):
    """项目人员统计"""
    name: str
    count: int = 0
    active_count: int = 0


class PeopleDimensionData(BaseModel):
    """人员维度数据 - 日报用"""
    total_count: int = 0
    active_count: int = 0
    department_count: int = 0
    function_count: int = 0
    avg_activity_score: float = 0.0
    by_department: List[DepartmentStats] = []
    by_function: List[FunctionStats] = []


class PeopleDashboard(BaseModel):
    """人员仪表盘"""
    date: str
    stats: Dict[str, Any] = Field(default_factory=lambda: {
        "total_people": 0,
        "active_today": 0,
        "active_7d": 0,
        "department_count": 0,
        "function_count": 0,
        "avg_activity_score": 0.0,
    })
    by_department: List[DepartmentStats] = []
    by_function: List[FunctionStats] = []
    by_project: List[ProjectStats] = []
    top_active: List[PersonSummary] = []  # 活跃度 TOP 5


class ActivityScoreConfig(BaseModel):
    """活跃度评分配置"""
    email_sent_weight: float = 0.4
    email_received_weight: float = 0.3
    recency_weight: float = 0.3

    # 评分等级阈值
    high_threshold: int = 70
    medium_threshold: int = 40
    low_threshold: int = 10
