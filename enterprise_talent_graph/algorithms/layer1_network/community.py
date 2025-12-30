"""
社区发现算法 - Layer 1 网络拓扑

识别实际协作圈子（vs 组织架构）
"""

import networkx as nx
import igraph as ig
import leidenalg
from typing import List, Dict
from collections import defaultdict
import logging

import sys
sys.path.append("/home/xinyue/vulcan-brain")

from enterprise_talent_graph.algorithms.base import (
    BaseAlgorithm, GraphData, AlgorithmResult, MetricDefinition
)

logger = logging.getLogger(__name__)


class LeidenCommunity(BaseAlgorithm):
    """
    Leiden 社区发现算法
    
    比 Louvain 更优：
    - 保证社群连通性
    - 更快的收敛速度
    - 更高的模块度
    
    业务含义：识别实际的协作圈子，发现跨部门合作或信息孤岛
    """
    
    name = "leiden_community"
    layer = "layer1_network"
    description = "Leiden 社区发现，识别实际协作圈子"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 构建 NetworkX 图
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
        
        # 转换为 igraph 格式
        node_list = list(G.nodes())
        node_to_idx = {node: i for i, node in enumerate(node_list)}
        
        edges_ig = []
        weights = []
        for u, v, data in G.edges(data=True):
            edges_ig.append((node_to_idx[u], node_to_idx[v]))
            weights.append(data.get("weight", 1))
        
        ig_graph = ig.Graph(n=len(node_list), edges=edges_ig, directed=False)
        ig_graph.vs["name"] = node_list
        ig_graph.es["weight"] = weights
        
        # 运行 Leiden 算法
        partition = leidenalg.find_partition(
            ig_graph, 
            leidenalg.ModularityVertexPartition,
            weights=weights
        )
        
        # 提取社区结果
        communities = defaultdict(list)
        node_community = {}
        
        for idx, community_id in enumerate(partition.membership):
            email = node_list[idx]
            communities[community_id].append(email)
            node_community[email] = community_id
        
        # 计算模块度
        modularity = partition.modularity
        
        # 计算每个社区的统计
        community_stats = []
        for comm_id, members in communities.items():
            # 计算社区内部密度
            subgraph = G.subgraph(members)
            internal_edges = subgraph.number_of_edges()
            max_edges = len(members) * (len(members) - 1) / 2
            density = internal_edges / max_edges if max_edges > 0 else 0
            
            # 内部员工数
            internal_count = sum(1 for m in members if "vulcanshield" in m.lower())
            
            community_stats.append({
                "community_id": comm_id,
                "size": len(members),
                "internal_employees": internal_count,
                "external_contacts": len(members) - internal_count,
                "density": round(density, 4),
                "members": members[:10]  # 只存前10个示例
            })
        
        community_stats.sort(key=lambda x: x["size"], reverse=True)
        
        # 构建节点更新
        node_updates = {}
        for email, comm_id in node_community.items():
            comm_size = len(communities[comm_id])
            node_updates[email] = {
                "network_metrics.community_id": comm_id,
                "network_metrics.community_size": comm_size
            }
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "total_communities": len(communities),
                "modularity": round(modularity, 4),
                "largest_community_size": community_stats[0]["size"] if community_stats else 0,
                "community_stats": community_stats[:10]  # Top 10 社区
            },
            node_updates=node_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="community_id",
                type="int",
                description="所属社区编号，相同编号的人在同一个协作圈子"
            ),
            MetricDefinition(
                name="community_size",
                type="int",
                description="所属社区的成员数量"
            )
        ]


class CrossCommunityBridge(BaseAlgorithm):
    """
    跨社区桥梁识别
    
    识别连接不同社区的关键人物
    这些人是信息在不同圈子间流动的关键渠道
    """
    
    name = "cross_community_bridge"
    layer = "layer1_network"
    description = "识别跨社区桥梁人物"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 构建图
        G = nx.Graph()
        
        for node in graph_data.nodes:
            email = node.get("email") or node.get("_id")
            if email:
                comm_id = node.get("network_metrics", {}).get("community_id")
                G.add_node(email, community_id=comm_id)
        
        for edge in graph_data.edges:
            source = edge.get("source")
            target = edge.get("target")
            weight = edge.get("weight", edge.get("count", 1))
            if source and target and source in G.nodes and target in G.nodes:
                G.add_edge(source, target, weight=weight)
        
        # 计算跨社区连接
        bridge_scores = {}
        
        for node in G.nodes():
            node_comm = G.nodes[node].get("community_id")
            if node_comm is None:
                continue
            
            cross_community_edges = 0
            total_edges = 0
            connected_communities = set()
            
            for neighbor in G.neighbors(node):
                total_edges += 1
                neighbor_comm = G.nodes[neighbor].get("community_id")
                if neighbor_comm is not None and neighbor_comm != node_comm:
                    cross_community_edges += 1
                    connected_communities.add(neighbor_comm)
            
            if total_edges > 0:
                bridge_ratio = cross_community_edges / total_edges
                bridge_scores[node] = {
                    "cross_community_edges": cross_community_edges,
                    "total_edges": total_edges,
                    "bridge_ratio": bridge_ratio,
                    "connected_communities": len(connected_communities)
                }
        
        # 排序找出顶级桥梁
        sorted_bridges = sorted(
            bridge_scores.items(),
            key=lambda x: (x[1]["connected_communities"], x[1]["bridge_ratio"]),
            reverse=True
        )
        
        # 构建节点更新
        node_updates = {}
        for rank, (email, scores) in enumerate(sorted_bridges, 1):
            node_updates[email] = {
                "network_metrics.cross_community_edges": scores["cross_community_edges"],
                "network_metrics.bridge_ratio": round(scores["bridge_ratio"], 4),
                "network_metrics.connected_communities": scores["connected_communities"],
                "network_metrics.bridge_rank": rank
            }
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "top_bridges": [
                    {
                        "email": email,
                        "connected_communities": scores["connected_communities"],
                        "bridge_ratio": round(scores["bridge_ratio"], 4)
                    }
                    for email, scores in sorted_bridges[:10]
                ]
            },
            node_updates=node_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="bridge_ratio",
                type="float",
                description="跨社区连接比例，越高说明越是跨领域的桥梁人物",
                range=(0, 1),
                higher_is_better=True
            ),
            MetricDefinition(
                name="connected_communities",
                type="int",
                description="连接的社区数量，越多说明影响范围越广"
            )
        ]
