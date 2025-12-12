"""
Email Intelligence V2.0 - Finance Document Model
财务文档模型 (发票/付款单)
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field

from .base import MongoModel, Provenance


class FinanceDocType(str, Enum):
    """财务文档类型"""
    INVOICE = "INVOICE"                 # 发票
    CREDIT_NOTE = "CREDIT_NOTE"         # 贷记单
    DEBIT_NOTE = "DEBIT_NOTE"           # 借记单
    PAYMENT_RECEIPT = "PAYMENT_RECEIPT" # 付款凭证
    QUOTE = "QUOTE"                     # 报价单
    PROFORMA = "PROFORMA"               # 形式发票


class PaymentStatus(str, Enum):
    """付款状态"""
    DRAFT = "DRAFT"             # 草稿
    SENT = "SENT"               # 已发送
    PENDING = "PENDING"         # 待付款
    PARTIAL = "PARTIAL"         # 部分付款
    PAID = "PAID"               # 已付款
    OVERDUE = "OVERDUE"         # 逾期
    CANCELLED = "CANCELLED"     # 已取消
    DISPUTED = "DISPUTED"       # 争议中


class PaymentMethod(str, Enum):
    """付款方式"""
    WIRE = "WIRE"               # 电汇
    CHECK = "CHECK"             # 支票
    CREDIT_CARD = "CREDIT_CARD" # 信用卡
    ACH = "ACH"                 # ACH
    LETTER_OF_CREDIT = "LC"     # 信用证
    OTHER = "OTHER"


class FinanceDocRefs(BaseModel):
    """关联引用"""
    party_id: Optional[str] = None          # 客户/供应商 Party ID
    party_name: Optional[str] = None        # 冗余
    fulfillment_ids: List[str] = Field(default_factory=list)  # 关联订单
    fulfillment_pos: List[str] = Field(default_factory=list)  # 冗余 PO 号


class FinanceLineItem(BaseModel):
    """发票行项目"""
    description: str
    quantity: float = 1
    unit_price: float = 0
    amount: float = 0
    product_id: Optional[str] = None
    sku_code: Optional[str] = None
    notes: Optional[str] = None


class PaymentRecord(BaseModel):
    """付款记录"""
    payment_date: datetime
    amount: float
    method: PaymentMethod = PaymentMethod.WIRE
    reference: Optional[str] = None     # 付款参考号
    notes: Optional[str] = None
    trigger_email_id: Optional[str] = None

    class Config:
        use_enum_values = True


class FinanceDoc(MongoModel):
    """
    财务文档 (发票/付款单)

    设计决策：财务文档独立于订单，因为一个订单可能有多张发票。
    """
    # 文档标识
    doc_type: FinanceDocType
    doc_number: str = Field(..., min_length=1, description="文档编号")
    external_ref: Optional[str] = None  # 外部参考号

    # 关联
    refs: FinanceDocRefs = Field(default_factory=FinanceDocRefs)

    # 金额
    currency: str = "USD"
    subtotal: float = 0
    tax: float = 0
    shipping: float = 0
    discount: float = 0
    total: float = 0

    # 行项目
    line_items: List[FinanceLineItem] = Field(default_factory=list)

    # 付款信息
    payment_status: PaymentStatus = PaymentStatus.DRAFT
    payment_terms: Optional[str] = None     # NET30, NET60 等
    due_date: Optional[datetime] = None
    paid_amount: float = 0
    outstanding: float = 0

    # 付款记录
    payments: List[PaymentRecord] = Field(default_factory=list)

    # 日期
    issue_date: Optional[datetime] = None
    sent_date: Optional[datetime] = None

    # 文件
    file_path: Optional[str] = None         # 附件路径
    file_name: Optional[str] = None

    # 数据血缘
    provenance: Provenance = Field(default_factory=Provenance)

    class Config:
        use_enum_values = True

    def record_payment(
        self,
        amount: float,
        payment_date: datetime = None,
        method: PaymentMethod = PaymentMethod.WIRE,
        reference: Optional[str] = None,
        trigger_email_id: Optional[str] = None
    ):
        """记录付款"""
        payment = PaymentRecord(
            payment_date=payment_date or datetime.utcnow(),
            amount=amount,
            method=method,
            reference=reference,
            trigger_email_id=trigger_email_id
        )
        self.payments.append(payment)
        self.paid_amount += amount
        self.outstanding = max(0, self.total - self.paid_amount)

        # 更新状态
        if self.outstanding <= 0:
            self.payment_status = PaymentStatus.PAID
        elif self.paid_amount > 0:
            self.payment_status = PaymentStatus.PARTIAL

        self.updated_at = datetime.utcnow()

    def is_overdue(self) -> bool:
        """是否逾期"""
        if not self.due_date:
            return False
        if self.payment_status == PaymentStatus.PAID:
            return False
        return datetime.utcnow() > self.due_date

    def days_overdue(self) -> int:
        """逾期天数"""
        if not self.is_overdue():
            return 0
        return (datetime.utcnow() - self.due_date).days

    def days_until_due(self) -> Optional[int]:
        """距离到期天数"""
        if not self.due_date:
            return None
        if self.payment_status == PaymentStatus.PAID:
            return None
        delta = self.due_date - datetime.utcnow()
        return delta.days


# 索引定义
FINANCE_DOC_INDEXES = [
    {"keys": [("doc_type", 1), ("doc_number", 1)], "unique": True},
    {"keys": [("refs.party_id", 1)]},
    {"keys": [("refs.fulfillment_ids", 1)]},
    {"keys": [("payment_status", 1)]},
    {"keys": [("due_date", 1)]},
    {"keys": [("issue_date", -1)]},
    {"keys": [("created_at", -1)]},
    {"keys": [("payment_status", 1), ("due_date", 1)]},  # 逾期查询
]
