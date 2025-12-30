"""
算法基类 - 可插拔算法框架

所有算法都继承此基类，保证统一接口和可扩展性。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetricDefinition:
    """指标定义"""
    name: str                              # 指标名称
    type: str                              # float, int, str, list
    description: str                       # 业务含义
    range: Optional[tuple] = None          # 值范围 (min, max)
    higher_is_better: Optional[bool] = None


@dataclass
class AlgorithmResult:
    """算法执行结果"""
    success: bool
    algorithm_name: str
    layer: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    node_updates: Dict[str, Dict] = field(default_factory=dict)  # email -> updates
    edge_updates: Dict[str, Dict] = field(default_factory=dict)  # edge_id -> updates
    function_updates: Dict[str, Dict] = field(default_factory=dict)  # func_id -> updates
    alerts: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    execution_time_ms: int = 0
    computed_at: datetime = field(default_factory=datetime.now)


@dataclass
class GraphData:
    """图数据容器 - 算法的输入"""
    nodes: List[Dict]                      # 节点列表 (从 MongoDB 或内存)
    edges: List[Dict]                      # 边列表
    emails: Optional[List[Dict]] = None    # 原始邮件 (某些算法需要)
    config: Dict = field(default_factory=dict)


class BaseAlgorithm(ABC):
    """
    算法基类
    
    所有算法必须继承此类并实现:
    - name: 算法名称
    - layer: 所属层级
    - run(): 执行算法
    - get_metrics(): 返回指标定义
    
    使用示例:
        class MyCentrality(BaseAlgorithm):
            name = "my_centrality"
            layer = "layer1_network"
            
            def run(self, graph_data: GraphData) -> AlgorithmResult:
                # 计算逻辑
                return AlgorithmResult(...)
    """
    
    # 子类必须定义
    name: str = "base"
    layer: str = "unknown"
    description: str = "Base algorithm"
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"algorithm.{self.name}")
    
    @abstractmethod
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        """
        执行算法
        
        Args:
            graph_data: 图数据 (节点、边、邮件)
        
        Returns:
            AlgorithmResult: 算法结果
        """
        pass
    
    @abstractmethod
    def get_metrics(self) -> List[MetricDefinition]:
        """
        返回该算法产生的指标定义
        
        Returns:
            List[MetricDefinition]: 指标定义列表
        """
        pass
    
    def validate_input(self, graph_data: GraphData) -> bool:
        """验证输入数据"""
        if not graph_data.nodes:
            self.logger.warning("No nodes in graph data")
            return False
        return True
    
    def __repr__(self):
        return f"<{self.__class__.__name__} layer={self.layer}>"
