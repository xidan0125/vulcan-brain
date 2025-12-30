"""
外部关系集中度分析 - Layer 4 外部生态

核心算法：HHI (赫芬达尔-赫希曼指数)
- 量化供应链/客户关系的集中度风险
- HHI > 0.25 表示高度集中，存在依赖风险
"""

import networkx as nx
from typing import List, Dict
from collections import defaultdict
import logging

import sys
sys.path.append("/home/xinyue/vulcan-brain")

from enterprise_talent_graph.algorithms.base import (
    BaseAlgorithm, GraphData, AlgorithmResult, MetricDefinition
)

logger = logging.getLogger(__name__)


class HHIConcentration(BaseAlgorithm):
    """
    HHI 集中度指数算法
    
    HHI = Σ(s_i)²，其中 s_i 是第 i 个外部组织的交互份额
    
    业务含义：
    - HHI > 0.25: 高度集中，单一大客户/供应商依赖风险
    - HHI 0.15-0.25: 中度集中
    - HHI < 0.15: 分散，风险较低
    """
    
    name = "hhi_concentration"
    layer = "layer4_external"
    description = "计算外部关系 HHI 集中度指数"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 统计与每个外部域的交互量
        external_interactions = defaultdict(int)
        internal_external_links = defaultdict(lambda: defaultdict(int))
        
        for edge in graph_data.edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            count = edge.get("count", 1)
            
            source_internal = "vulcanshield" in source.lower()
            target_internal = "vulcanshield" in target.lower()
            
            # 只统计内部-外部的边
            if source_internal and not target_internal:
                domain = target.split("@")[-1].lower() if "@" in target else target
                external_interactions[domain] += count
                internal_external_links[source][domain] += count
            elif target_internal and not source_internal:
                domain = source.split("@")[-1].lower() if "@" in source else source
                external_interactions[domain] += count
                internal_external_links[target][domain] += count
        
        if not external_interactions:
            return AlgorithmResult(
                success=False,
                algorithm_name=self.name,
                layer=self.layer,
                errors=["No external interactions found"]
            )
        
        # 计算总交互量
        total_interactions = sum(external_interactions.values())
        
        # 计算每个域的份额和 HHI
        domain_shares = {}
        for domain, count in external_interactions.items():
            share = count / total_interactions
            domain_shares[domain] = {
                "count": count,
                "share": share,
                "share_squared": share ** 2
            }
        
        # 计算 HHI
        hhi = sum(d["share_squared"] for d in domain_shares.values())
        
        # 识别高集中度域（份额 > 10%）
        concentrated_domains = sorted(
            [(d, s) for d, s in domain_shares.items() if s["share"] > 0.05],
            key=lambda x: x[1]["share"],
            reverse=True
        )
        
        # 评估风险等级
        if hhi > 0.25:
            concentration_level = "high"
            risk_description = "外部关系高度集中，存在单一依赖风险"
        elif hhi > 0.15:
            concentration_level = "medium"
            risk_description = "外部关系中度集中"
        else:
            concentration_level = "low"
            risk_description = "外部关系分散，风险较低"
        
        # 计算每个内部员工的外部关系集中度
        employee_concentration = {}
        for employee, domains in internal_external_links.items():
            emp_total = sum(domains.values())
            if emp_total > 0:
                emp_hhi = sum((c/emp_total)**2 for c in domains.values())
                employee_concentration[employee] = {
                    "hhi": emp_hhi,
                    "external_domains": len(domains),
                    "top_domain": max(domains.items(), key=lambda x: x[1])[0]
                }
        
        # 构建节点更新
        node_updates = {}
        for employee, conc in employee_concentration.items():
            node_updates[employee] = {
                "external_metrics.personal_hhi": round(conc["hhi"], 4),
                "external_metrics.external_domain_count": conc["external_domains"],
                "external_metrics.top_external_domain": conc["top_domain"]
            }
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "overall_hhi": round(hhi, 4),
                "concentration_level": concentration_level,
                "risk_description": risk_description,
                "total_external_domains": len(external_interactions),
                "total_external_interactions": total_interactions,
                "top_domains": [
                    {
                        "domain": domain,
                        "count": data["count"],
                        "share": round(data["share"] * 100, 2)
                    }
                    for domain, data in concentrated_domains[:15]
                ]
            },
            node_updates=node_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="overall_hhi",
                type="float",
                description="整体外部关系 HHI 指数，> 0.25 为高集中风险",
                range=(0, 1),
                higher_is_better=False
            ),
            MetricDefinition(
                name="personal_hhi",
                type="float",
                description="个人外部关系 HHI 指数",
                range=(0, 1)
            )
        ]


class ExternalReach(BaseAlgorithm):
    """
    外联广度分析
    
    统计每个人连接的外部组织数量
    识别对外关系的关键维护者
    """
    
    name = "external_reach"
    layer = "layer4_external"
    description = "计算外联广度，识别外部关系维护者"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 统计每个内部员工的外部联系
        external_reach = defaultdict(lambda: {
            "domains": set(),
            "contacts": set(),
            "interaction_count": 0
        })
        
        for edge in graph_data.edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            count = edge.get("count", 1)
            
            source_internal = "vulcanshield" in source.lower()
            target_internal = "vulcanshield" in target.lower()
            
            if source_internal and not target_internal:
                domain = target.split("@")[-1].lower() if "@" in target else target
                external_reach[source]["domains"].add(domain)
                external_reach[source]["contacts"].add(target)
                external_reach[source]["interaction_count"] += count
            elif target_internal and not source_internal:
                domain = source.split("@")[-1].lower() if "@" in source else source
                external_reach[target]["domains"].add(domain)
                external_reach[target]["contacts"].add(source)
                external_reach[target]["interaction_count"] += count
        
        # 计算排名
        reach_scores = []
        for employee, data in external_reach.items():
            reach_scores.append({
                "email": employee,
                "domain_count": len(data["domains"]),
                "contact_count": len(data["contacts"]),
                "interaction_count": data["interaction_count"]
            })
        
        reach_scores.sort(key=lambda x: x["domain_count"], reverse=True)
        
        # 构建节点更新
        node_updates = {}
        for rank, item in enumerate(reach_scores, 1):
            node_updates[item["email"]] = {
                "external_metrics.domain_reach": item["domain_count"],
                "external_metrics.contact_reach": item["contact_count"],
                "external_metrics.external_interactions": item["interaction_count"],
                "external_metrics.reach_rank": rank
            }
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "top_external_connectors": reach_scores[:15],
                "total_internal_with_external": len(reach_scores),
                "avg_domain_reach": round(
                    sum(r["domain_count"] for r in reach_scores) / len(reach_scores), 2
                ) if reach_scores else 0
            },
            node_updates=node_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="domain_reach",
                type="int",
                description="连接的外部组织（域名）数量"
            ),
            MetricDefinition(
                name="contact_reach",
                type="int",
                description="连接的外部联系人数量"
            ),
            MetricDefinition(
                name="reach_rank",
                type="int",
                description="外联广度排名"
            )
        ]


class BoundarySpanner(BaseAlgorithm):
    """
    边界跨越者分析
    
    识别对外关系的关键瓶颈人物
    某些外部关系只通过单一员工维护 = 高风险
    """
    
    name = "boundary_spanner"
    layer = "layer4_external"
    description = "识别外部关系瓶颈人物"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 统计每个外部域由哪些内部员工维护
        domain_maintainers = defaultdict(set)
        domain_interaction_count = defaultdict(int)
        
        for edge in graph_data.edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            count = edge.get("count", 1)
            
            source_internal = "vulcanshield" in source.lower()
            target_internal = "vulcanshield" in target.lower()
            
            if source_internal and not target_internal:
                domain = target.split("@")[-1].lower() if "@" in target else target
                domain_maintainers[domain].add(source)
                domain_interaction_count[domain] += count
            elif target_internal and not source_internal:
                domain = source.split("@")[-1].lower() if "@" in source else source
                domain_maintainers[domain].add(target)
                domain_interaction_count[domain] += count
        
        # 识别单点维护的外部关系
        single_point_domains = []
        multi_point_domains = []
        
        for domain, maintainers in domain_maintainers.items():
            interaction_count = domain_interaction_count[domain]
            
            if len(maintainers) == 1:
                single_point_domains.append({
                    "domain": domain,
                    "sole_maintainer": list(maintainers)[0],
                    "interaction_count": interaction_count,
                    "risk": "high" if interaction_count > 50 else "medium"
                })
            else:
                multi_point_domains.append({
                    "domain": domain,
                    "maintainer_count": len(maintainers),
                    "maintainers": list(maintainers)[:5],
                    "interaction_count": interaction_count
                })
        
        # 按交互量排序
        single_point_domains.sort(key=lambda x: x["interaction_count"], reverse=True)
        
        # 统计每个员工独占维护的域数量
        employee_exclusive = defaultdict(list)
        for item in single_point_domains:
            employee_exclusive[item["sole_maintainer"]].append(item["domain"])
        
        # 构建节点更新
        node_updates = {}
        for employee, exclusive_domains in employee_exclusive.items():
            node_updates[employee] = {
                "external_metrics.exclusive_domains": len(exclusive_domains),
                "external_metrics.exclusive_domain_list": exclusive_domains[:10]
            }
        
        # 生成风险预警
        alerts = []
        for item in single_point_domains[:10]:
            if item["interaction_count"] > 20:
                alerts.append({
                    "type": "boundary_single_point",
                    "severity": item["risk"],
                    "domain": item["domain"],
                    "sole_maintainer": item["sole_maintainer"],
                    "detail": f"外部组织 {item['domain']} 仅由 {item['sole_maintainer'].split('@')[0]} 维护，交互 {item['interaction_count']} 次"
                })
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "single_point_count": len(single_point_domains),
                "multi_point_count": len(multi_point_domains),
                "high_risk_single_points": [
                    d for d in single_point_domains[:20] if d["risk"] == "high"
                ],
                "top_boundary_spanners": [
                    {"email": emp, "exclusive_domains": len(domains)}
                    for emp, domains in sorted(
                        employee_exclusive.items(),
                        key=lambda x: len(x[1]),
                        reverse=True
                    )[:10]
                ]
            },
            node_updates=node_updates,
            alerts=alerts
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="exclusive_domains",
                type="int",
                description="独占维护的外部组织数量"
            )
        ]
