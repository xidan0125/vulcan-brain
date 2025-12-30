"""
关系类型分类 - Layer 2 关系语义

使用本地 LLM (Qwen3) 分析邮件交互模式，识别关系类型
"""

import httpx
import json
import logging
from typing import List, Dict, Tuple
from collections import defaultdict

import sys
sys.path.append("/home/xinyue/vulcan-brain")

from enterprise_talent_graph.algorithms.base import (
    BaseAlgorithm, GraphData, AlgorithmResult, MetricDefinition
)

logger = logging.getLogger(__name__)

VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"


class RelationshipClassifier(BaseAlgorithm):
    """
    关系类型分类器
    
    分析邮件交互模式，识别：
    - hierarchy: 上下级关系 (指令型单向)
    - peer: 同事协作 (双向对等)
    - external_client: 外部客户
    - external_vendor: 外部供应商
    - external_partner: 外部合作伙伴
    """
    
    name = "relationship_classifier"
    layer = "layer2_semantics"
    description = "使用 AI 分析关系类型"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 只处理内部员工之间 + 内部-外部的关系
        # 收集每对关系的特征
        edge_features = {}
        
        for edge in graph_data.edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            count = edge.get("count", 1)
            weight = edge.get("weight", 1)
            is_reciprocal = edge.get("is_reciprocal", False)
            
            if not source or not target:
                continue
            
            # 生成 edge_id
            pair = tuple(sorted([source, target]))
            edge_id = f"{pair[0]}||{pair[1]}"
            
            if edge_id not in edge_features:
                edge_features[edge_id] = {
                    "source": source,
                    "target": target,
                    "source_to_target": 0,
                    "target_to_source": 0,
                    "total_weight": 0,
                    "is_reciprocal": False
                }
            
            # 累加方向性统计
            if source == pair[0]:
                edge_features[edge_id]["source_to_target"] += count
            else:
                edge_features[edge_id]["target_to_source"] += count
            
            edge_features[edge_id]["total_weight"] += weight
            if is_reciprocal:
                edge_features[edge_id]["is_reciprocal"] = True
        
        # 基于规则分类关系类型（不调用 LLM，提高效率）
        edge_updates = {}
        relationship_stats = defaultdict(int)
        
        for edge_id, features in edge_features.items():
            source = features["source"]
            target = features["target"]
            s_to_t = features["source_to_target"]
            t_to_s = features["target_to_source"]
            total = s_to_t + t_to_s
            
            if total == 0:
                continue
            
            source_internal = "vulcanshield" in source.lower()
            target_internal = "vulcanshield" in target.lower()
            
            # 计算对称性
            symmetry = min(s_to_t, t_to_s) / max(s_to_t, t_to_s) if max(s_to_t, t_to_s) > 0 else 0
            
            # 分类规则
            if source_internal and target_internal:
                # 内部关系
                if symmetry > 0.6:
                    rel_type = "peer"  # 双向对等 = 同事协作
                elif symmetry < 0.2:
                    rel_type = "hierarchy"  # 单向 = 上下级
                else:
                    rel_type = "mixed"
            else:
                # 外部关系 - 根据域名特征判断
                external = target if source_internal else source
                domain = external.split("@")[-1].lower() if "@" in external else ""
                
                # 简单规则判断
                if any(kw in domain for kw in ['bank', 'finance', 'dbs', 'ocbc', 'uob']):
                    rel_type = "external_financial"
                elif any(kw in domain for kw in ['gov', 'iras', 'acra', 'mom']):
                    rel_type = "external_government"
                elif any(kw in domain for kw in ['shipping', 'logistics', 'freight', 'dhl', 'fedex']):
                    rel_type = "external_logistics"
                elif symmetry > 0.4:
                    rel_type = "external_partner"  # 双向交流 = 合作伙伴
                elif s_to_t > t_to_s and source_internal:
                    rel_type = "external_vendor"  # 我们主动联系 = 供应商
                else:
                    rel_type = "external_client"  # 对方主动联系 = 客户
            
            edge_updates[edge_id] = {
                "relationship_type": rel_type,
                "symmetry_ratio": round(symmetry, 4),
                "interaction_direction": "bidirectional" if symmetry > 0.3 else "unidirectional"
            }
            
            relationship_stats[rel_type] += 1
        
        # 更新节点的关系类型统计
        node_relationships = defaultdict(lambda: defaultdict(int))
        for edge_id, updates in edge_updates.items():
            parts = edge_id.split("||")
            for p in parts:
                node_relationships[p][updates["relationship_type"]] += 1
        
        node_updates = {}
        for email, rel_counts in node_relationships.items():
            primary_type = max(rel_counts.items(), key=lambda x: x[1])[0] if rel_counts else "unknown"
            node_updates[email] = {
                "semantic_metrics.primary_relationship_type": primary_type,
                "semantic_metrics.relationship_distribution": dict(rel_counts)
            }
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "total_relationships_classified": len(edge_updates),
                "relationship_distribution": dict(relationship_stats)
            },
            node_updates=node_updates,
            edge_updates=edge_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="relationship_type",
                type="str",
                description="关系类型: peer/hierarchy/external_client/external_vendor/external_partner"
            ),
            MetricDefinition(
                name="symmetry_ratio",
                type="float",
                description="沟通对称性，越高越双向对等"
            )
        ]


class CommunicationPattern(BaseAlgorithm):
    """
    沟通模式分析
    
    分析沟通的时间模式和强度，识别：
    - 工作时间沟通比例
    - 响应速度模式
    - 沟通频率趋势
    """
    
    name = "communication_pattern"
    layer = "layer2_semantics"
    description = "分析沟通时间模式"
    
    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")
        
        # 如果有原始邮件数据，分析时间模式
        if not graph_data.emails:
            return AlgorithmResult(
                success=True,
                algorithm_name=self.name,
                layer=self.layer,
                metrics={"note": "No email data available for time pattern analysis"}
            )
        
        # 统计每个人的发件时间分布
        person_time_stats = defaultdict(lambda: {
            "work_hours": 0,  # 9-18
            "after_hours": 0,  # 18-22
            "night": 0,  # 22-9
            "weekend": 0,
            "total": 0
        })
        
        for email in graph_data.emails:
            sender = email.get("from", {})
            if isinstance(sender, dict):
                sender_email = sender.get("address", "").lower()
            else:
                sender_email = str(sender).lower()
            
            if not sender_email or "vulcanshield" not in sender_email:
                continue
            
            # 解析时间
            received_at = email.get("received_at")
            if not received_at:
                continue
            
            try:
                if hasattr(received_at, 'hour'):
                    hour = received_at.hour
                    weekday = received_at.weekday()
                else:
                    continue
                
                person_time_stats[sender_email]["total"] += 1
                
                if weekday >= 5:  # 周末
                    person_time_stats[sender_email]["weekend"] += 1
                elif 9 <= hour < 18:  # 工作时间
                    person_time_stats[sender_email]["work_hours"] += 1
                elif 18 <= hour < 22:  # 加班
                    person_time_stats[sender_email]["after_hours"] += 1
                else:  # 深夜/凌晨
                    person_time_stats[sender_email]["night"] += 1
                    
            except Exception as e:
                continue
        
        # 计算比例并更新节点
        node_updates = {}
        for email, stats in person_time_stats.items():
            if stats["total"] < 10:  # 忽略样本量太小的
                continue
            
            total = stats["total"]
            work_ratio = stats["work_hours"] / total
            after_hours_ratio = (stats["after_hours"] + stats["night"] + stats["weekend"]) / total
            
            # 判断工作模式
            if after_hours_ratio > 0.4:
                work_pattern = "intensive"  # 高强度
            elif after_hours_ratio > 0.2:
                work_pattern = "extended"  # 经常加班
            else:
                work_pattern = "normal"  # 正常
            
            node_updates[email] = {
                "semantic_metrics.work_hours_ratio": round(work_ratio, 4),
                "semantic_metrics.after_hours_ratio": round(after_hours_ratio, 4),
                "semantic_metrics.work_pattern": work_pattern,
                "semantic_metrics.email_volume": total
            }
        
        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "employees_analyzed": len(node_updates),
                "intensive_workers": len([n for n in node_updates.values() if n.get("semantic_metrics.work_pattern") == "intensive"]),
                "extended_workers": len([n for n in node_updates.values() if n.get("semantic_metrics.work_pattern") == "extended"])
            },
            node_updates=node_updates
        )
    
    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="work_pattern",
                type="str",
                description="工作模式: normal/extended/intensive"
            ),
            MetricDefinition(
                name="after_hours_ratio",
                type="float",
                description="非工作时间邮件比例"
            )
        ]
