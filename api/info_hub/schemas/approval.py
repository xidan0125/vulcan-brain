"""
审批维度数据模型
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel
from .common import AIAnalysis


class ApprovalAIAnalysis(AIAnalysis):
    """审批 AI 分析"""
    pending_attention: List[str] = []
    recommendations: List[str] = []


class ApprovalItem(BaseModel):
    """审批项"""
    instance_code: str
    approval_code: str
    approval_name: str
    status: str  # PENDING/APPROVED/REJECTED/CANCELED
    user_id: Optional[str] = None
    open_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    serial_number: str = ""


class ApprovalDefinition(BaseModel):
    """审批定义（类型）"""
    approval_code: str
    approval_name: str
    is_external: bool = False


class ApprovalDimensionData(BaseModel):
    """审批维度数据"""
    total_count: int = 0
    pending_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    by_status: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    ai_analysis: ApprovalAIAnalysis = ApprovalAIAnalysis()


class ApprovalDashboard(BaseModel):
    """审批仪表盘"""
    date: str
    stats: dict
    summary: Optional[dict] = None
    pending_count: int = 0
