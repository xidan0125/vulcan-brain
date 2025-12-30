"""
企业人才图谱 - 算法库

使用方式:
    from enterprise_talent_graph.algorithms import AlgorithmRunner, get_registry
    
    # 运行所有算法
    runner = AlgorithmRunner()
    results = runner.run_all()
    
    # 查看可用算法
    registry = get_registry()
    print(registry.list_algorithms())
"""

from .base import BaseAlgorithm, GraphData, AlgorithmResult, MetricDefinition
from .registry import AlgorithmRegistry, get_registry
from .runner import AlgorithmRunner

__all__ = [
    "BaseAlgorithm",
    "GraphData", 
    "AlgorithmResult",
    "MetricDefinition",
    "AlgorithmRegistry",
    "get_registry",
    "AlgorithmRunner"
]
