"""
中心度算法 - Layer 1 网络拓扑

包含多种中心度计算:
- DegreeCentrality: 度中心度 (信息吞吐量)
- BetweennessCentrality: 中介中心度 (桥梁度)
- PageRankCentrality: PageRank (综合影响力)
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


class DegreeCentrality(BaseAlgorithm):
    """
    度中心度算法
    
    计算每个节点的连接数，反映信息吞吐量。
    hub_score 越高，说明该人员是信息枢纽。
    """
    
    name = "degree_centrality"
    layer = "layer1_network"
    description = "计算节点度中心度，识别信息枢纽"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name} on {len(graph_data.nodes)} nodes, {len(graph_data.edges)} edges")
        
        # 构建 NetworkX 图
        G = nx.Graph()
        
        # 添加节点
        for node in graph_data.nodes:
            email = node.get("email") or node.get("_id")
            if email:
                G.add_node(email, **node)
        
        # 添加边
        for edge in graph_data.edges:
            source = edge.get("source")
            target = edge.get("target")
            weight = edge.get("count", 1)
            if source and target:
                G.add_edge(source, target, weight=weight)
        
        if len(G.nodes) == 0:
            return AlgorithmResult(
                success=False,
                algorithm_name=self.name,
                layer=self.layer,
                errors=["No nodes in graph"]
            )
        
        # 计算度中心度
        degree_centrality = nx.degree_centrality(G)
        
        # 计算加权度中心度
        weighted_degree = {}
        for node in G.nodes():
            weighted_degree[node] = sum(
                G[node][neighbor].get("weight", 1) 
                for neighbor in G.neighbors(node)
            )
        
        # 归一化加权度
        max_weighted = max(weighted_degree.values()) if weighted_degree and max(weighted_degree.values()) > 0 else 1
        weighted_normalized = {
            node: val / max_weighted 
            for node, val in weighted_degree.items()
        }
        
        # 构建节点更新
        node_updates = {}
        for email in G.nodes():
            node_updates[email] = {
                "network_metrics.hub_score": round(weighted_normalized.get(email, 0), 4),
                "network_metrics.degree_centrality": round(degree_centrality.get(email, 0), 4),
                "network_metrics.total_connections": G.degree(email)
            }
        
        # 计算排名
        sorted_by_hub = sorted(
            weighted_normalized.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        for rank, (email, _) in enumerate(sorted_by_hub, 1):
            node_updates[email]["network_metrics.hub_rank"] = rank
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "nodes_processed": len(G.nodes),
                "edges_processed": len(G.edges),
                "max_hub_score": round(max(weighted_normalized.values()), 4) if weighted_normalized else 0,
                "top_hubs": [
                    {"email": email, "hub_score": round(score, 4)} 
                    for email, score in sorted_by_hub[:10]
                ]
            },
            node_updates=node_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="hub_score",
                type="float",
                description="信息枢纽度，值越高说明该人员是信息吞吐量的核心",
                range=(0, 1),
                higher_is_better=None  # 高不一定好，可能过载
            ),
            MetricDefinition(
                name="hub_rank",
                type="int",
                description="枢纽度排名，1 为最高"
            )
        ]


class BetweennessCentrality(BaseAlgorithm):
    """
    中介中心度算法
    
    计算经过该节点的最短路径数量，反映桥梁作用。
    bridge_score 越高，说明该人员是跨领域的关键连接者。
    """
    
    name = "betweenness_centrality"
    layer = "layer1_network"
    description = "计算中介中心度，识别跨领域桥梁"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 构建图
        G = nx.Graph()
        for node in graph_data.nodes:
            email = node.get("email") or node.get("_id")
            if email:
                G.add_node(email)
        
        for edge in graph_data.edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and target:
                G.add_edge(source, target)
        
        if len(G.nodes) == 0:
            return AlgorithmResult(
                success=False,
                algorithm_name=self.name,
                layer=self.layer,
                errors=["No nodes in graph"]
            )
        
        # 计算中介中心度
        betweenness = nx.betweenness_centrality(G)
        
        # 构建节点更新
        node_updates = {}
        for email, score in betweenness.items():
            node_updates[email] = {
                "network_metrics.bridge_score": round(score, 4)
            }
        
        # 计算排名
        sorted_by_bridge = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)
        for rank, (email, _) in enumerate(sorted_by_bridge, 1):
            node_updates[email]["network_metrics.bridge_rank"] = rank
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "max_bridge_score": round(max(betweenness.values()), 4) if betweenness else 0,
                "top_bridges": [
                    {"email": email, "bridge_score": round(score, 4)}
                    for email, score in sorted_by_bridge[:10]
                ]
            },
            node_updates=node_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="bridge_score",
                type="float",
                description="桥梁度，值越高说明该人员连接不同群体的作用越大",
                range=(0, 1),
                higher_is_better=True
            )
        ]


class PageRankCentrality(BaseAlgorithm):
    """
    PageRank 算法
    
    考虑连接的重要性传播，综合评估影响力。
    """
    
    name = "pagerank_centrality"
    layer = "layer1_network"
    description = "计算 PageRank，评估综合影响力"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 构建有向图 (邮件有方向)
        G = nx.DiGraph()
        
        for node in graph_data.nodes:
            email = node.get("email") or node.get("_id")
            if email:
                G.add_node(email)
        
        for edge in graph_data.edges:
            source = edge.get("source")
            target = edge.get("target")
            weight = edge.get("count", 1)
            if source and target:
                # 双向添加
                G.add_edge(source, target, weight=weight)
                G.add_edge(target, source, weight=weight)
        
        if len(G.nodes) == 0:
            return AlgorithmResult(
                success=False,
                algorithm_name=self.name,
                layer=self.layer,
                errors=["No nodes in graph"]
            )
        
        # 计算 PageRank
        try:
            pagerank = nx.pagerank(G, weight="weight")
        except nx.PowerIterationFailedConvergence:
            pagerank = nx.pagerank(G, weight="weight", max_iter=200)
        
        # 归一化到 0-1
        max_pr = max(pagerank.values()) if pagerank else 1
        normalized = {k: v / max_pr for k, v in pagerank.items()}
        
        # 构建节点更新
        node_updates = {}
        for email, score in normalized.items():
            node_updates[email] = {
                "network_metrics.influence_score": round(score, 4)
            }
        
        # 计算排名
        sorted_by_influence = sorted(normalized.items(), key=lambda x: x[1], reverse=True)
        for rank, (email, _) in enumerate(sorted_by_influence, 1):
            node_updates[email]["network_metrics.influence_rank"] = rank
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "top_influencers": [
                    {"email": email, "influence_score": round(score, 4)}
                    for email, score in sorted_by_influence[:10]
                ]
            },
            node_updates=node_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="influence_score",
                type="float",
                description="综合影响力，考虑连接的重要性传播",
                range=(0, 1),
                higher_is_better=True
            )
        ]
