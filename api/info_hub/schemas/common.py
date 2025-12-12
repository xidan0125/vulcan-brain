"""
通用数据模型
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """统一 API 响应格式"""
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None


class PaginatedResponse(BaseModel):
    """分页响应"""
    items: List[Any]
    total: int
    limit: int
    offset: int


class DateRangeRequest(BaseModel):
    """日期范围请求"""
    date: Optional[str] = None  # YYYY-MM-DD
    days: int = Field(default=7, ge=1, le=30)


class GenerateRequest(BaseModel):
    """生成请求 (日报等)"""
    date: Optional[str] = None  # YYYY-MM-DD，默认昨天
    force: bool = False  # 是否强制覆盖


# ===== 维度统计基类 =====

class DimensionStats(BaseModel):
    """维度统计基类"""
    total: int = 0
    
    
class AIAnalysis(BaseModel):
    """AI 分析结果基类"""
    summary: str = ""
    action_items: List[str] = []
    risks: List[str] = []
    highlights: List[str] = []
    sentiment: str = "neutral"  # positive/neutral/negative
