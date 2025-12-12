"""
Email Intelligence V2.0 - Domain Models
基于 DDD (Domain-Driven Design) 的业务对象定义

集合总览:
- parties: 商业伙伴 (公司+联系人)
- products: 产品/SKU
- fulfillments: 交付任务 (核心聚合根)
- shipments: 物流运输
- finance_docs: 财务文档 (发票/付款单)
- compliance_docs: 合规文档 (W-9等)
- email_events: 邮件→业务对象映射
- action_items: AI 提取的待办事项
- entity_merge_queue: 待人工确认的实体合并建议
"""

# Base
from .base import (
    MongoModel,
    Provenance,
    ProvenanceSource,
    EntityResolution,
    ResolutionStatus,
    MatchType,
    MergeHistoryEntry,
)

# Party
from .party import (
    Party,
    PartyType,
    Relationship,
    Industry,
    Tier,
    Region,
    PaymentTerms,
    CompanyInfo,
    PersonInfo,
    PartyHealth,
    RiskFlag,
    PARTY_INDEXES,
)

# Product
from .product import (
    Product,
    ProductCategory,
    ProductSpecs,
    SupplyChainInfo,
    ProductStats,
    PRODUCT_INDEXES,
)

# Fulfillment
from .fulfillment import (
    Fulfillment,
    FulfillmentStatus,
    FulfillmentStage,
    StatusHistoryEntry,
    LineItem,
    FulfillmentRefs,
    LinkedDocs,
    FulfillmentDates,
    FulfillmentAmount,
    STATUS_TO_STAGE,
    VALID_TRANSITIONS,
    FULFILLMENT_INDEXES,
)

# Shipment
from .shipment import (
    Shipment,
    ShipmentStatus,
    Carrier,
    ServiceType,
    ExceptionType,
    ShipmentEvent,
    Location,
    Route,
    ShipmentDates,
    Cargo,
    ShipmentCosts,
    ShipmentException,
    SHIPMENT_INDEXES,
)

# Finance
from .finance import (
    FinanceDoc,
    FinanceDocType,
    PaymentStatus,
    PaymentMethod,
    FinanceDocRefs,
    FinanceLineItem,
    PaymentRecord,
    FINANCE_DOC_INDEXES,
)

# Compliance
from .compliance import (
    ComplianceDoc,
    ComplianceDocType,
    ValidityStatus,
    Validity,
    FileInfo,
    Usage,
    AlertSettings,
    COMPLIANCE_DOC_INDEXES,
)

# Email Event
from .email_event import (
    EmailEvent,
    EmailEventType,
    ActionType,
    ExtractedEntityType,
    Classification,
    AffectedChange,
    AffectedObject,
    ExtractedEntity,
    EMAIL_EVENT_INDEXES,
)

# Action Item
from .action_item import (
    ActionItem,
    ActionItemType,
    ActionItemPriority,
    ActionItemStatus,
    ActionType as SuggestedActionType,
    RelatedObject,
    Context,
    DraftEmail,
    SuggestedAction,
    Assignment,
    Resolution,
    Scoring,
    ACTION_ITEM_INDEXES,
)

# Entity Merge Queue
from .entity_merge_queue import (
    EntityMergeQueue,
    MergeQueueStatus,
    ImpactLevel,
    MergeSuggestion,
    CommonEmail,
    MatchDetails,
    MatchEvidence,
    RiskAssessment,
    Review,
    AutoProcessing,
    ENTITY_MERGE_QUEUE_INDEXES,
)

# 所有索引定义
ALL_INDEXES = {
    "parties": PARTY_INDEXES,
    "products": PRODUCT_INDEXES,
    "fulfillments": FULFILLMENT_INDEXES,
    "shipments": SHIPMENT_INDEXES,
    "finance_docs": FINANCE_DOC_INDEXES,
    "compliance_docs": COMPLIANCE_DOC_INDEXES,
    "email_events": EMAIL_EVENT_INDEXES,
    "action_items": ACTION_ITEM_INDEXES,
    "entity_merge_queue": ENTITY_MERGE_QUEUE_INDEXES,
}

__all__ = [
    # Base
    'MongoModel', 'Provenance', 'ProvenanceSource', 'EntityResolution',
    'ResolutionStatus', 'MatchType', 'MergeHistoryEntry',

    # Party
    'Party', 'PartyType', 'Relationship', 'Industry', 'Tier', 'Region',
    'PaymentTerms', 'CompanyInfo', 'PersonInfo', 'PartyHealth', 'RiskFlag',
    'PARTY_INDEXES',

    # Product
    'Product', 'ProductCategory', 'ProductSpecs', 'SupplyChainInfo',
    'ProductStats', 'PRODUCT_INDEXES',

    # Fulfillment
    'Fulfillment', 'FulfillmentStatus', 'FulfillmentStage', 'StatusHistoryEntry',
    'LineItem', 'FulfillmentRefs', 'LinkedDocs', 'FulfillmentDates',
    'FulfillmentAmount', 'STATUS_TO_STAGE', 'VALID_TRANSITIONS', 'FULFILLMENT_INDEXES',

    # Shipment
    'Shipment', 'ShipmentStatus', 'Carrier', 'ServiceType', 'ExceptionType',
    'ShipmentEvent', 'Location', 'Route', 'ShipmentDates', 'Cargo',
    'ShipmentCosts', 'ShipmentException', 'SHIPMENT_INDEXES',

    # Finance
    'FinanceDoc', 'FinanceDocType', 'PaymentStatus', 'PaymentMethod',
    'FinanceDocRefs', 'FinanceLineItem', 'PaymentRecord', 'FINANCE_DOC_INDEXES',

    # Compliance
    'ComplianceDoc', 'ComplianceDocType', 'ValidityStatus', 'Validity',
    'FileInfo', 'Usage', 'AlertSettings', 'COMPLIANCE_DOC_INDEXES',

    # Email Event
    'EmailEvent', 'EmailEventType', 'ActionType', 'ExtractedEntityType',
    'Classification', 'AffectedChange', 'AffectedObject', 'ExtractedEntity',
    'EMAIL_EVENT_INDEXES',

    # Action Item
    'ActionItem', 'ActionItemType', 'ActionItemPriority', 'ActionItemStatus',
    'SuggestedActionType', 'RelatedObject', 'Context', 'DraftEmail',
    'SuggestedAction', 'Assignment', 'Resolution', 'Scoring', 'ACTION_ITEM_INDEXES',

    # Entity Merge Queue
    'EntityMergeQueue', 'MergeQueueStatus', 'ImpactLevel', 'MergeSuggestion',
    'CommonEmail', 'MatchDetails', 'MatchEvidence', 'RiskAssessment',
    'Review', 'AutoProcessing', 'ENTITY_MERGE_QUEUE_INDEXES',

    # All indexes
    'ALL_INDEXES',
]
