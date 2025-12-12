"""
Email Intelligence V2.0 - Email Event Model
邮件事件模型 (邮件→业务对象映射)
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field

from .base import MongoModel


class EmailEventType(str, Enum):
    """邮件意图类型"""
    ORDER_CONFIRM = "ORDER_CONFIRM"         # 订单确认
    QUOTE_REQUEST = "QUOTE_REQUEST"         # 询价
    QUOTE_RESPONSE = "QUOTE_RESPONSE"       # 报价
    SHIPPING_UPDATE = "SHIPPING_UPDATE"     # 物流更新
    INVOICE = "INVOICE"                     # 发票
    PAYMENT = "PAYMENT"                     # 付款
    COMPLIANCE = "COMPLIANCE"               # 合规
    QUALITY = "QUALITY"                     # 质量
    MEETING = "MEETING"             # 业务会议
    CONTRACT = "CONTRACT"           # 合同协商
    OTHER_BUSINESS = "OTHER_BUSINESS" # 其他业务
    OTHER = "OTHER"


class ActionType(str, Enum):
    """操作类型"""
    CREATE = "CREATE"               # 创建对象
    STATUS_UPDATE = "STATUS_UPDATE" # 状态更新
    UPDATE_FIELD = "UPDATE_FIELD"   # 字段更新
    LINK = "LINK"                   # 建立关联
    NO_ACTION = "NO_ACTION"         # 无操作


class ExtractedEntityType(str, Enum):
    """提取的实体类型"""
    PO_NUMBER = "PO_NUMBER"
    SO_NUMBER = "SO_NUMBER"
    TRACKING_NUMBER = "TRACKING_NUMBER"
    INVOICE_NUMBER = "INVOICE_NUMBER"
    COMPANY = "COMPANY"
    PERSON = "PERSON"
    PRODUCT = "PRODUCT"
    DATE = "DATE"
    AMOUNT = "AMOUNT"
    QUANTITY = "QUANTITY"
    OTHER = "OTHER"


class Classification(BaseModel):
    """AI 分类结果"""
    intent: EmailEventType = EmailEventType.OTHER
    sub_intent: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    model: str = "qwen3:30b-a3b"

    class Config:
        use_enum_values = True


class AffectedChange(BaseModel):
    """变更详情"""
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None


class AffectedObject(BaseModel):
    """受影响的业务对象"""
    collection: str                     # parties, fulfillments, shipments 等
    object_id: Optional[str] = None     # 对象 ID
    object_ref: Optional[str] = None    # 可读引用 (PO号, 追踪号等)
    action: ActionType = ActionType.NO_ACTION
    changes: Optional[AffectedChange] = None

    class Config:
        use_enum_values = True


class ExtractedEntity(BaseModel):
    """提取的实体"""
    entity_type: ExtractedEntityType
    value: str
    normalized_value: Optional[str] = None  # 标准化后的值
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_party_id: Optional[str] = None  # 匹配到的 Party ID
    context: Optional[str] = None           # 上下文 (如 "ETA", "发货日期")

    class Config:
        use_enum_values = True


class EmailEvent(MongoModel):
    """
    邮件事件 (邮件→业务对象映射)

    设计决策：轻量级中间表，解耦邮件和业务对象。
    作用：一封邮件可能同时更新多个业务对象，此表记录映射关系。
    """
    # 来源邮件
    email_id: str = Field(..., description="邮件 ID (emails 集合)")
    email_subject: Optional[str] = None
    email_date: Optional[datetime] = None
    email_from: Optional[str] = None

    # AI 分类结果
    classification: Classification = Field(default_factory=Classification)

    # 影响的业务对象
    affects: List[AffectedObject] = Field(default_factory=list)

    # 提取的实体 (快照)
    extracted_entities: List[ExtractedEntity] = Field(default_factory=list)

    # 处理状态
    processed: bool = False
    process_error: Optional[str] = None
    process_attempts: int = 0

    class Config:
        use_enum_values = True

    def add_affected_object(
        self,
        collection: str,
        object_id: Optional[str] = None,
        object_ref: Optional[str] = None,
        action: ActionType = ActionType.NO_ACTION,
        changes: Optional[AffectedChange] = None
    ):
        """添加受影响的对象"""
        affected = AffectedObject(
            collection=collection,
            object_id=object_id,
            object_ref=object_ref,
            action=action,
            changes=changes
        )
        self.affects.append(affected)

    def add_extracted_entity(
        self,
        entity_type: ExtractedEntityType,
        value: str,
        confidence: float = 0.0,
        matched_party_id: Optional[str] = None,
        context: Optional[str] = None
    ):
        """添加提取的实体"""
        entity = ExtractedEntity(
            entity_type=entity_type,
            value=value,
            confidence=confidence,
            matched_party_id=matched_party_id,
            context=context
        )
        self.extracted_entities.append(entity)

    def get_affected_by_collection(self, collection: str) -> List[AffectedObject]:
        """获取指定集合的受影响对象"""
        return [a for a in self.affects if a.collection == collection]

    def get_entities_by_type(self, entity_type: ExtractedEntityType) -> List[ExtractedEntity]:
        """获取指定类型的实体"""
        return [e for e in self.extracted_entities if e.entity_type == entity_type]


# 索引定义
EMAIL_EVENT_INDEXES = [
    {"keys": [("email_id", 1)], "unique": True},
    {"keys": [("classification.intent", 1)]},
    {"keys": [("email_date", -1)]},
    {"keys": [("affects.collection", 1), ("affects.object_id", 1)]},
    {"keys": [("processed", 1)]},
    {"keys": [("created_at", -1)]},
]
