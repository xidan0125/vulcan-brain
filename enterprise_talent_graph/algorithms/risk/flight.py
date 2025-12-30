"""
Flight Risk 离职风险分析 - Risk Layer

基于网络行为变化识别潜在离职风险：
- 通信模式变化（减少内部沟通）
- 网络隔离趋势
- 离职传染效应（同事离职后的风险）
- 外部联系增加（可能在找工作）
"""

import networkx as nx
from typing import List, Dict, Set, Optional
from collections import defaultdict
from datetime import datetime, timedelta
import logging
import math

import sys
sys.path.append("/home/xinyue/vulcan-brain")

from enterprise_talent_graph.algorithms.base import (
    BaseAlgorithm, GraphData, AlgorithmResult, MetricDefinition
)

logger = logging.getLogger(__name__)


class FlightRiskDetection(BaseAlgorithm):
    """
    离职风险检测算法

    基于多维度信号识别离职风险：
    1. 内部通信减少
    2. 与核心团队的互动下降
    3. 同事离职的传染效应
    4. 外部联系异常增加

    业务含义：
    - 高风险者可能需要管理层关注
    - 及时干预可能留住关键人才
    """

    name = "flight_risk_detection"
    layer = "risk"
    description = "基于网络行为变化检测离职风险"

    def __init__(self, departed_employees: Optional[List[str]] = None):
        """
        Args:
            departed_employees: 已知离职员工列表，用于计算传染效应
        """
        super().__init__()
        self.departed_employees = set(departed_employees or [])

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

        # 计算各项指标
        flight_scores = {}

        # 1. 计算内部连接度（与同事的联系强度）
        internal_connectivity = {}
        for email in internal_nodes:
            if email not in G:
                continue

            internal_weight = 0
            external_weight = 0

            for neighbor in G.neighbors(email):
                edge_weight = G[email][neighbor].get("weight", 1)
                if "vulcanshield" in neighbor.lower():
                    internal_weight += edge_weight
                else:
                    external_weight += edge_weight

            total_weight = internal_weight + external_weight
            internal_ratio = internal_weight / total_weight if total_weight > 0 else 0

            internal_connectivity[email] = {
                "internal_weight": internal_weight,
                "external_weight": external_weight,
                "internal_ratio": internal_ratio
            }

        # 2. 计算网络中心度（边缘化程度）
        try:
            pagerank = nx.pagerank(G)
        except:
            pagerank = {n: 1/len(G.nodes) for n in G.nodes}

        # 3. 计算社区归属强度
        try:
            from community import community_louvain
            partition = community_louvain.best_partition(G)
        except:
            partition = {n: 0 for n in G.nodes}

        community_strength = {}
        for email in internal_nodes:
            if email not in G or email not in partition:
                continue

            my_community = partition[email]
            same_community_weight = 0
            total_weight = 0

            for neighbor in G.neighbors(email):
                edge_weight = G[email][neighbor].get("weight", 1)
                total_weight += edge_weight
                if partition.get(neighbor) == my_community:
                    same_community_weight += edge_weight

            community_strength[email] = (
                same_community_weight / total_weight if total_weight > 0 else 0
            )

        # 4. 计算离职传染效应
        contagion_scores = {}
        if self.departed_employees:
            for email in internal_nodes:
                if email not in G:
                    continue

                contagion = 0
                for departed in self.departed_employees:
                    if departed in G and G.has_edge(email, departed):
                        # 与离职者的关系强度
                        weight = G[email][departed].get("weight", 1)
                        contagion += math.log1p(weight)

                contagion_scores[email] = contagion
        else:
            contagion_scores = {email: 0 for email in internal_nodes}

        # 归一化并计算综合风险分数
        max_pagerank = max(pagerank.values()) if pagerank else 1
        max_contagion = max(contagion_scores.values()) if contagion_scores and max(contagion_scores.values()) > 0 else 1

        for email in internal_nodes:
            if email not in G:
                continue

            conn = internal_connectivity.get(email, {"internal_ratio": 0.5})
            pr = pagerank.get(email, 0)
            cs = community_strength.get(email, 0.5)
            ct = contagion_scores.get(email, 0)

            # 低内部连接 → 高风险
            isolation_risk = 1 - conn["internal_ratio"]

            # 低中心度 → 边缘化 → 高风险
            marginalization_risk = 1 - (pr / max_pagerank)

            # 低社区归属 → 高风险
            detachment_risk = 1 - cs

            # 传染风险
            contagion_risk = ct / max_contagion if max_contagion > 0 else 0

            # 综合风险分数
            # 权重：隔离30%，边缘化25%，脱离25%，传染20%
            flight_score = (
                isolation_risk * 0.30 +
                marginalization_risk * 0.25 +
                detachment_risk * 0.25 +
                contagion_risk * 0.20
            )

            flight_scores[email] = {
                "flight_score": round(flight_score, 4),
                "isolation_risk": round(isolation_risk, 4),
                "marginalization_risk": round(marginalization_risk, 4),
                "detachment_risk": round(detachment_risk, 4),
                "contagion_risk": round(contagion_risk, 4),
                "internal_ratio": round(conn["internal_ratio"], 4),
                "pagerank": round(pr, 6)
            }

        # 按风险分数排序
        sorted_by_risk = sorted(
            flight_scores.items(),
            key=lambda x: x[1]["flight_score"],
            reverse=True
        )

        # 构建节点更新
        node_updates = {}
        for rank, (email, scores) in enumerate(sorted_by_risk, 1):
            risk_level = "high" if scores["flight_score"] > 0.6 else (
                "medium" if scores["flight_score"] > 0.4 else "low"
            )

            node_updates[email] = {
                "risk_metrics.flight_score": scores["flight_score"],
                "risk_metrics.flight_rank": rank,
                "risk_metrics.flight_level": risk_level,
                "risk_metrics.isolation_risk": scores["isolation_risk"],
                "risk_metrics.marginalization_risk": scores["marginalization_risk"]
            }

        # 生成风险预警
        alerts = []
        for email, scores in sorted_by_risk[:15]:
            if scores["flight_score"] > 0.5:
                severity = "high" if scores["flight_score"] > 0.65 else "medium"

                # 分析主要风险因素
                risk_factors = []
                if scores["isolation_risk"] > 0.6:
                    risk_factors.append("内部联系较少")
                if scores["marginalization_risk"] > 0.7:
                    risk_factors.append("处于网络边缘")
                if scores["detachment_risk"] > 0.6:
                    risk_factors.append("与核心团队脱离")
                if scores["contagion_risk"] > 0.3:
                    risk_factors.append("受离职同事影响")

                alerts.append({
                    "type": "flight_risk",
                    "severity": severity,
                    "person": email,
                    "score": scores["flight_score"],
                    "detail": "，".join(risk_factors) if risk_factors else "多项风险指标偏高"
                })

        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "analyzed_count": len(flight_scores),
                "high_risk_count": len([s for s in flight_scores.values() if s["flight_score"] > 0.6]),
                "medium_risk_count": len([s for s in flight_scores.values() if 0.4 < s["flight_score"] <= 0.6]),
                "avg_internal_ratio": round(
                    sum(s["internal_ratio"] for s in flight_scores.values()) / len(flight_scores)
                    if flight_scores else 0, 4
                ),
                "departed_employees_count": len(self.departed_employees),
                "top_flight_risks": [
                    {"email": email, **scores}
                    for email, scores in sorted_by_risk[:10]
                ]
            },
            node_updates=node_updates,
            alerts=alerts
        )

    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="flight_score",
                type="float",
                description="离职风险得分，越高说明离职可能性越大",
                range=(0, 1),
                higher_is_better=False
            ),
            MetricDefinition(
                name="isolation_risk",
                type="float",
                description="隔离风险，内部联系较少",
                range=(0, 1)
            ),
            MetricDefinition(
                name="marginalization_risk",
                type="float",
                description="边缘化风险，处于网络边缘位置",
                range=(0, 1)
            ),
            MetricDefinition(
                name="contagion_risk",
                type="float",
                description="传染风险，与离职者关系密切",
                range=(0, 1)
            )
        ]


class RetentionAnalysis(BaseAlgorithm):
    """
    人才保留分析

    识别关键人才并评估保留优先级：
    - 结合影响力和离职风险
    - 给出保留建议优先级
    """

    name = "retention_analysis"
    layer = "risk"
    description = "分析人才保留优先级"

    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")

        # 获取已有的指标
        node_metrics = {}
        for node in graph_data.nodes:
            email = node.get("email") or node.get("_id")
            if not email or "vulcanshield" not in email.lower():
                continue

            # 从节点数据提取指标
            metrics = node.get("metrics", {})
            risk_metrics = node.get("risk_metrics", {})

            influence = metrics.get("influence_score", 0)
            flight_risk = risk_metrics.get("flight_score", 0)
            single_point = risk_metrics.get("single_point_score", 0)

            if influence > 0 or flight_risk > 0:
                node_metrics[email] = {
                    "influence": influence,
                    "flight_risk": flight_risk,
                    "single_point_risk": single_point
                }

        if not node_metrics:
            return AlgorithmResult(
                success=False,
                algorithm_name=self.name,
                layer=self.layer,
                errors=["No metrics data available for retention analysis"]
            )

        # 计算保留优先级
        # 高影响力 + 高离职风险 = 最高优先级
        retention_priority = {}

        max_influence = max(m["influence"] for m in node_metrics.values()) or 1

        for email, metrics in node_metrics.items():
            normalized_influence = metrics["influence"] / max_influence

            # 保留优先级 = 影响力 × 风险
            priority_score = (
                normalized_influence * 0.5 +
                metrics["flight_risk"] * 0.3 +
                metrics["single_point_risk"] * 0.2
            )

            # 只有当影响力和风险都显著时才是高优先级
            if normalized_influence > 0.3 and metrics["flight_risk"] > 0.4:
                priority_category = "critical"
            elif normalized_influence > 0.2 or metrics["flight_risk"] > 0.5:
                priority_category = "high"
            elif normalized_influence > 0.1 or metrics["flight_risk"] > 0.3:
                priority_category = "medium"
            else:
                priority_category = "low"

            retention_priority[email] = {
                "priority_score": round(priority_score, 4),
                "priority_category": priority_category,
                "influence": round(normalized_influence, 4),
                "flight_risk": metrics["flight_risk"],
                "single_point_risk": metrics["single_point_risk"]
            }

        # 按优先级排序
        sorted_by_priority = sorted(
            retention_priority.items(),
            key=lambda x: x[1]["priority_score"],
            reverse=True
        )

        # 生成建议
        alerts = []
        for email, priority in sorted_by_priority[:10]:
            if priority["priority_category"] in ["critical", "high"]:
                alerts.append({
                    "type": "retention_priority",
                    "severity": "high" if priority["priority_category"] == "critical" else "medium",
                    "person": email,
                    "score": priority["priority_score"],
                    "detail": f"影响力 {priority['influence']*100:.0f}%，离职风险 {priority['flight_risk']*100:.0f}%"
                })

        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "analyzed_count": len(retention_priority),
                "critical_count": len([p for p in retention_priority.values() if p["priority_category"] == "critical"]),
                "high_count": len([p for p in retention_priority.values() if p["priority_category"] == "high"]),
                "retention_priorities": [
                    {"email": email, **priority}
                    for email, priority in sorted_by_priority[:15]
                ]
            },
            alerts=alerts
        )

    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="priority_score",
                type="float",
                description="保留优先级分数",
                range=(0, 1),
                higher_is_better=True
            ),
            MetricDefinition(
                name="priority_category",
                type="str",
                description="优先级类别: critical/high/medium/low"
            )
        ]
