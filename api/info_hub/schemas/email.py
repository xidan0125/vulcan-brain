"""
邮件维度数据模型
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from .common import AIAnalysis


class EmailContact(BaseModel):
    """邮件联系人"""
    name: str = ""
    address: str
    count: int = 0


class EmailAIAnalysis(AIAnalysis):
    """邮件 AI 分析"""
    vip_updates: List[str] = []
    urgent_matters: List[str] = []
    key_topics: List[str] = []


class EmailDimensionData(BaseModel):
    """邮件维度数据"""
    total: int = 0
    received: int = 0
    sent: int = 0
    important: int = 0
    external_count: int = 0
    top_contacts: List[EmailContact] = []
    ai_analysis: EmailAIAnalysis = EmailAIAnalysis()


class EmailItem(BaseModel):
    """邮件项"""
    email_id: str
    subject: str
    from_: dict  # {name, address}
    to: List[dict] = []
    body_preview: str = ""
    importance: str = "normal"
    is_read: bool = True
    has_attachments: bool = False
    received_at: str
    folder: str = "inbox"
    category: Optional[str] = None

    class Config:
        # 允许 from_ 映射到 from
        populate_by_name = True
        
        
class EmailListResponse(BaseModel):
    """邮件列表响应"""
    emails: List[EmailItem]
    total: int
    offset: int
    limit: int
