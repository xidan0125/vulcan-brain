"""
Email Intelligence V2.0 - Fulfillment Model
交付任务模型 (核心聚合根)
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field

from .base import MongoModel, Provenance


class FulfillmentStatus(str, Enum):
    """
    履约状态 (状态机)

    架构师评审 2025-12-11: 增加异常分支状态
    - BLOCKED: 阻塞状态 (W-9过期/信用额度超标/海关查验等)
    - PARTIAL_SHIPPED: 部分发货 (B2B大单分批发货)
    - PARTIAL_PAID: 部分付款 (30%定金等)
    """
    NEW = "NEW"                     # 新建 (收到询价)
    QUOTED = "QUOTED"               # 已报价
    CONFIRMED = "CONFIRMED"         # 已确认 (收到 PO)
    BLOCKED = "BLOCKED"             # 阻塞 (合规/信用/海关等问题) ⚠️
    PRODUCING = "PRODUCING"         # 生产中
    QC_PENDING = "QC_PENDING"       # 待质检
    READY_TO_SHIP = "READY_TO_SHIP" # 待发货
    PARTIAL_SHIPPED = "PARTIAL_SHIPPED"  # 部分发货 ⚠️
    SHIPPING = "SHIPPING"           # 运输中 (全部发货)
    DELIVERED = "DELIVERED"         # 已送达
    INVOICED = "INVOICED"           # 已开票
    PARTIAL_PAID = "PARTIAL_PAID"   # 部分付款 (定金/分期) ⚠️
    PAID = "PAID"                   # 已付款
    CLOSED = "CLOSED"               # 已关闭
    CANCELLED = "CANCELLED"         # 已取消
    ON_HOLD = "ON_HOLD"             # 暂停 (客户要求)


class FulfillmentStage(str, Enum):
    """大阶段"""
    SALES = "SALES"                 # 销售阶段
    ENGINEERING = "ENGINEERING"     # 工程阶段
    PRODUCTION = "PRODUCTION"       # 生产阶段
    LOGISTICS = "LOGISTICS"         # 物流阶段
    FINANCE = "FINANCE"             # 财务阶段
    COMPLETED = "COMPLETED"         # 已完成


# 状态到阶段的映射
STATUS_TO_STAGE = {
    FulfillmentStatus.NEW: FulfillmentStage.SALES,
    FulfillmentStatus.QUOTED: FulfillmentStage.SALES,
    FulfillmentStatus.CONFIRMED: FulfillmentStage.SALES,
    FulfillmentStatus.BLOCKED: FulfillmentStage.SALES,        # BLOCKED 可能发生在任何阶段，默认归 SALES
    FulfillmentStatus.PRODUCING: FulfillmentStage.PRODUCTION,
    FulfillmentStatus.QC_PENDING: FulfillmentStage.PRODUCTION,
    FulfillmentStatus.READY_TO_SHIP: FulfillmentStage.LOGISTICS,
    FulfillmentStatus.PARTIAL_SHIPPED: FulfillmentStage.LOGISTICS,  # 部分发货
    FulfillmentStatus.SHIPPING: FulfillmentStage.LOGISTICS,
    FulfillmentStatus.DELIVERED: FulfillmentStage.LOGISTICS,
    FulfillmentStatus.INVOICED: FulfillmentStage.FINANCE,
    FulfillmentStatus.PARTIAL_PAID: FulfillmentStage.FINANCE,       # 部分付款
    FulfillmentStatus.PAID: FulfillmentStage.FINANCE,
    FulfillmentStatus.CLOSED: FulfillmentStage.COMPLETED,
    FulfillmentStatus.CANCELLED: FulfillmentStage.COMPLETED,
    FulfillmentStatus.ON_HOLD: FulfillmentStage.SALES,
}

# 合法的状态转换 (架构师评审 2025-12-11 更新)
# BLOCKED 可以从任何非终态状态进入，也可以恢复到原状态
VALID_TRANSITIONS = {
    FulfillmentStatus.NEW: [
        FulfillmentStatus.QUOTED,
        FulfillmentStatus.CONFIRMED,
        FulfillmentStatus.BLOCKED,      # 可能因信用问题直接阻塞
        FulfillmentStatus.CANCELLED
    ],
    FulfillmentStatus.QUOTED: [
        FulfillmentStatus.CONFIRMED,
        FulfillmentStatus.NEW,
        FulfillmentStatus.BLOCKED,
        FulfillmentStatus.CANCELLED
    ],
    FulfillmentStatus.CONFIRMED: [
        FulfillmentStatus.PRODUCING,
        FulfillmentStatus.BLOCKED,      # W-9过期/信用额度等
        FulfillmentStatus.ON_HOLD,
        FulfillmentStatus.CANCELLED
    ],
    FulfillmentStatus.BLOCKED: [        # 阻塞解除后可恢复到多个状态
        FulfillmentStatus.CONFIRMED,
        FulfillmentStatus.PRODUCING,
        FulfillmentStatus.READY_TO_SHIP,
        FulfillmentStatus.CANCELLED
    ],
    FulfillmentStatus.PRODUCING: [
        FulfillmentStatus.QC_PENDING,
        FulfillmentStatus.BLOCKED,
        FulfillmentStatus.ON_HOLD
    ],
    FulfillmentStatus.QC_PENDING: [
        FulfillmentStatus.READY_TO_SHIP,
        FulfillmentStatus.PRODUCING,    # QC失败返工
        FulfillmentStatus.BLOCKED
    ],
    FulfillmentStatus.READY_TO_SHIP: [
        FulfillmentStatus.PARTIAL_SHIPPED,  # 分批发货
        FulfillmentStatus.SHIPPING,         # 全部发货
        FulfillmentStatus.BLOCKED,          # 海关问题
        FulfillmentStatus.ON_HOLD
    ],
    FulfillmentStatus.PARTIAL_SHIPPED: [    # 部分发货状态
        FulfillmentStatus.PARTIAL_SHIPPED,  # 继续分批
        FulfillmentStatus.SHIPPING,         # 最后一批发出
        FulfillmentStatus.BLOCKED
    ],
    FulfillmentStatus.SHIPPING: [
        FulfillmentStatus.DELIVERED,
        FulfillmentStatus.BLOCKED,          # 海关扣留
        FulfillmentStatus.ON_HOLD
    ],
    FulfillmentStatus.DELIVERED: [
        FulfillmentStatus.INVOICED,
        FulfillmentStatus.CLOSED            # 无需开票的情况
    ],
    FulfillmentStatus.INVOICED: [
        FulfillmentStatus.PARTIAL_PAID,     # 收到定金/部分付款
        FulfillmentStatus.PAID              # 全额付款
    ],
    FulfillmentStatus.PARTIAL_PAID: [       # 部分付款状态
        FulfillmentStatus.PARTIAL_PAID,     # 继续收款
        FulfillmentStatus.PAID              # 付清
    ],
    FulfillmentStatus.PAID: [
        FulfillmentStatus.CLOSED
    ],
    FulfillmentStatus.CLOSED: [],           # 终态
    FulfillmentStatus.CANCELLED: [],        # 终态
    FulfillmentStatus.ON_HOLD: [            # 暂停可恢复到多个状态
        FulfillmentStatus.CONFIRMED,
        FulfillmentStatus.PRODUCING,
        FulfillmentStatus.READY_TO_SHIP,
        FulfillmentStatus.SHIPPING,
        FulfillmentStatus.BLOCKED,
        FulfillmentStatus.CANCELLED
    ],
}


class StatusHistoryEntry(BaseModel):
    """状态历史记录 (简化版 Event Sourcing)"""
    status: FulfillmentStatus
    stage: FulfillmentStage
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    changed_by: str = "system"              # system | user_email
    trigger_email_id: Optional[str] = None  # 触发此变更的邮件
    reason: str = ""                        # 变更原因
    evidence_snippet: Optional[str] = None  # 邮件中的证据片段

    class Config:
        use_enum_values = True


class LineItem(BaseModel):
    """订单行项目"""
    product_id: Optional[str] = None    # Product ID
    product_name: str                   # 产品名称 (冗余，方便显示)
    sku_code: Optional[str] = None
    quantity: float
    unit: str = "pcs"
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    notes: Optional[str] = None


class FulfillmentRefs(BaseModel):
    """关联引用"""
    customer_id: Optional[str] = None           # Party ID (客户公司)
    customer_name: Optional[str] = None         # 冗余
    customer_contact_id: Optional[str] = None   # Party ID (客户联系人)
    supplier_ids: List[str] = Field(default_factory=list)  # 供应商 Party IDs


class LinkedDocs(BaseModel):
    """关联文档"""
    shipment_ids: List[str] = Field(default_factory=list)
    invoice_ids: List[str] = Field(default_factory=list)
    compliance_doc_ids: List[str] = Field(default_factory=list)
    quote_ids: List[str] = Field(default_factory=list)


class FulfillmentDates(BaseModel):
    """关键日期"""
    po_date: Optional[datetime] = None          # PO 日期
    target_delivery: Optional[datetime] = None  # 目标交付日期
    actual_delivery: Optional[datetime] = None  # 实际交付日期
    invoice_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None


class FulfillmentAmount(BaseModel):
    """金额信息"""
    subtotal: float = 0
    shipping: float = 0
    tax: float = 0
    total: float = 0
    currency: str = "USD"
    paid_amount: float = 0
    outstanding: float = 0


class Fulfillment(MongoModel):
    """
    交付任务 (核心聚合根)

    设计决策：这是系统的"脊梁"，串联订单、物流、财务。
    状态机：NEW → CONFIRMED → PRODUCING → SHIPPING → DELIVERED → INVOICED → PAID → CLOSED
    """
    # 订单标识
    client_po: str = Field(..., min_length=1, description="客户 PO 号")
    internal_so: Optional[str] = None   # 内部 SO 号
    quote_ref: Optional[str] = None     # 关联报价单

    # 状态机
    current_status: FulfillmentStatus = FulfillmentStatus.NEW
    current_stage: FulfillmentStage = FulfillmentStage.SALES
    is_blocked: bool = False
    block_reason: Optional[str] = None

    # 状态历史 (简化版 Event Sourcing)
    status_history: List[StatusHistoryEntry] = Field(default_factory=list)

    # 关联引用
    refs: FulfillmentRefs = Field(default_factory=FulfillmentRefs)

    # 行项目
    line_items: List[LineItem] = Field(default_factory=list)

    # 关联文档
    linked_docs: LinkedDocs = Field(default_factory=LinkedDocs)

    # 日期
    dates: FulfillmentDates = Field(default_factory=FulfillmentDates)

    # 金额
    amount: FulfillmentAmount = Field(default_factory=FulfillmentAmount)

    # 数据血缘
    provenance: Provenance = Field(default_factory=Provenance)

    class Config:
        use_enum_values = True

    def can_transition_to(self, new_status: FulfillmentStatus) -> bool:
        """检查是否可以转换到新状态"""
        valid_next = VALID_TRANSITIONS.get(self.current_status, [])
        return new_status in valid_next

    def transition_to(
        self,
        new_status: FulfillmentStatus,
        trigger_email_id: Optional[str] = None,
        reason: str = "",
        evidence_snippet: Optional[str] = None,
        changed_by: str = "system"
    ) -> bool:
        """
        状态转换

        Returns:
            bool: 是否转换成功
        """
        if not self.can_transition_to(new_status):
            return False

        new_stage = STATUS_TO_STAGE.get(new_status, self.current_stage)

        # 记录历史
        entry = StatusHistoryEntry(
            status=new_status,
            stage=new_stage,
            changed_by=changed_by,
            trigger_email_id=trigger_email_id,
            reason=reason,
            evidence_snippet=evidence_snippet
        )
        self.status_history.append(entry)

        # 更新当前状态
        self.current_status = new_status
        self.current_stage = new_stage
        self.updated_at = datetime.utcnow()

        return True

    def get_days_in_status(self) -> int:
        """获取在当前状态的天数"""
        if not self.status_history:
            return 0
        last_change = self.status_history[-1].timestamp
        return (datetime.utcnow() - last_change).days

    def is_overdue(self) -> bool:
        """是否逾期"""
        if not self.dates.target_delivery:
            return False
        if self.current_status in [FulfillmentStatus.CLOSED, FulfillmentStatus.CANCELLED]:
            return False
        return datetime.utcnow() > self.dates.target_delivery


# 索引定义
FULFILLMENT_INDEXES = [
    {"keys": [("client_po", 1)], "unique": True},
    {"keys": [("internal_so", 1)]},
    {"keys": [("current_status", 1)]},
    {"keys": [("current_stage", 1)]},
    {"keys": [("refs.customer_id", 1)]},
    {"keys": [("refs.customer_name", 1)]},
    {"keys": [("dates.target_delivery", 1)]},
    {"keys": [("dates.po_date", -1)]},
    {"keys": [("created_at", -1)]},
    {"keys": [("is_blocked", 1), ("current_status", 1)]},
]
