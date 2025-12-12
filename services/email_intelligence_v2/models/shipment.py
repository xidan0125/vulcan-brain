"""
Email Intelligence V2.0 - Shipment Model
物流运输模型
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field

from .base import MongoModel, Provenance


class ShipmentStatus(str, Enum):
    """物流状态"""
    BOOKED = "BOOKED"                   # 已预订
    PICKED_UP = "PICKED_UP"             # 已取件
    IN_TRANSIT = "IN_TRANSIT"           # 运输中
    CUSTOMS_HOLD = "CUSTOMS_HOLD"       # 海关扣留
    CUSTOMS_CLEARED = "CUSTOMS_CLEARED" # 已清关
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"  # 派送中
    DELIVERED = "DELIVERED"             # 已送达
    EXCEPTION = "EXCEPTION"             # 异常
    RETURNED = "RETURNED"               # 已退回


class Carrier(str, Enum):
    """承运商"""
    UPS = "UPS"
    FEDEX = "FEDEX"
    DHL = "DHL"
    EXPEDITORS = "EXPEDITORS"
    SF = "SF"               # 顺丰
    TNT = "TNT"
    USPS = "USPS"
    OTHER = "OTHER"


class ServiceType(str, Enum):
    """服务类型"""
    EXPRESS = "EXPRESS"     # 快递
    STANDARD = "STANDARD"   # 标准
    FREIGHT = "FREIGHT"     # 货运
    AIR = "AIR"             # 空运
    SEA = "SEA"             # 海运
    GROUND = "GROUND"       # 陆运


class ExceptionType(str, Enum):
    """异常类型"""
    CUSTOMS_HOLD = "CUSTOMS_HOLD"       # 海关扣留
    DELAY = "DELAY"                     # 延误
    DAMAGE = "DAMAGE"                   # 货损
    LOST = "LOST"                       # 丢失
    ADDRESS_ISSUE = "ADDRESS_ISSUE"     # 地址问题
    WEATHER = "WEATHER"                 # 天气原因
    OTHER = "OTHER"


class ShipmentEvent(BaseModel):
    """物流事件 (状态追踪)"""
    status: ShipmentStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    location: Optional[str] = None
    trigger_email_id: Optional[str] = None
    notes: Optional[str] = None
    is_exception: bool = False

    class Config:
        use_enum_values = True


class Location(BaseModel):
    """地点"""
    city: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None


class Route(BaseModel):
    """路线信息"""
    origin: Location = Field(default_factory=Location)
    destination: Location = Field(default_factory=Location)
    via: List[str] = Field(default_factory=list)  # 中转站


class ShipmentDates(BaseModel):
    """日期信息"""
    booked_date: Optional[datetime] = None
    pickup_date: Optional[datetime] = None
    etd: Optional[datetime] = None              # 预计离港
    eta: Optional[datetime] = None              # 预计到达
    actual_departure: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None


class Cargo(BaseModel):
    """货物信息"""
    packages: int = 1
    gross_weight_kg: Optional[float] = None
    volume_cbm: Optional[float] = None
    declared_value: Optional[float] = None
    currency: str = "USD"
    hs_codes: List[str] = Field(default_factory=list)
    dangerous_goods: bool = False
    description: Optional[str] = None


class ShipmentCosts(BaseModel):
    """运费"""
    freight: float = 0
    insurance: float = 0
    customs_duty: float = 0
    other: float = 0
    total: float = 0
    currency: str = "USD"
    paid_by: str = "SHIPPER"  # SHIPPER | CONSIGNEE


class ShipmentException(BaseModel):
    """异常记录"""
    exception_type: ExceptionType
    reported_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    description: str = ""
    resolution: Optional[str] = None
    trigger_email_id: Optional[str] = None

    class Config:
        use_enum_values = True


class Shipment(MongoModel):
    """
    物流运输

    设计决策：独立于 fulfillments，因为一个订单可能多次发货。
    """
    # 物流标识
    tracking_number: str = Field(..., min_length=1, description="追踪号")
    carrier: Carrier = Carrier.OTHER
    carrier_ref: Optional[str] = None       # 承运商内部编号
    service_type: ServiceType = ServiceType.STANDARD

    # 关联订单
    fulfillment_id: Optional[str] = None    # Fulfillment ID
    fulfillment_po: Optional[str] = None    # 冗余，方便查询

    # 状态
    current_status: ShipmentStatus = ShipmentStatus.BOOKED
    status_history: List[ShipmentEvent] = Field(default_factory=list)

    # 路线
    route: Route = Field(default_factory=Route)

    # 日期
    dates: ShipmentDates = Field(default_factory=ShipmentDates)

    # 货物
    cargo: Cargo = Field(default_factory=Cargo)

    # 费用
    costs: ShipmentCosts = Field(default_factory=ShipmentCosts)

    # 异常
    exceptions: List[ShipmentException] = Field(default_factory=list)

    # 数据血缘
    provenance: Provenance = Field(default_factory=Provenance)

    class Config:
        use_enum_values = True

    def add_event(
        self,
        status: ShipmentStatus,
        location: Optional[str] = None,
        trigger_email_id: Optional[str] = None,
        notes: Optional[str] = None,
        is_exception: bool = False
    ):
        """添加物流事件"""
        event = ShipmentEvent(
            status=status,
            location=location,
            trigger_email_id=trigger_email_id,
            notes=notes,
            is_exception=is_exception
        )
        self.status_history.append(event)
        self.current_status = status
        self.updated_at = datetime.utcnow()

    def add_exception(
        self,
        exception_type: ExceptionType,
        description: str,
        trigger_email_id: Optional[str] = None
    ):
        """添加异常记录"""
        exception = ShipmentException(
            exception_type=exception_type,
            description=description,
            trigger_email_id=trigger_email_id
        )
        self.exceptions.append(exception)

    def has_unresolved_exceptions(self) -> bool:
        """是否有未解决的异常"""
        return any(e.resolved_at is None for e in self.exceptions)

    def is_delayed(self) -> bool:
        """是否延误"""
        if not self.dates.eta:
            return False
        if self.current_status == ShipmentStatus.DELIVERED:
            return False
        return datetime.utcnow() > self.dates.eta


# 索引定义
SHIPMENT_INDEXES = [
    {"keys": [("tracking_number", 1)], "unique": True},
    {"keys": [("carrier", 1)]},
    {"keys": [("current_status", 1)]},
    {"keys": [("fulfillment_id", 1)]},
    {"keys": [("fulfillment_po", 1)]},
    {"keys": [("dates.eta", 1)]},
    {"keys": [("dates.booked_date", -1)]},
    {"keys": [("created_at", -1)]},
]
