"""
Email Intelligence V2.0 - Action Item Model
待办事项模型 (AI 提取的待办)
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field

from .base import MongoModel


class ActionItemType(str, Enum):
    """待办类型"""
    COMPLIANCE_RENEWAL = "COMPLIANCE_RENEWAL"   # 合规文档更新
    FOLLOW_UP = "FOLLOW_UP"                     # 跟进
    PAYMENT_REMINDER = "PAYMENT_REMINDER"       # 付款提醒
    SHIPPING_ISSUE = "SHIPPING_ISSUE"           # 物流问题
    QUALITY_ISSUE = "QUALITY_ISSUE"             # 质量问题
    QUOTE_NEEDED = "QUOTE_NEEDED"               # 需要报价
    ORDER_CONFIRMATION = "ORDER_CONFIRMATION"   # 订单确认
    DOCUMENT_REQUEST = "DOCUMENT_REQUEST"       # 文档请求
    REVIEW_REQUIRED = "REVIEW_REQUIRED"         # 需要审核
    ENTITY_MERGE = "ENTITY_MERGE"               # 实体合并审核
    OTHER = "OTHER"


class ActionItemPriority(str, Enum):
    """优先级"""
    CRITICAL = "CRITICAL"       # 紧急 (红色)
    HIGH = "HIGH"               # 高 (橙色)
    MEDIUM = "MEDIUM"           # 中 (黄色)
    LOW = "LOW"                 # 低 (灰色)


class ActionItemStatus(str, Enum):
    """状态"""
    PENDING = "PENDING"         # 待处理
    IN_PROGRESS = "IN_PROGRESS" # 处理中
    COMPLETED = "COMPLETED"     # 已完成
    DISMISSED = "DISMISSED"     # 已忽略
    AUTO_RESOLVED = "AUTO_RESOLVED"  # 自动解决


class ActionType(str, Enum):
    """建议的操作类型"""
    SEND_EMAIL = "SEND_EMAIL"       # 发送邮件
    UPDATE_RECORD = "UPDATE_RECORD" # 更新记录
    CREATE_TASK = "CREATE_TASK"     # 创建任务
    ESCALATE = "ESCALATE"           # 升级处理
    REVIEW = "REVIEW"               # 审核
    MERGE_ENTITIES = "MERGE_ENTITIES"  # 合并实体
    NONE = "NONE"


class RelatedObject(BaseModel):
    """关联对象"""
    collection: str
    object_id: str
    object_ref: Optional[str] = None  # 可读引用


class Context(BaseModel):
    """来源上下文"""
    trigger_type: str = "EMAIL_RECEIVED"  # COMPLIANCE_EXPIRY, EMAIL_RECEIVED, SCHEDULE, MANUAL
    source_email_id: Optional[str] = None
    source_email_event_id: Optional[str] = None
    related_objects: List[RelatedObject] = Field(default_factory=list)


class DraftEmail(BaseModel):
    """草拟邮件"""
    to: Optional[str] = None
    cc: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class SuggestedAction(BaseModel):
    """AI 建议的操作"""
    action_type: ActionType = ActionType.NONE
    draft_email: Optional[DraftEmail] = None
    ai_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: Optional[str] = None

    class Config:
        use_enum_values = True


class Assignment(BaseModel):
    """分配信息"""
    assignee: Optional[str] = None      # 负责人邮箱
    assigned_at: Optional[datetime] = None
    due_date: Optional[datetime] = None


class Resolution(BaseModel):
    """处理记录"""
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_type: Optional[str] = None  # ACTIONED, DISMISSED, AUTO_RESOLVED
    notes: Optional[str] = None
    follow_up_action_id: Optional[str] = None  # 如果产生新的待办


class Scoring(BaseModel):
    """评分因子 (用于排序)"""
    base_score: int = 50
    urgency_bonus: int = 0              # 紧急度加分
    financial_bonus: int = 0            # 涉及金额
    compliance_bonus: int = 0           # 合规相关
    customer_tier_bonus: int = 0        # 客户等级
    total_score: int = 50               # 最终优先级分数

    def calculate_total(self):
        """计算总分"""
        self.total_score = (
            self.base_score +
            self.urgency_bonus +
            self.financial_bonus +
            self.compliance_bonus +
            self.customer_tier_bonus
        )


class ActionItem(MongoModel):
    """
    待办事项 (AI 提取的待办)

    设计决策：这一层直接连接 AI 和人。
    AI 不敢直接改数据库，但可以"提议"。管理员只需点 Confirm。
    这是 B2B 系统最稳健的 Human-in-the-Loop 模式。
    """
    # 基本信息
    item_type: ActionItemType
    priority: ActionItemPriority = ActionItemPriority.MEDIUM
    status: ActionItemStatus = ActionItemStatus.PENDING

    # 内容
    title: str = Field(..., min_length=1, description="标题")
    description: Optional[str] = None

    # 来源上下文
    context: Context = Field(default_factory=Context)

    # AI 建议
    suggested_action: SuggestedAction = Field(default_factory=SuggestedAction)

    # 分配
    assignment: Assignment = Field(default_factory=Assignment)

    # 处理记录
    resolution: Optional[Resolution] = None

    # 评分
    scoring: Scoring = Field(default_factory=Scoring)

    class Config:
        use_enum_values = True

    def assign_to(self, assignee: str, due_date: Optional[datetime] = None):
        """分配给某人"""
        self.assignment.assignee = assignee
        self.assignment.assigned_at = datetime.utcnow()
        self.assignment.due_date = due_date
        self.updated_at = datetime.utcnow()

    def mark_in_progress(self):
        """标记为处理中"""
        self.status = ActionItemStatus.IN_PROGRESS
        self.updated_at = datetime.utcnow()

    def complete(self, resolved_by: str, notes: Optional[str] = None):
        """完成"""
        self.status = ActionItemStatus.COMPLETED
        self.resolution = Resolution(
            resolved_at=datetime.utcnow(),
            resolved_by=resolved_by,
            resolution_type="ACTIONED",
            notes=notes
        )
        self.updated_at = datetime.utcnow()

    def dismiss(self, dismissed_by: str, reason: Optional[str] = None):
        """忽略"""
        self.status = ActionItemStatus.DISMISSED
        self.resolution = Resolution(
            resolved_at=datetime.utcnow(),
            resolved_by=dismissed_by,
            resolution_type="DISMISSED",
            notes=reason
        )
        self.updated_at = datetime.utcnow()

    def is_overdue(self) -> bool:
        """是否逾期"""
        if not self.assignment.due_date:
            return False
        if self.status in [ActionItemStatus.COMPLETED, ActionItemStatus.DISMISSED]:
            return False
        return datetime.utcnow() > self.assignment.due_date

    def calculate_priority_score(
        self,
        is_urgent: bool = False,
        has_financial_impact: bool = False,
        is_compliance: bool = False,
        customer_tier: str = "NORMAL"
    ):
        """计算优先级分数"""
        self.scoring.base_score = 50

        if is_urgent:
            self.scoring.urgency_bonus = 30
        if has_financial_impact:
            self.scoring.financial_bonus = 20
        if is_compliance:
            self.scoring.compliance_bonus = 25

        tier_bonus = {
            "STRATEGIC": 30,
            "KEY": 20,
            "NORMAL": 0,
            "INACTIVE": -10
        }
        self.scoring.customer_tier_bonus = tier_bonus.get(customer_tier, 0)

        self.scoring.calculate_total()

        # 根据分数设置优先级
        if self.scoring.total_score >= 100:
            self.priority = ActionItemPriority.CRITICAL
        elif self.scoring.total_score >= 80:
            self.priority = ActionItemPriority.HIGH
        elif self.scoring.total_score >= 50:
            self.priority = ActionItemPriority.MEDIUM
        else:
            self.priority = ActionItemPriority.LOW


# 索引定义
ACTION_ITEM_INDEXES = [
    {"keys": [("status", 1), ("scoring.total_score", -1)]},
    {"keys": [("item_type", 1), ("status", 1)]},
    {"keys": [("assignment.assignee", 1), ("status", 1)]},
    {"keys": [("assignment.due_date", 1)]},
    {"keys": [("context.source_email_id", 1)]},
    {"keys": [("priority", 1), ("status", 1)]},
    {"keys": [("created_at", -1)]},
]
