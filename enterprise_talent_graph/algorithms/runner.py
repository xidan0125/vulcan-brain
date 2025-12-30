"""
算法运行器 V2 - 支持时间窗口

使用方式:
    from algorithms.runner import AlgorithmRunner

    runner = AlgorithmRunner()

    # 运行所有算法 (指定时间窗口)
    results = runner.run_all(time_window="90d")

    # 支持的时间窗口: 30d, 90d, 180d, 365d, all
"""

import time
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from pymongo import MongoClient

from .base import BaseAlgorithm, GraphData, AlgorithmResult
from .registry import get_registry, AlgorithmRegistry

logger = logging.getLogger(__name__)

# 预定义时间窗口
VALID_TIME_WINDOWS = ["30d", "90d", "180d", "365d", "all"]


class AlgorithmRunner:
    """算法运行器 (支持时间窗口)"""

    def __init__(self, mongo_uri: str = "mongodb://localhost:27017",
                 db_name: str = "vulcan_brain"):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.registry = get_registry()
        self.registry.auto_discover()

    def _get_collection_names(self, time_window: str) -> tuple:
        """获取对应时间窗口的集合名"""
        if time_window == "all" or time_window == "default":
            return "talent_nodes", "talent_edges"
        else:
            return f"talent_nodes_{time_window}", f"talent_edges_{time_window}"

    def build_graph_data(self, time_window: str = "all", include_emails: bool = False) -> GraphData:
        """
        从数据库构建图数据 (支持时间窗口)

        Args:
            time_window: 时间窗口 (30d, 90d, 180d, 365d, all)
            include_emails: 是否包含原始邮件数据

        Returns:
            GraphData: 图数据容器
        """
        if time_window not in VALID_TIME_WINDOWS:
            raise ValueError(f"Invalid time_window: {time_window}. Valid options: {VALID_TIME_WINDOWS}")

        nodes_col, edges_col = self._get_collection_names(time_window)
        logger.info(f"Building graph data from {nodes_col}, {edges_col} (time_window: {time_window})")

        # 从对应的集合获取数据
        nodes = list(self.db[nodes_col].find({}))
        edges = list(self.db[edges_col].find({}))

        if not nodes:
            # 尝试默认集合
            logger.warning(f"Collection {nodes_col} is empty, falling back to talent_nodes")
            nodes = list(self.db.talent_nodes.find({}))
            edges = list(self.db.talent_edges.find({}))

        # 映射字段名
        for edge in edges:
            if 'from_email' in edge:
                edge['source'] = edge['from_email']
            if 'to_email' in edge:
                edge['target'] = edge['to_email']
            if 'interaction_count' in edge and 'count' not in edge:
                edge['count'] = edge['interaction_count']

        logger.info(f"Loaded {len(nodes)} nodes, {len(edges)} edges")

        return GraphData(
            nodes=nodes,
            edges=edges,
            emails=None,
            config={
                "built_at": datetime.now().isoformat(),
                "time_window": time_window
            }
        )

    def run_all(self, time_window: str = "all", save_results: bool = True) -> Dict[str, AlgorithmResult]:
        """
        运行所有注册的算法

        Args:
            time_window: 时间窗口
            save_results: 是否保存结果到数据库

        Returns:
            所有算法结果
        """
        logger.info(f"Running all algorithms (time_window: {time_window})...")
        start_time = time.time()

        # 构建图数据
        graph_data = self.build_graph_data(time_window=time_window)

        results = {}
        layers = ["layer1_network", "layer2_semantics", "layer3_functions", "layer4_external", "risk"]

        for layer in layers:
            layer_results = self.run_layer(layer, graph_data=graph_data, save_results=False)
            results.update(layer_results)

        if save_results:
            self._save_all_results(results, time_window)

        elapsed = time.time() - start_time
        logger.info(f"All algorithms completed in {elapsed:.2f}s")

        return results

    def run_layer(self, layer: str, graph_data: Optional[GraphData] = None,
                  time_window: str = "all", save_results: bool = True) -> Dict[str, AlgorithmResult]:
        """运行某一层的所有算法"""
        logger.info(f"Running layer: {layer}")

        if graph_data is None:
            graph_data = self.build_graph_data(time_window=time_window)

        algorithms = self.registry.get_by_layer(layer)
        results = {}

        for algo_class in algorithms:
            try:
                algo = algo_class()
                logger.info(f"  Running {algo.name}...")
                start = time.time()
                result = algo.run(graph_data)
                elapsed = time.time() - start
                logger.info(f"    Done in {elapsed:.2f}s")
                results[algo.name] = result
            except Exception as e:
                logger.error(f"  Error in {algo_class.__name__}: {e}")

        if save_results:
            self._save_all_results(results, time_window)

        return results

    def run_algorithm(self, name: str, time_window: str = "all",
                      save_results: bool = True) -> Optional[AlgorithmResult]:
        """运行单个算法"""
        algo = self.registry.get(name)
        if not algo:
            logger.error(f"Algorithm not found: {name}")
            return None

        graph_data = self.build_graph_data(time_window=time_window)
        result = algo.run(graph_data)

        if save_results:
            self._save_all_results({name: result}, time_window)

        return result

    def _save_all_results(self, results: Dict[str, AlgorithmResult], time_window: str):
        """保存所有算法结果到数据库"""
        nodes_col, _ = self._get_collection_names(time_window)

        # 汇总所有节点指标
        node_metrics = {}
        risk_alerts = []

        for algo_name, result in results.items():
            # 收集节点指标
            for email, metrics in result.node_updates.items():
                if email not in node_metrics:
                    node_metrics[email] = {}
                node_metrics[email].update(metrics)

            # 收集风险预警
            risk_alerts.extend(result.alerts)

        # 更新节点
        for email, metrics in node_metrics.items():
            # 按类型分组
            network_metrics = {}
            risk_metrics = {}
            external_metrics = {}
            function_metrics = {}
            semantic_metrics = {}

            for key, value in metrics.items():
                # 去除前缀 (network_metrics., risk_metrics., etc.)
                clean_key = key.split('.')[-1] if '.' in key else key
                
                # FIRST check risk-related keywords (before 'score')
                if any(k in key for k in ['single_point', 'fragmentation', 'exclusive', 'burnout', 'flight', 'retention', 'isolation', 'marginalization']):
                    risk_metrics[clean_key] = value
                elif any(k in key for k in ['centrality', 'score', 'rank', 'community', 'bridge', 'constraint', 'size', 'efficiency', 'connections', 'ratio', 'edges']):
                    network_metrics[clean_key] = value
                elif any(k in key for k in ['external', 'domain', 'hhi', 'reach', 'contact']):
                    external_metrics[clean_key] = value
                elif any(k in key for k in ['function', 'topic', 'primary']):
                    function_metrics[clean_key] = value
                elif any(k in key for k in ['relationship', 'pattern', 'hours', 'volume']):
                    semantic_metrics[clean_key] = value
                else:
                    network_metrics[clean_key] = value

            update_doc = {"$set": {}}
            # Use dot notation to merge fields instead of replacing entire subdocuments
            for key, value in network_metrics.items():
                update_doc["$set"][f"network_metrics.{key}"] = value
            for key, value in risk_metrics.items():
                update_doc["$set"][f"risk_metrics.{key}"] = value
            for key, value in external_metrics.items():
                update_doc["$set"][f"external_metrics.{key}"] = value
            for key, value in function_metrics.items():
                update_doc["$set"][f"function_metrics.{key}"] = value
            for key, value in semantic_metrics.items():
                update_doc["$set"][f"semantic_metrics.{key}"] = value

            update_doc["$set"]["time_window"] = time_window
            update_doc["$set"]["updated_at"] = datetime.now()

            if update_doc["$set"]:
                self.db[nodes_col].update_one(
                    {"email": email},
                    update_doc,
                    upsert=False
                )

        # 保存风险预警
        if risk_alerts:
            risk_col = f"risk_alerts_{time_window}" if time_window != "all" else "risk_alerts"
            self.db[risk_col].delete_many({"time_window": time_window})
            for alert in risk_alerts:
                alert["time_window"] = time_window
            self.db[risk_col].insert_many(risk_alerts)

        logger.info(f"Saved metrics for {len(node_metrics)} nodes, {len(risk_alerts)} alerts")


def run_all_time_windows():
    """为所有时间窗口运行算法"""
    runner = AlgorithmRunner()

    for tw in VALID_TIME_WINDOWS:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing time window: {tw}")
        logger.info(f"{'='*60}")
        try:
            runner.run_all(time_window=tw)
        except Exception as e:
            logger.error(f"Error processing {tw}: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_all_time_windows()
