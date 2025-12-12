"""
Email Intelligence V2.0 - Party Model
商业伙伴模型：公司 + 联系人
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator

from .base import MongoModel, Provenance, EntityResolution


class PartyType(str, Enum):
    """伙伴类型"""
    COMPANY = "COMPANY"
    PERSON = "PERSON"


class Relationship(str, Enum):
    """商业关系"""
    CUSTOMER = "CUSTOMER"       # 客户
    SUPPLIER = "SUPPLIER"       # 供应商
    LOGISTICS = "LOGISTICS"     # 物流商
    PARTNER = "PARTNER"         # 合作伙伴
    INTERNAL = "INTERNAL"       # 内部
    UNKNOWN = "UNKNOWN"         # 未知


class Industry(str, Enum):
    """行业"""
    AEROSPACE = "aerospace"
    AUTOMOTIVE = "automotive"
    ELECTRONICS = "electronics"
    MANUFACTURING = "manufacturing"
    LOGISTICS = "logistics"
    OTHER = "other"


class Tier(str, Enum):
    """客户分级"""
    STRATEGIC = "STRATEGIC"     # 战略客户 (SpaceX 级别)
    KEY = "KEY"                 # 重要客户
    NORMAL = "NORMAL"           # 普通客户
    INACTIVE = "INACTIVE"       # 不活跃


class Region(str, Enum):
    """地区"""
    US = "US"
    JP = "JP"
    CN = "CN"
    EU = "EU"
    OTHER = "OTHER"


class PaymentTerms(str, Enum):
    """付款条款"""
    NET30 = "NET30"
    NET60 = "NET60"
    NET90 = "NET90"
    PREPAID = "PREPAID"
    COD = "COD"
    OTHER = "OTHER"


class CompanyInfo(BaseModel):
    """公司特有信息"""
    relationship: Relationship = Relationship.UNKNOWN
    industry: Industry = Industry.OTHER
    tier: Tier = Tier.NORMAL
    region: Region = Region.OTHER
    tax_id: Optional[str] = None            # 税号 (敏感信息)
    payment_terms: Optional[PaymentTerms] = None
    credit_limit: Optional[float] = None
    currency: str = "USD"

    class Config:
        use_enum_values = True


class PersonInfo(BaseModel):
    """联系人特有信息"""
    email: str
    title: Optional[str] = None             # 职位
    department: Optional[str] = None        # 部门
    phone: Optional[str] = None
    belongs_to_company: Optional[str] = None  # 关联公司 ID
    is_primary_contact: bool = False        # 是否主要联系人

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v and "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower() if v else v


class RiskFlag(str, Enum):
    """风险标记"""
    PAYMENT_DELAY = "PAYMENT_DELAY"               # 付款延迟
    COMPLIANCE_EXPIRING = "COMPLIANCE_EXPIRING"   # 合规文档即将过期
    QUALITY_ISSUE = "QUALITY_ISSUE"               # 质量问题
    COMMUNICATION_GAP = "COMMUNICATION_GAP"       # 沟通断档
    ORDER_DISPUTE = "ORDER_DISPUTE"               # 订单争议


class PartyHealth(BaseModel):
    """健康度指标"""
    score: int = Field(default=50, ge=0, le=100, description="综合健康度 0-100")
    last_interaction: Optional[datetime] = None
    interaction_count_30d: int = 0
    open_issues_count: int = 0
    risk_flags: List[RiskFlag] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class Party(MongoModel):
    """
    商业伙伴 (公司 + 联系人)

    设计决策：公司和联系人放在同一集合，用 party_type 区分。
    理由：避免跨表 JOIN，联系人天然属于公司。
    """
    party_type: PartyType

    # 基础信息
    canonical_name: str = Field(..., min_length=1, description="标准名称")
    aliases: List[str] = Field(default_factory=list, description="别名列表 (用于匹配)")
    domain: Optional[str] = None  # 邮箱域名

    # 类型特定信息
    company_info: Optional[CompanyInfo] = None
    person_info: Optional[PersonInfo] = None

    # 健康度
    health: PartyHealth = Field(default_factory=PartyHealth)

    # Entity Resolution
    entity_resolution: EntityResolution = Field(default_factory=EntityResolution)

    # 数据血缘
    provenance: Provenance = Field(default_factory=Provenance)

    class Config:
        use_enum_values = True

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, v):
        """别名去重和标准化"""
        if not v:
            return []
        # 去重，保持原始顺序
        seen = set()
        result = []
        for alias in v:
            normalized = alias.strip()
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                result.append(normalized)
        return result

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, v):
        """域名标准化"""
        if v:
            return v.lower().strip()
        return v

    def add_alias(self, alias: str) -> bool:
        """添加别名，返回是否添加成功"""
        normalized = alias.strip()
        if not normalized:
            return False
        if normalized.lower() in [a.lower() for a in self.aliases]:
            return False
        self.aliases.append(normalized)
        return True

    def is_alias_of(self, other_party_id: str) -> bool:
        """检查是否为另一个 party 的别名"""
        return (
            not self.entity_resolution.is_canonical and
            self.entity_resolution.canonical_id == other_party_id
        )

    def get_all_related_ids(self) -> List[str]:
        """获取所有相关 ID (包括自己和通过 merge_history 合并的)"""
        ids = [self.id] if self.id else []
        for entry in self.entity_resolution.merge_history:
            if entry.merged_from_id not in ids:
                ids.append(entry.merged_from_id)
        return ids


# 索引定义 (用于 Schema 初始化脚本)
PARTY_INDEXES = [
    {"keys": [("party_type", 1), ("canonical_name", 1)], "unique": True},
    {"keys": [("aliases", 1)]},
    {"keys": [("domain", 1)]},
    {"keys": [("company_info.relationship", 1)]},
    {"keys": [("company_info.tier", 1)]},
    {"keys": [("person_info.email", 1)]},
    {"keys": [("person_info.belongs_to_company", 1)]},
    {"keys": [("health.score", -1)]},
    {"keys": [("entity_resolution.canonical_id", 1)]},
    {"keys": [("entity_resolution.is_canonical", 1)]},
    {"keys": [("entity_resolution.resolution_status", 1)]},
]
