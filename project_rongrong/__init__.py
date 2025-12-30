"""
Project Rongrong - 企业邮件智能日报系统 v4.0

架构:
    Stage 1: Filter 分流 (vLLM-2, Port 8003)
    Stage 2: 6 Agent 并行处理 (vLLM-1, Port 8000)
    Stage 3: 执行摘要生成

目录结构:
    project_rongrong/
    ├── __init__.py          # 本文件
    ├── config.py            # 配置
    ├── pipeline.py          # 主管道调度
    ├── services/
    │   ├── filter.py        # Stage 1: 邮件分流 (v15)
    │   └── vllm_client.py   # vLLM 调用封装
    ├── agents/
    │   ├── base.py          # Agent 基类
    │   ├── customer.py      # 销售 Agent
    │   ├── supply_chain.py  # 交付 Agent
    │   ├── logistics.py     # 物流 Agent
    │   ├── management.py    # 管理 Agent
    │   ├── admin.py         # 行政 Agent (VLM)
    │   └── file.py          # 文件 Agent (VLM)
    └── scripts/
        └── run_daily.py     # 每日执行脚本
"""

__version__ = "4.0.0"
__author__ = "Vulcan Brain"
