"""
Email Intelligence V2.0 - Compliance Document Model
合规文档模型 (W-9, COO, 认证等)
"""
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field

from .base import MongoModel, Provenance


class ComplianceDocType(str, Enum):
    """合规文档类型"""
    W9 = "W9"                           # 美国税务表格
    W8BEN = "W8BEN"                     # 外国人税务表格
    COO = "COO"                         # 原产地证明
    COC = "COC"                         # 符合性证书
    MSDS = "MSDS"                       # 材料安全数据表
    TEST_REPORT = "TEST_REPORT"         # 测试报告
    CERTIFICATION = "CERTIFICATION"     # 认证证书 (AS9100, NADCAP等)
    LICENSE = "LICENSE"                 # 许可证
    INSURANCE = "INSURANCE"             # 保险证明
    NDA = "NDA"                         # 保密协议
    CONTRACT = "CONTRACT"               # 合同
    OTHER = "OTHER"


class ValidityStatus(str, Enum):
    """有效性状态"""
    VALID = "VALID"             # 有效
    EXPIRING_SOON = "EXPIRING_SOON"  # 即将过期 (30天内)
    EXPIRED = "EXPIRED"         # 已过期
    PENDING = "PENDING"         # 待验证
    REJECTED = "REJECTED"       # 已拒绝


class Validity(BaseModel):
    """有效性信息"""
    status: ValidityStatus = ValidityStatus.PENDING
    issue_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    days_until_expiry: Optional[int] = None  # 计算字段，定期更新
    is_perpetual: bool = False  # 是否永久有效

    class Config:
        use_enum_values = True

    def update_status(self):
        """更新状态和剩余天数"""
        if self.is_perpetual:
            self.status = ValidityStatus.VALID
            self.days_until_expiry = None
            return

        if not self.expiry_date:
            self.status = ValidityStatus.PENDING
            self.days_until_expiry = None
            return

        now = datetime.utcnow()
        delta = self.expiry_date - now
        self.days_until_expiry = delta.days

        if delta.days < 0:
            self.status = ValidityStatus.EXPIRED
        elif delta.days <= 30:
            self.status = ValidityStatus.EXPIRING_SOON
        else:
            self.status = ValidityStatus.VALID


class FileInfo(BaseModel):
    """文件信息"""
    filename: str
    storage_path: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class Usage(BaseModel):
    """使用记录"""
    fulfillment_ids: List[str] = Field(default_factory=list)
    last_used: Optional[datetime] = None
    usage_count: int = 0


class AlertSettings(BaseModel):
    """提醒设置"""
    alert_days_before: List[int] = Field(default_factory=lambda: [90, 60, 30, 7])
    alert_recipients: List[str] = Field(default_factory=list)
    last_alert_sent: Optional[datetime] = None


class ComplianceDoc(MongoModel):
    """
    合规文档 (W-9, COO 等)

    设计决策：合规文档独立存储，可关联多个订单。
    核心功能：过期提醒、自动失效、使用追踪。
    """
    # 文档信息
    doc_type: ComplianceDocType
    doc_name: str = Field(..., min_length=1, description="文档名称")
    doc_number: Optional[str] = None    # 文档编号

    # 关联方
    party_id: str = Field(..., description="关联的 Party ID")
    party_name: Optional[str] = None    # 冗余

    # 有效性
    validity: Validity = Field(default_factory=Validity)

    # 文件
    file: Optional[FileInfo] = None

    # 使用记录
    usage: Usage = Field(default_factory=Usage)

    # 提醒设置
    alerts: AlertSettings = Field(default_factory=AlertSettings)

    # 附加信息
    notes: Optional[str] = None
    issuer: Optional[str] = None        # 签发机构
    scope: Optional[str] = None         # 适用范围

    # 数据血缘
    provenance: Provenance = Field(default_factory=Provenance)

    class Config:
        use_enum_values = True

    def refresh_validity(self):
        """刷新有效性状态"""
        self.validity.update_status()
        self.updated_at = datetime.utcnow()

    def record_usage(self, fulfillment_id: str):
        """记录使用"""
        if fulfillment_id not in self.usage.fulfillment_ids:
            self.usage.fulfillment_ids.append(fulfillment_id)
        self.usage.last_used = datetime.utcnow()
        self.usage.usage_count += 1

    def is_valid(self) -> bool:
        """是否有效"""
        self.refresh_validity()
        return self.validity.status in [ValidityStatus.VALID, ValidityStatus.EXPIRING_SOON]

    def needs_renewal(self) -> bool:
        """是否需要更新"""
        self.refresh_validity()
        return self.validity.status in [ValidityStatus.EXPIRED, ValidityStatus.EXPIRING_SOON]

    def should_send_alert(self) -> bool:
        """是否应该发送提醒"""
        if not self.validity.days_until_expiry:
            return False
        if self.validity.days_until_expiry < 0:
            return False  # 已过期，不再提醒
        return self.validity.days_until_expiry in self.alerts.alert_days_before


# 索引定义
COMPLIANCE_DOC_INDEXES = [
    {"keys": [("party_id", 1), ("doc_type", 1)]},
    {"keys": [("validity.expiry_date", 1)]},
    {"keys": [("validity.status", 1)]},
    {"keys": [("validity.days_until_expiry", 1)]},
    {"keys": [("doc_type", 1)]},
    {"keys": [("created_at", -1)]},
]
