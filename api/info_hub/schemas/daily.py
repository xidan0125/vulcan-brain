"""
日报数据模型
五维度统一格式
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from .chat import ChatDimensionData
from .email import EmailDimensionData
from .people import PeopleDimensionData
from .approval import ApprovalDimensionData


class ProjectDimensionData(BaseModel):
    """项目维度数据 (占位)"""
    total_count: int = 0
    in_progress: int = 0
    completed: int = 0
    blocked: int = 0
    # TODO: Phase 2 实现


class DimensionOverview(BaseModel):
    """维度概览（用于快速展示）"""
    chat: dict = {"total_messages": 0, "total_decisions": 0, "total_risks": 0}
    email: dict = {"total": 0, "important": 0, "external": 0}
    people: dict = {"total_count": 0, "active_count": 0}
    approval: dict = {"total_count": 0, "pending_count": 0}
    project: dict = {"total_count": 0, "in_progress": 0}


class DailyReport(BaseModel):
    """每日日报 - 核心数据结构"""
    date: str  # YYYY-MM-DD
    generated_at: Optional[str] = None
    
    # 五维度数据
    chat: ChatDimensionData = ChatDimensionData()
    email: EmailDimensionData = EmailDimensionData()
    people: PeopleDimensionData = PeopleDimensionData()
    approval: ApprovalDimensionData = ApprovalDimensionData()
    project: ProjectDimensionData = ProjectDimensionData()
    
    # 概览
    overview: DimensionOverview = DimensionOverview()


class DailyReportResponse(BaseModel):
    """日报响应"""
    report: DailyReport


class ReportOverview(BaseModel):
    """日报概览（列表用）"""
    latest_report_date: Optional[str] = None
    report_count: int = 0
    dates: List[str] = []
