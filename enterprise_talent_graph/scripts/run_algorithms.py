#!/usr/bin/env python3
"""
运行所有算法并保存结果到 MongoDB
"""

import sys
import logging
sys.path.append("/home/xinyue/vulcan-brain")

from enterprise_talent_graph.algorithms.runner import AlgorithmRunner

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 60)
    logger.info("企业人才图谱 - 算法执行")
    logger.info("=" * 60)
    
    runner = AlgorithmRunner()
    
    # 显示已注册的算法
    algorithms = runner.registry.list_algorithms()
    logger.info(f"\n已注册算法 ({len(algorithms)} 个):")
    for algo in algorithms:
        logger.info(f"  - [{algo['layer']}] {algo['name']}: {algo['description']}")
    
    # 运行所有算法
    logger.info("\n开始运行算法...")
    results = runner.run_all(save_results=True)
    
    # 打印结果摘要
    logger.info("\n" + "=" * 60)
    logger.info("算法执行结果摘要")
    logger.info("=" * 60)
    
    for layer, layer_results in results.items():
        logger.info(f"\n{layer}:")
        for result in layer_results:
            status = "✓" if result.success else "✗"
            logger.info(f"  {status} {result.algorithm_name} ({result.execution_time_ms}ms)")
            
            if result.success and result.metrics:
                # 打印关键指标
                for key, value in result.metrics.items():
                    if isinstance(value, (int, float, str)):
                        logger.info(f"      {key}: {value}")
                    elif isinstance(value, list) and len(value) <= 5:
                        logger.info(f"      {key}: {value}")
            
            if result.errors:
                for error in result.errors:
                    logger.error(f"      Error: {error}")
    
    # 统计
    total = sum(len(r) for r in results.values())
    success = sum(1 for layer_results in results.values() for r in layer_results if r.success)
    logger.info(f"\n总计: {success}/{total} 算法成功执行")
    
    return results


if __name__ == "__main__":
    main()
