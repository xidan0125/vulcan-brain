"""
Email Intelligence V2.0 - Product Model
产品/SKU 模型
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field

from .base import MongoModel, Provenance


class ProductCategory(str, Enum):
    """产品类别"""
    RAW_MATERIAL = "RAW_MATERIAL"     # 原材料
    COMPONENT = "COMPONENT"           # 零部件
    ASSEMBLY = "ASSEMBLY"             # 组件
    SERVICE = "SERVICE"               # 服务


class ProductSpecs(BaseModel):
    """产品规格"""
    category: ProductCategory = ProductCategory.COMPONENT
    material: Optional[str] = None
    thickness: Optional[str] = None
    temperature_rating: Optional[str] = None
    certifications: List[str] = Field(default_factory=list)  # AS9100, NADCAP 等
    custom_fields: dict = Field(default_factory=dict)        # 灵活扩展

    class Config:
        use_enum_values = True


class SupplyChainInfo(BaseModel):
    """供应链信息"""
    primary_supplier_id: Optional[str] = None   # 主供应商 Party ID
    lead_time_days: Optional[int] = None        # 交货周期 (天)
    min_order_qty: Optional[int] = None         # 最小订购量
    unit: str = "pcs"                           # 单位: sqm, pcs, kg
    hs_code: Optional[str] = None               # 海关编码
    export_controlled: bool = False             # 是否出口管制
    itar_controlled: bool = False               # ITAR 管制


class ProductStats(BaseModel):
    """产品统计信息"""
    total_orders: int = 0
    total_quantity: float = 0
    last_ordered: Optional[datetime] = None
    avg_unit_price: Optional[float] = None
    top_customers: List[str] = Field(default_factory=list)  # Party IDs


class Product(MongoModel):
    """
    产品/SKU

    设计决策：产品是独立实体，不嵌入订单。
    理由：产品需要独立维护规格、别名，支持跨订单复用。
    """
    sku_code: str = Field(..., min_length=1, description="内部 SKU 编码")
    canonical_name: str = Field(..., min_length=1, description="标准名称")
    aliases: List[str] = Field(default_factory=list, description="各种叫法")

    # 产品规格
    specs: ProductSpecs = Field(default_factory=ProductSpecs)

    # 供应链信息
    supply_chain: SupplyChainInfo = Field(default_factory=SupplyChainInfo)

    # 统计信息
    stats: ProductStats = Field(default_factory=ProductStats)

    # 数据血缘
    provenance: Provenance = Field(default_factory=Provenance)

    def add_alias(self, alias: str) -> bool:
        """添加别名"""
        normalized = alias.strip()
        if not normalized:
            return False
        if normalized.lower() in [a.lower() for a in self.aliases]:
            return False
        self.aliases.append(normalized)
        return True

    def is_export_controlled(self) -> bool:
        """是否有出口管制"""
        return self.supply_chain.export_controlled or self.supply_chain.itar_controlled


# 索引定义
PRODUCT_INDEXES = [
    {"keys": [("sku_code", 1)], "unique": True},
    {"keys": [("canonical_name", 1)]},
    {"keys": [("aliases", 1)]},
    {"keys": [("specs.category", 1)]},
    {"keys": [("supply_chain.export_controlled", 1)]},
    {"keys": [("supply_chain.itar_controlled", 1)]},
]
