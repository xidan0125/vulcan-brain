"""
Burnout 燃尽指数分析 - Risk Layer

基于工作模式识别潜在的过劳风险：
- 深夜邮件比例 (21:00 后)
- 周末工作比例
- 邮件发送量趋势
- 响应时间模式
"""

import networkx as nx
from typing import List, Dict, Set
from collections import defaultdict
from datetime import datetime, timedelta
import logging

import sys
sys.path.append("/home/xinyue/vulcan-brain")

from enterprise_talent_graph.algorithms.base import (
    BaseAlgorithm, GraphData, AlgorithmResult, MetricDefinition
)

logger = logging.getLogger(__name__)


class BurnoutDetection(BaseAlgorithm):
    """
    燃尽风险检测算法

    分析邮件发送时间模式，识别过劳信号：
    - 深夜邮件 (21:00-06:00) 比例
    - 周末邮件比例
    - 邮件量异常增长

    业务含义：
    - 高燃尽风险者需要关注工作负荷
    - 可能需要人员补充或任务重新分配
    """

    name = "burnout_detection"
    layer = "risk"
    description = "基于工作模式检测燃尽风险"

    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")

        # 收集每个内部员工的邮件时间戳
        # graph_data.raw_data 包含原始邮件数据
        emails = graph_data.emails or []

        if not emails:
            logger.warning("No raw email data available for burnout analysis")
            # 退回到基于节点元数据的分析
            return self._fallback_analysis(graph_data)

        # 按发件人分组统计
        sender_stats = defaultdict(lambda: {
            "total": 0,
            "late_night": 0,  # 21:00 - 06:00
            "weekend": 0,
            "timestamps": []
        })

        for email in emails:
            sender = email.get("from_email", "").lower()
            if "vulcanshield" not in sender:
                continue

            # 解析时间
            sent_time = email.get("sent_time") or email.get("date")
            if not sent_time:
                continue

            if isinstance(sent_time, str):
                try:
                    sent_time = datetime.fromisoformat(sent_time.replace("Z", "+00:00"))
                except:
                    continue

            sender_stats[sender]["total"] += 1
            sender_stats[sender]["timestamps"].append(sent_time)

            # 判断深夜 (21:00 - 06:00)
            hour = sent_time.hour
            if hour >= 21 or hour < 6:
                sender_stats[sender]["late_night"] += 1

            # 判断周末
            if sent_time.weekday() >= 5:  # 5=Saturday, 6=Sunday
                sender_stats[sender]["weekend"] += 1

        # 计算燃尽分数
        burnout_scores = {}

        for email, stats in sender_stats.items():
            if stats["total"] < 10:  # 样本太少，跳过
                continue

            late_night_ratio = stats["late_night"] / stats["total"]
            weekend_ratio = stats["weekend"] / stats["total"]

            # 计算邮件量趋势（最近30%邮件 vs 之前70%）
            volume_growth = 0
            if len(stats["timestamps"]) >= 20:
                sorted_ts = sorted(stats["timestamps"])
                split_point = int(len(sorted_ts) * 0.7)
                early_period = sorted_ts[:split_point]
                late_period = sorted_ts[split_point:]

                if early_period and late_period:
                    early_days = max(1, (early_period[-1] - early_period[0]).days)
                    late_days = max(1, (late_period[-1] - late_period[0]).days)

                    early_rate = len(early_period) / early_days
                    late_rate = len(late_period) / late_days

                    if early_rate > 0:
                        volume_growth = (late_rate - early_rate) / early_rate

            # 综合燃尽分数
            # 权重：深夜40%，周末30%，量增长30%
            burnout_score = (
                late_night_ratio * 0.4 +
                weekend_ratio * 0.3 +
                min(1.0, max(0, volume_growth)) * 0.3
            )

            burnout_scores[email] = {
                "burnout_score": round(burnout_score, 4),
                "late_night_ratio": round(late_night_ratio, 4),
                "weekend_ratio": round(weekend_ratio, 4),
                "volume_growth": round(volume_growth, 4),
                "total_emails": stats["total"]
            }

        # 按燃尽分数排序
        sorted_by_burnout = sorted(
            burnout_scores.items(),
            key=lambda x: x[1]["burnout_score"],
            reverse=True
        )

        # 构建节点更新
        node_updates = {}
        for rank, (email, scores) in enumerate(sorted_by_burnout, 1):
            risk_level = "high" if scores["burnout_score"] > 0.35 else (
                "medium" if scores["burnout_score"] > 0.2 else "low"
            )

            node_updates[email] = {
                "risk_metrics.burnout_score": scores["burnout_score"],
                "risk_metrics.late_night_ratio": scores["late_night_ratio"],
                "risk_metrics.weekend_ratio": scores["weekend_ratio"],
                "risk_metrics.burnout_rank": rank,
                "risk_metrics.burnout_level": risk_level
            }

        # 生成风险预警
        alerts = []
        for email, scores in sorted_by_burnout[:15]:
            if scores["burnout_score"] > 0.25:
                severity = "high" if scores["burnout_score"] > 0.35 else "medium"

                # 构建详细说明
                details = []
                if scores["late_night_ratio"] > 0.2:
                    details.append(f"深夜邮件占比 {scores['late_night_ratio']*100:.0f}%")
                if scores["weekend_ratio"] > 0.15:
                    details.append(f"周末工作占比 {scores['weekend_ratio']*100:.0f}%")
                if scores["volume_growth"] > 0.3:
                    details.append(f"工作量增长 {scores['volume_growth']*100:.0f}%")

                alerts.append({
                    "type": "burnout_risk",
                    "severity": severity,
                    "person": email,
                    "score": scores["burnout_score"],
                    "detail": "，".join(details) if details else "工作模式异常"
                })

        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "analyzed_count": len(burnout_scores),
                "high_risk_count": len([s for s in burnout_scores.values() if s["burnout_score"] > 0.35]),
                "medium_risk_count": len([s for s in burnout_scores.values() if 0.2 < s["burnout_score"] <= 0.35]),
                "avg_late_night_ratio": round(
                    sum(s["late_night_ratio"] for s in burnout_scores.values()) / len(burnout_scores)
                    if burnout_scores else 0, 4
                ),
                "avg_weekend_ratio": round(
                    sum(s["weekend_ratio"] for s in burnout_scores.values()) / len(burnout_scores)
                    if burnout_scores else 0, 4
                ),
                "top_burnout_risks": [
                    {"email": email, **scores}
                    for email, scores in sorted_by_burnout[:10]
                ]
            },
            node_updates=node_updates,
            alerts=alerts
        )

    def _fallback_analysis(self, graph_data: GraphData) -> AlgorithmResult:
        """
        当没有原始邮件数据时，基于节点度数推断工作负荷
        """
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

        # 基于通信量推断工作负荷
        workload_scores = {}
        degrees = dict(G.degree(weight="weight"))
        max_degree = max(degrees.values()) if degrees else 1

        for email in internal_nodes:
            if email not in degrees:
                continue

            # 归一化工作负荷
            normalized_load = degrees[email] / max_degree
            workload_scores[email] = {
                "burnout_score": round(normalized_load * 0.5, 4),  # 保守估计
                "communication_volume": degrees[email],
                "note": "基于通信量推断，无时间模式数据"
            }

        sorted_scores = sorted(
            workload_scores.items(),
            key=lambda x: x[1]["burnout_score"],
            reverse=True
        )

        node_updates = {}
        for rank, (email, scores) in enumerate(sorted_scores, 1):
            node_updates[email] = {
                "risk_metrics.burnout_score": scores["burnout_score"],
                "risk_metrics.burnout_rank": rank,
                "risk_metrics.burnout_level": "unknown"
            }

        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "analyzed_count": len(workload_scores),
                "note": "Fallback mode - no timestamp data available",
                "top_workload": [
                    {"email": email, **scores}
                    for email, scores in sorted_scores[:10]
                ]
            },
            node_updates=node_updates,
            alerts=[]
        )

    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="burnout_score",
                type="float",
                description="燃尽风险得分，越高说明过劳风险越大",
                range=(0, 1),
                higher_is_better=False
            ),
            MetricDefinition(
                name="late_night_ratio",
                type="float",
                description="深夜邮件比例 (21:00-06:00)",
                range=(0, 1)
            ),
            MetricDefinition(
                name="weekend_ratio",
                type="float",
                description="周末邮件比例",
                range=(0, 1)
            )
        ]


class WorkloadTrend(BaseAlgorithm):
    """
    工作负荷趋势分析

    按周/月分析每个人的邮件量变化趋势
    识别工作量异常增长的人员
    """

    name = "workload_trend"
    layer = "risk"
    description = "分析工作负荷变化趋势"

    def run(self, graph_data: GraphData) -> AlgorithmResult:
        logger.info(f"Running {self.name}")

        emails = graph_data.emails or []

        if not emails:
            return AlgorithmResult(
                success=False,
                algorithm_name=self.name,
                layer=self.layer,
                errors=["No raw email data available"]
            )

        # 按发件人和周分组
        weekly_counts = defaultdict(lambda: defaultdict(int))

        for email in emails:
            sender = email.get("from_email", "").lower()
            if "vulcanshield" not in sender:
                continue

            sent_time = email.get("sent_time") or email.get("date")
            if not sent_time:
                continue

            if isinstance(sent_time, str):
                try:
                    sent_time = datetime.fromisoformat(sent_time.replace("Z", "+00:00"))
                except:
                    continue

            # 计算周数 (ISO week)
            week_key = sent_time.strftime("%Y-W%W")
            weekly_counts[sender][week_key] += 1

        # 计算趋势
        trends = {}

        for sender, weeks in weekly_counts.items():
            if len(weeks) < 4:  # 至少4周数据
                continue

            sorted_weeks = sorted(weeks.items())
            counts = [c for _, c in sorted_weeks]

            # 简单线性回归斜率
            n = len(counts)
            x_mean = (n - 1) / 2
            y_mean = sum(counts) / n

            numerator = sum((i - x_mean) * (counts[i] - y_mean) for i in range(n))
            denominator = sum((i - x_mean) ** 2 for i in range(n))

            slope = numerator / denominator if denominator != 0 else 0

            # 归一化斜率（相对于平均值）
            normalized_slope = slope / y_mean if y_mean > 0 else 0

            trends[sender] = {
                "weekly_slope": round(slope, 2),
                "normalized_trend": round(normalized_slope, 4),
                "avg_weekly_volume": round(y_mean, 1),
                "recent_weeks": counts[-4:],
                "total_weeks": n
            }

        # 按趋势排序
        sorted_trends = sorted(
            trends.items(),
            key=lambda x: x[1]["normalized_trend"],
            reverse=True
        )

        # 生成预警
        alerts = []
        for email, trend in sorted_trends[:10]:
            if trend["normalized_trend"] > 0.15:  # 周增长超过15%
                alerts.append({
                    "type": "workload_surge",
                    "severity": "medium",
                    "person": email,
                    "score": trend["normalized_trend"],
                    "detail": f"周均邮件量 {trend['avg_weekly_volume']:.0f}，增长趋势 {trend['normalized_trend']*100:.0f}%"
                })

        return AlgorithmResult(
            success=True,
            algorithm_name=self.name,
            layer=self.layer,
            metrics={
                "analyzed_count": len(trends),
                "increasing_count": len([t for t in trends.values() if t["normalized_trend"] > 0.1]),
                "decreasing_count": len([t for t in trends.values() if t["normalized_trend"] < -0.1]),
                "top_increasing": [
                    {"email": email, **trend}
                    for email, trend in sorted_trends[:10]
                ],
                "top_decreasing": [
                    {"email": email, **trend}
                    for email, trend in sorted_trends[-10:]
                ]
            },
            alerts=alerts
        )

    def get_metrics(self) -> List[MetricDefinition]:
        return [
            MetricDefinition(
                name="normalized_trend",
                type="float",
                description="归一化工作量趋势，正值表示增长"
            )
        ]
