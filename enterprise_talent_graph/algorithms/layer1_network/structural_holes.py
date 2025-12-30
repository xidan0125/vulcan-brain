"""
结构洞算法 - Layer 1 网络拓扑

基于 Ronald Burt 的结构洞理论：
- 占据结构洞的人连接了互不认识的群体
- 这类人往往是创新的来源和信息的控制者
- 约束系数越低，结构洞优势越大
"""

import networkx as nx
from typing import List, Dict
import logging

import sys
sys.path.append("/home/xinyue/vulcan-brain")

from enterprise_talent_graph.algorithms.base import (
    BaseAlgorithm, GraphData, AlgorithmResult, MetricDefinition
)

logger = logging.getLogger(__name__)


class StructuralHoles(BaseAlgorithm):
    """
    结构洞约束系数算法
    
    Burt's Constraint: C_i = Σ(p_ij + Σp_iq*p_qj)²
    
    业务含义：
    - 低约束（< 0.3）：占据结构洞，连接多个互不相连的群体
      → 创新人才、信息掮客、战略价值高
    - 高约束（> 0.7）：网络封闭，朋友圈都是熟人
      → 信息冗余，但团队凝聚力强
    """
    
    name = "structural_holes"
    layer = "layer1_network"
    description = "计算结构洞约束系数，识别创新人才和信息控制者"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 构建无向图
        G = nx.Graph()
        
        for node in graph_data.nodes:
            email = node.get("email") or node.get("_id")
            if email:
                G.add_node(email, **node)
        
        for edge in graph_data.edges:
            source = edge.get("source")
            target = edge.get("target")
            weight = edge.get("weight", edge.get("count", 1))
            if source and target and source in G.nodes and target in G.nodes:
                G.add_edge(source, target, weight=weight)
        
        if len(G.nodes) == 0:
            return AlgorithmResult(
                success=False,
                algorithm_name=self.name,
                layer=self.layer,
                errors=["No nodes in graph"]
            )
        
        # 计算约束系数
        # NetworkX 内置了 constraint 函数
        try:
            constraint = nx.constraint(G, weight="weight")
        except Exception as e:
            logger.warning(f"Weighted constraint failed: {e}, trying unweighted")
            constraint = nx.constraint(G)
        
        # 计算有效规模 (Effective Size)
        # 有效规模 = 邻居数 - 邻居间的冗余连接
        effective_size = {}
        for node in G.nodes():
            neighbors = list(G.neighbors(node))
            n = len(neighbors)
            if n == 0:
                effective_size[node] = 0
                continue
            
            # 计算邻居间的连接数
            redundancy = 0
            for i, ni in enumerate(neighbors):
                for nj in neighbors[i+1:]:
                    if G.has_edge(ni, nj):
                        redundancy += 1
            
            # 有效规模 = n - 2*redundancy/n (近似)
            effective_size[node] = n - (2 * redundancy / n) if n > 0 else 0
        
        # 计算效率 (Efficiency) = 有效规模 / 实际规模
        efficiency = {}
        for node in G.nodes():
            degree = G.degree(node)
            if degree > 0:
                efficiency[node] = effective_size[node] / degree
            else:
                efficiency[node] = 0
        
        # 构建节点更新
        node_updates = {}
        
        # 按约束系数排序（低约束 = 高结构洞优势）
        sorted_by_constraint = sorted(
            [(n, c) for n, c in constraint.items() if c is not None],
            key=lambda x: x[1]
        )
        
        for rank, (email, c) in enumerate(sorted_by_constraint, 1):
            # 结构洞得分 = 1 - 约束系数（归一化）
            structural_hole_score = 1 - min(c, 1)
            
            node_updates[email] = {
                "network_metrics.constraint": round(c, 4) if c else None,
                "network_metrics.structural_hole_score": round(structural_hole_score, 4),
                "network_metrics.effective_size": round(effective_size.get(email, 0), 2),
                "network_metrics.efficiency": round(efficiency.get(email, 0), 4),
                "network_metrics.structural_hole_rank": rank
            }
        
        # 识别结构洞占据者（低约束）
        structural_hole_brokers = [
            {"email": email, "constraint": round(c, 4), "structural_hole_score": round(1-min(c,1), 4)}
            for email, c in sorted_by_constraint[:20]
            if c is not None and c < 0.5
        ]
        
        # 识别封闭网络者（高约束）
        closed_network = [
            {"email": email, "constraint": round(c, 4)}
            for email, c in sorted_by_constraint[-10:]
            if c is not None and c > 0.7
        ]
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "avg_constraint": round(
                    sum(c for c in constraint.values() if c) / 
                    len([c for c in constraint.values() if c]), 4
                ) if constraint else 0,
                "structural_hole_brokers": structural_hole_brokers,
                "closed_network_nodes": closed_network,
                "nodes_with_low_constraint": len([c for c in constraint.values() if c and c < 0.3]),
                "nodes_with_high_constraint": len([c for c in constraint.values() if c and c > 0.7])
            },
            node_updates=node_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="constraint",
                type="float",
                description="Burt约束系数，越低说明越占据结构洞优势",
                range=(0, 1),
                higher_is_better=False
            ),
            MetricDefinition(
                name="structural_hole_score",
                type="float",
                description="结构洞得分 = 1-约束，越高越有信息控制优势",
                range=(0, 1),
                higher_is_better=True
            ),
            MetricDefinition(
                name="effective_size",
                type="float",
                description="有效网络规模，去除冗余连接后的实际影响范围"
            ),
            MetricDefinition(
                name="efficiency",
                type="float",
                description="网络效率，有效规模/实际规模",
                range=(0, 1),
                higher_is_better=True
            )
        ]
