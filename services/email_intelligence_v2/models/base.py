"""
Email Intelligence V2.0 - Base Models
基础模型定义：Provenance, EntityResolution, MongoModel
"""
from datetime import datetime
from typing import Optional, List, Any
from enum import Enum
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(str):
    """MongoDB ObjectId 的 Pydantic 兼容类型"""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str):
            if ObjectId.is_valid(v):
                return v
        raise ValueError(f"Invalid ObjectId: {v}")


class ProvenanceSource(str, Enum):
    """数据来源类型"""
    LEGACY_MIGRATION = "LEGACY_MIGRATION"     # 从旧系统迁移
    EMAIL_EXTRACTION = "EMAIL_EXTRACTION"     # 从邮件 AI 提取
    MANUAL = "MANUAL"                         # 人工录入
    ERP_SYNC = "ERP_SYNC"                     # ERP 同步
    API_IMPORT = "API_IMPORT"                 # API 导入


class Provenance(BaseModel):
    """数据血缘 - 记录数据来源和可信度"""
    source: ProvenanceSource = ProvenanceSource.EMAIL_EXTRACTION
    source_email_ids: List[str] = Field(default_factory=list, description="数据来源邮件 ID 列表")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="AI 置信度")
    last_verified: Optional[datetime] = None
    verified_by: Optional[str] = None  # "system" | "human" | user_email

    class Config:
        use_enum_values = True


class ResolutionStatus(str, Enum):
    """实体消歧状态"""
    CANONICAL = "CANONICAL"           # 主记录
    ALIAS = "ALIAS"                   # 别名记录 (指向主记录)
    PENDING_REVIEW = "PENDING_REVIEW" # 待人工审核


class MatchType(str, Enum):
    """匹配类型"""
    DOMAIN_EXACT = "DOMAIN_EXACT"     # 域名精确匹配
    ALIAS_EXACT = "ALIAS_EXACT"       # 别名精确匹配
    NAME_FUZZY = "NAME_FUZZY"         # 名称模糊匹配
    TOKEN_OVERLAP = "TOKEN_OVERLAP"   # 词元重叠匹配
    AI_SUGGEST = "AI_SUGGEST"         # AI 建议匹配


class MergeHistoryEntry(BaseModel):
    """合并历史记录"""
    merged_from_id: str = Field(..., description="被合并记录的 ID")
    merged_at: datetime = Field(default_factory=datetime.utcnow)
    merged_by: str = Field(default="auto", description="auto | manual")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    match_type: MatchType
    evidence: str = Field(default="", description="匹配证据说明")

    class Config:
        use_enum_values = True


class EntityResolution(BaseModel):
    """实体消歧信息"""
    canonical_id: Optional[str] = Field(None, description="如果是别名记录，指向主记录")
    is_canonical: bool = Field(default=True, description="是否为主记录")
    merge_history: List[MergeHistoryEntry] = Field(default_factory=list)
    resolution_status: ResolutionStatus = ResolutionStatus.CANONICAL

    class Config:
        use_enum_values = True


class MongoModel(BaseModel):
    """MongoDB 文档基类"""
    id: Optional[str] = Field(None, alias="_id", description="MongoDB ObjectId")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ObjectId: lambda v: str(v)
        }

    def to_mongo(self) -> dict:
        """转换为 MongoDB 文档格式"""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if data.get("_id"):
            data["_id"] = ObjectId(data["_id"])
        return data

    @classmethod
    def from_mongo(cls, data: dict) -> "MongoModel":
        """从 MongoDB 文档创建实例"""
        if data.get("_id"):
            data["_id"] = str(data["_id"])
        return cls(**data)
