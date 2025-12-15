"""
Soul Types - 核心数据结构定义

定义 Soul 模块使用的所有数据类型
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime


class Dimension(Enum):
    """六维度枚举"""
    RISK_APPETITE = "risk_appetite"
    TIME_HORIZON = "time_horizon"
    STRATEGIC_DRIVE = "strategic_drive"
    PEOPLE_PHILOSOPHY = "people_philosophy"
    CONTROL_STYLE = "control_style"
    ETHICAL_BOUNDARY = "ethical_boundary"


# 维度元数据
DIMENSION_META = {
    Dimension.RISK_APPETITE: {
        "name": "风险阈值",
        "high": "激进",
        "low": "保守",
        "high_desc": "决策风格偏激进，愿意承担高风险",
        "low_desc": "决策风格偏保守，倾向规避风险"
    },
    Dimension.TIME_HORIZON: {
        "name": "时间视界",
        "high": "长期主义",
        "low": "短期收益",
        "high_desc": "注重长期价值，愿意延迟满足",
        "low_desc": "关注短期收益，追求快速回报"
    },
    Dimension.STRATEGIC_DRIVE: {
        "name": "战略驱动",
        "high": "深度谋划",
        "low": "直觉行动",
        "high_desc": "深度谋划型，重视战略规划",
        "low_desc": "直觉行动型，快速迭代"
    },
    Dimension.PEOPLE_PHILOSOPHY: {
        "name": "人际哲学",
        "high": "协作共生",
        "low": "独狼领袖",
        "high_desc": "协作共生，重视团队协作",
        "low_desc": "独狼领袖，独立决策"
    },
    Dimension.CONTROL_STYLE: {
        "name": "控制风格",
        "high": "秩序建立",
        "low": "混沌适应",
        "high_desc": "喜欢结构化方案，偏好秩序和流程",
        "low_desc": "适应不确定性，灵活应变"
    },
    Dimension.ETHICAL_BOUNDARY: {
        "name": "伦理边界",
        "high": "原则坚守",
        "low": "灰度决策",
        "high_desc": "原则坚守，不走捷径",
        "low_desc": "灰度决策，灵活变通"
    }
}


@dataclass
class Genome:
    """
    六维度人格基因

    数值范围: 0-100, 50=中性
    """
    risk_appetite: float = 50.0
    time_horizon: float = 50.0
    strategic_drive: float = 50.0
    people_philosophy: float = 50.0
    control_style: float = 50.0
    ethical_boundary: float = 50.0

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            "risk_appetite": self.risk_appetite,
            "time_horizon": self.time_horizon,
            "strategic_drive": self.strategic_drive,
            "people_philosophy": self.people_philosophy,
            "control_style": self.control_style,
            "ethical_boundary": self.ethical_boundary
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Genome":
        """从字典创建"""
        return cls(
            risk_appetite=data.get("risk_appetite", 50.0),
            time_horizon=data.get("time_horizon", 50.0),
            strategic_drive=data.get("strategic_drive", 50.0),
            people_philosophy=data.get("people_philosophy", 50.0),
            control_style=data.get("control_style", 50.0),
            ethical_boundary=data.get("ethical_boundary", 50.0)
        )

    def get_value(self, dim: Dimension) -> float:
        """获取指定维度的值"""
        return getattr(self, dim.value)

    def set_value(self, dim: Dimension, value: float):
        """设置指定维度的值（带边界检查）"""
        setattr(self, dim.value, max(0, min(100, value)))


@dataclass
class SoulContext:
    """
    Soul 上下文 - 传递给 Interceptor
    """
    user_id: str
    genome: Genome
    task_type: str = "general"  # "chat", "code", "search", "email"
    strict_mode: bool = False   # 严格模式：阻断违规而非警告

    # 可选元数据
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AuditResult:
    """
    审计结果
    """
    passed: bool                    # 是否通过审计
    score: float = 1.0              # 对齐分数 (0-1)
    violations: List[str] = field(default_factory=list)  # 违规项
    suggestions: List[str] = field(default_factory=list) # 改进建议
    blocked: bool = False           # 是否被阻断
    original_response: Optional[str] = None  # 原始响应（如被修改）


@dataclass
class CalibrationQuestion:
    """
    校准问题
    """
    id: str
    scenario: str                   # 情境描述
    category: str                   # 分类: FUNDING/HR/STRATEGY/MARKET/CRISIS
    options: List[Dict]             # 选项列表 [{id, text, weights}]
    source: Optional[str] = None    # 来源（新闻链接等）
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CalibrationAnswer:
    """
    校准答案
    """
    question_id: str
    selected_option: str            # A/B/C
    weights: Dict[str, float]       # 选项权重
    answered_at: datetime = field(default_factory=datetime.now)
