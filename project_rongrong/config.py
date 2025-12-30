"""Project Rongrong 配置"""
from dataclasses import dataclass

@dataclass
class VLLMConfig:
    """vLLM 模型配置"""
    # Stage 1: Filter (Non-thinking)
    filter_url: str = "http://localhost:8003/v1/chat/completions"
    filter_model: str = "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"

    # Stage 2+3: Agents (Thinking + VL)
    agent_url: str = "http://localhost:8000/v1/chat/completions"
    agent_model: str = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

@dataclass
class MongoConfig:
    """MongoDB 配置"""
    uri: str = "mongodb://localhost:27017"
    database: str = "vulcan_brain"

    # Collections
    emails_collection: str = "wecom_emails"
    reports_collection: str = "wecom_daily_reports"
    pipeline_collection: str = "wecom_report_pipeline"

@dataclass
class PipelineConfig:
    """Pipeline 配置"""
    batch_size: int = 30
    max_emails: int = 500
    timeout: int = 120

# 分类定义
CATEGORIES = [
    "CUSTOMER",      # 创收流
    "SUPPLY_CHAIN",  # 交付流
    "LOGISTICS",     # 物流流
    "MANAGEMENT",    # 决策流
    "ADMIN",         # 行政流
    "FILE",          # 文件流
    "FILTER",        # 过滤流
]

# 需要 VLM 的 Agent
VLM_AGENTS = ["ADMIN", "FILE"]

# 默认配置实例
vllm_config = VLLMConfig()
mongo_config = MongoConfig()
pipeline_config = PipelineConfig()
