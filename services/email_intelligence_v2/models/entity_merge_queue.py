"""
Email Intelligence V2.0 - Entity Merge Queue Model
实体合并队列模型 (待人工确认的实体合并建议)
"""
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field

from .base import MongoModel, MatchType


class MergeQueueStatus(str, Enum):
    """队列状态"""
    PENDING = "PENDING"         # 待审核
    APPROVED = "APPROVED"       # 已批准
    REJECTED = "REJECTED"       # 已拒绝
    AUTO_MERGED = "AUTO_MERGED" # 自动合并 (高置信度)
    AUTO_REJECTED = "AUTO_REJECTED"  # 自动拒绝 (超时)
    EXPIRED = "EXPIRED"         # 已过期


class ImpactLevel(str, Enum):
    """影响级别"""
    HIGH = "HIGH"       # 高影响 (>10 个关联对象)
    MEDIUM = "MEDIUM"   # 中影响 (5-10 个关联对象)
    LOW = "LOW"         # 低影响 (<5 个关联对象)


class MergeSuggestion(BaseModel):
    """合并建议"""
    source_party_id: str                    # 待合并的记录 (将变成别名)
    source_name: str
    source_aliases: List[str] = Field(default_factory=list)
    source_domain: Optional[str] = None

    target_party_id: str                    # 合并目标 (主记录)
    target_name: str
    target_aliases: List[str] = Field(default_factory=list)
    target_domain: Optional[str] = None


class CommonEmail(BaseModel):
    """共同出现的邮件"""
    email_id: str
    subject: Optional[str] = None
    date: Optional[datetime] = None


class MatchDetails(BaseModel):
    """匹配详情"""
    domain_match: bool = False
    name_similarity: float = Field(default=0.0, ge=0.0, le=1.0, description="Levenshtein 相似度")
    token_overlap: float = Field(default=0.0, ge=0.0, le=1.0, description="词元重叠率")
    ai_reasoning: Optional[str] = None


class MatchEvidence(BaseModel):
    """匹配证据"""
    match_type: MatchType
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    details: MatchDetails = Field(default_factory=MatchDetails)
    common_emails: List[CommonEmail] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class RiskAssessment(BaseModel):
    """风险评估"""
    impact_level: ImpactLevel = ImpactLevel.LOW
    affected_fulfillments: int = 0
    affected_shipments: int = 0
    affected_finance_docs: int = 0
    affected_compliance_docs: int = 0
    warning: Optional[str] = None

    class Config:
        use_enum_values = True

    def calculate_impact_level(self):
        """计算影响级别"""
        total = (
            self.affected_fulfillments +
            self.affected_shipments +
            self.affected_finance_docs +
            self.affected_compliance_docs
        )
        if total > 10:
            self.impact_level = ImpactLevel.HIGH
        elif total >= 5:
            self.impact_level = ImpactLevel.MEDIUM
        else:
            self.impact_level = ImpactLevel.LOW


class Review(BaseModel):
    """审核记录"""
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    decision: Optional[str] = None  # APPROVE, REJECT
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None


class AutoProcessing(BaseModel):
    """自动处理设置"""
    eligible_for_auto_merge: bool = False
    auto_merge_blocked_reason: Optional[str] = None
    scheduled_auto_reject_at: Optional[datetime] = None  # 30天未处理自动拒绝


class EntityMergeQueue(MongoModel):
    """
    实体合并队列

    设计决策：Entity Resolution 过程中，置信度不足的匹配会进入此队列，等待人工审核。
    这是解决"实体消歧"核心风险的关键机制。
    """
    # 状态
    status: MergeQueueStatus = MergeQueueStatus.PENDING

    # 合并建议
    merge_suggestion: MergeSuggestion

    # 匹配证据
    match_evidence: MatchEvidence

    # 风险评估
    risk_assessment: RiskAssessment = Field(default_factory=RiskAssessment)

    # 审核
    review: Review = Field(default_factory=Review)

    # 自动处理
    auto_processing: AutoProcessing = Field(default_factory=AutoProcessing)

    class Config:
        use_enum_values = True

    def __init__(self, **data):
        super().__init__(**data)
        # 设置默认的自动拒绝时间 (30天后)
        if not self.auto_processing.scheduled_auto_reject_at:
            self.auto_processing.scheduled_auto_reject_at = datetime.utcnow() + timedelta(days=30)
        # 评估是否可自动合并
        self._evaluate_auto_merge_eligibility()

    def _evaluate_auto_merge_eligibility(self):
        """
        评估是否满足自动合并条件

        架构师评审 2025-12-11: 采用"保守自动，激进人工"策略
        - >= 0.98 + 域名匹配/税号匹配: 自动合并
        - 0.75 - 0.98: 人工审核队列
        - < 0.75: 视为新实体
        """
        confidence = self.match_evidence.confidence

        # >= 0.98 + 强标识符匹配 → 可自动合并 (保守策略)
        if confidence >= 0.98 and self.match_evidence.details.domain_match:
            self.auto_processing.eligible_for_auto_merge = True
            return

        # 置信度低于 0.75 → 视为新实体，不应进入队列
        if confidence < 0.75:
            self.auto_processing.eligible_for_auto_merge = False
            self.auto_processing.auto_merge_blocked_reason = f"置信度 {confidence:.2f} 低于阈值 0.75，应视为新实体"
            return

        # 0.75 - 0.98 区间 → 全部进入人工审核队列
        # 架构师意见: "管理者宁愿多点几下，也不愿看到数据乱掉"
        self.auto_processing.eligible_for_auto_merge = False
        self.auto_processing.auto_merge_blocked_reason = f"置信度 {confidence:.2f} 在 0.75-0.98 区间，需人工审核"

    def approve(self, reviewer: str, notes: Optional[str] = None):
        """批准合并"""
        self.status = MergeQueueStatus.APPROVED
        self.review.reviewed_by = reviewer
        self.review.reviewed_at = datetime.utcnow()
        self.review.decision = "APPROVE"
        self.review.notes = notes
        self.updated_at = datetime.utcnow()

    def reject(self, reviewer: str, reason: str):
        """拒绝合并"""
        self.status = MergeQueueStatus.REJECTED
        self.review.reviewed_by = reviewer
        self.review.reviewed_at = datetime.utcnow()
        self.review.decision = "REJECT"
        self.review.rejection_reason = reason
        self.updated_at = datetime.utcnow()

    def auto_merge(self):
        """自动合并"""
        if not self.auto_processing.eligible_for_auto_merge:
            raise ValueError("此记录不满足自动合并条件")
        self.status = MergeQueueStatus.AUTO_MERGED
        self.review.reviewed_by = "system"
        self.review.reviewed_at = datetime.utcnow()
        self.review.decision = "APPROVE"
        self.review.notes = "系统自动合并 (高置信度)"
        self.updated_at = datetime.utcnow()

    def auto_reject_if_expired(self) -> bool:
        """如果过期则自动拒绝"""
        if self.status != MergeQueueStatus.PENDING:
            return False
        if not self.auto_processing.scheduled_auto_reject_at:
            return False
        if datetime.utcnow() < self.auto_processing.scheduled_auto_reject_at:
            return False

        self.status = MergeQueueStatus.AUTO_REJECTED
        self.review.reviewed_by = "system"
        self.review.reviewed_at = datetime.utcnow()
        self.review.decision = "REJECT"
        self.review.rejection_reason = "超过 30 天未处理，系统自动拒绝"
        self.updated_at = datetime.utcnow()
        return True

    def is_actionable(self) -> bool:
        """是否可操作"""
        return self.status == MergeQueueStatus.PENDING


# 索引定义
ENTITY_MERGE_QUEUE_INDEXES = [
    {"keys": [("status", 1), ("created_at", -1)]},
    {"keys": [("merge_suggestion.source_party_id", 1)]},
    {"keys": [("merge_suggestion.target_party_id", 1)]},
    {"keys": [("match_evidence.confidence", -1)]},
    {"keys": [("auto_processing.scheduled_auto_reject_at", 1)]},
    {"keys": [("risk_assessment.impact_level", 1)]},
]
