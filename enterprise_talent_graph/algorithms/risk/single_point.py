"""
单点故障分析 - Risk Layer

识别组织中的关键依赖点：
- 某人离开后会导致业务断裂
- 某人是唯一的外部关系维护者
- 网络鲁棒性测试（渗透分析）
"""

import networkx as nx
from typing import List, Dict, Set
from collections import defaultdict
import logging

import sys
sys.path.append("/home/xinyue/vulcan-brain")

from enterprise_talent_graph.algorithms.base import (
    BaseAlgorithm, GraphData, AlgorithmResult, MetricDefinition
)

logger = logging.getLogger(__name__)


class SinglePointFailure(BaseAlgorithm):
    """
    单点故障检测算法
    
    识别移除后会导致网络碎片化的关键节点
    
    业务含义：
    - 高单点风险者离职会导致业务断层
    - 需要安排备份人员分担关键关系
    """
    
    name = "single_point_failure"
    layer = "risk"
    description = "识别单点故障风险，评估关键依赖"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 只分析内部员工
        internal_nodes = set()
        G = nx.Graph()
        
        for node in graph_data.nodes:
            email = node.get("email") or node.get("_id")
            if email:
                G.add_node(email, **node)
                if "vulcanshield" in email.lower():
                    internal_nodes.add(email)
        
        for edge in graph_data.edges:
            source = edge.get("source")
            target = edge.get("target")
            weight = edge.get("weight", edge.get("count", 1))
            if source and target and source in G.nodes and target in G.nodes:
                G.add_edge(source, target, weight=weight)
        
        if len(internal_nodes) == 0:
            return AlgorithmResult(
                success=False,
                algorithm_name=self.name,
                layer=self.layer,
                errors=["No internal nodes found"]
            )
        
        # 计算原始网络的最大连通分量
        original_components = list(nx.connected_components(G))
        original_largest = max(len(c) for c in original_components) if original_components else 0
        
        # 对每个内部员工计算移除后的影响
        failure_impact = {}
        
        for employee in internal_nodes:
            if employee not in G:
                continue
            
            # 创建移除该节点后的图
            G_removed = G.copy()
            G_removed.remove_node(employee)
            
            # 计算移除后的最大连通分量
            new_components = list(nx.connected_components(G_removed))
            new_largest = max(len(c) for c in new_components) if new_components else 0
            
            # 计算碎片化程度
            fragmentation = 1 - (new_largest / original_largest) if original_largest > 0 else 0
            
            # 计算该员工独占的外部联系人
            exclusive_external = 0
            employee_external = set()
            
            for neighbor in G.neighbors(employee):
                if "vulcanshield" not in neighbor.lower():
                    employee_external.add(neighbor)
                    # 检查是否只有这个员工联系该外部人
                    other_internal_connections = 0
                    for n2 in G.neighbors(neighbor):
                        if n2 != employee and "vulcanshield" in n2.lower():
                            other_internal_connections += 1
                    if other_internal_connections == 0:
                        exclusive_external += 1
            
            failure_impact[employee] = {
                "fragmentation": fragmentation,
                "exclusive_external_contacts": exclusive_external,
                "total_external_contacts": len(employee_external),
                "degree": G.degree(employee)
            }
        
        # 计算综合单点风险得分
        for employee, impact in failure_impact.items():
            # 综合得分 = 碎片化影响 * 0.5 + 独占外部关系比例 * 0.5
            external_exclusivity = (
                impact["exclusive_external_contacts"] / impact["total_external_contacts"]
                if impact["total_external_contacts"] > 0 else 0
            )
            
            risk_score = impact["fragmentation"] * 0.5 + external_exclusivity * 0.5
            impact["risk_score"] = risk_score
            impact["external_exclusivity"] = external_exclusivity
        
        # 按风险得分排序
        sorted_by_risk = sorted(
            failure_impact.items(),
            key=lambda x: x[1]["risk_score"],
            reverse=True
        )
        
        # 构建节点更新
        node_updates = {}
        for rank, (email, impact) in enumerate(sorted_by_risk, 1):
            risk_level = "high" if impact["risk_score"] > 0.3 else (
                "medium" if impact["risk_score"] > 0.15 else "low"
            )
            
            node_updates[email] = {
                "risk_metrics.single_point_score": round(impact["risk_score"], 4),
                "risk_metrics.fragmentation_impact": round(impact["fragmentation"], 4),
                "risk_metrics.exclusive_external": impact["exclusive_external_contacts"],
                "risk_metrics.single_point_rank": rank,
                "risk_metrics.single_point_level": risk_level
            }
        
        # 生成风险预警
        alerts = []
        for email, impact in sorted_by_risk[:10]:
            if impact["risk_score"] > 0.2:
                alerts.append({
                    "type": "single_point_failure",
                    "severity": "high" if impact["risk_score"] > 0.3 else "medium",
                    "person": email,
                    "score": round(impact["risk_score"], 4),
                    "detail": f"移除后网络碎片化 {impact['fragmentation']*100:.1f}%，" +
                             f"独占 {impact['exclusive_external_contacts']} 个外部联系人"
                })
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "high_risk_count": len([i for i in failure_impact.values() if i["risk_score"] > 0.3]),
                "medium_risk_count": len([i for i in failure_impact.values() if 0.15 < i["risk_score"] <= 0.3]),
                "top_risks": [
                    {
                        "email": email,
                        "risk_score": round(impact["risk_score"], 4),
                        "fragmentation": round(impact["fragmentation"], 4),
                        "exclusive_external": impact["exclusive_external_contacts"]
                    }
                    for email, impact in sorted_by_risk[:10]
                ]
            },
            node_updates=node_updates,
            alerts=alerts
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="single_point_score",
                type="float",
                description="单点故障风险得分，越高说明该人离开的影响越大",
                range=(0, 1),
                higher_is_better=False
            ),
            MetricDefinition(
                name="fragmentation_impact",
                type="float",
                description="移除后的网络碎片化程度",
                range=(0, 1)
            ),
            MetricDefinition(
                name="exclusive_external",
                type="int",
                description="独占的外部联系人数量（只有此人维护的关系）"
            )
        ]


class PercolationAnalysis(BaseAlgorithm):
    """
    渗透分析 - 组织鲁棒性测试
    
    模拟移除 Top N 关键节点后的网络状态
    基于物理学渗透理论评估组织韧性
    """
    
    name = "percolation_analysis"
    layer = "risk"
    description = "渗透分析，测试移除关键人物后的组织鲁棒性"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 构建图
        G = nx.Graph()
        internal_nodes = set()
        
        for node in graph_data.nodes:
            email = node.get("email") or node.get("_id")
            if email:
                G.add_node(email, **node)
                if "vulcanshield" in email.lower():
                    internal_nodes.add(email)
        
        for edge in graph_data.edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and target and source in G.nodes and target in G.nodes:
                G.add_edge(source, target)
        
        if len(G.nodes) == 0:
            return AlgorithmResult(
                success=False,
                algorithm_name=self.name,
                layer=self.layer,
                errors=["No nodes in graph"]
            )
        
        # 按 PageRank 排序（模拟移除最重要的人）
        pagerank = nx.pagerank(G)
        sorted_internal = sorted(
            [(n, pr) for n, pr in pagerank.items() if n in internal_nodes],
            key=lambda x: x[1],
            reverse=True
        )
        
        # 原始最大连通分量
        original_gcc = len(max(nx.connected_components(G), key=len))
        
        # 渐进移除 Top 1, 3, 5, 10 人
        percolation_curve = []
        G_test = G.copy()
        removed = []
        
        checkpoints = [1, 3, 5, 10, 15, 20]
        
        for i, (node, _) in enumerate(sorted_internal):
            G_test.remove_node(node)
            removed.append(node)
            
            if i + 1 in checkpoints:
                components = list(nx.connected_components(G_test))
                gcc_size = max(len(c) for c in components) if components else 0
                fragmentation = 1 - (gcc_size / original_gcc) if original_gcc > 0 else 0
                
                percolation_curve.append({
                    "removed_count": i + 1,
                    "removed_nodes": removed.copy(),
                    "gcc_size": gcc_size,
                    "fragmentation": round(fragmentation, 4),
                    "num_components": len(components)
                })
            
            if i + 1 >= max(checkpoints):
                break
        
        # 评估组织韧性
        # 如果移除 5 人后碎片化 > 20%，则组织脆弱
        fragmentation_at_5 = next(
            (p["fragmentation"] for p in percolation_curve if p["removed_count"] == 5),
            0
        )
        
        robustness_level = "robust" if fragmentation_at_5 < 0.1 else (
            "moderate" if fragmentation_at_5 < 0.2 else "fragile"
        )
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "original_gcc_size": original_gcc,
                "robustness_level": robustness_level,
                "fragmentation_at_5": fragmentation_at_5,
                "percolation_curve": percolation_curve,
                "critical_nodes": [n for n, _ in sorted_internal[:5]]
            }
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="robustness_level",
                type="str",
                description="组织韧性等级: robust/moderate/fragile"
            )
        ]
