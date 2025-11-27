# Vulcan Brain V4 - Configuration File
# ============================================
# 统一管理配置，避免硬编码

# === LLM Configuration ===
LLM_MODEL_NAME = "qwen3-thinking"  # Ollama 模型名称（经过 curl /api/tags 确认）
LLM_BASE_URL = "http://localhost:11434"  # Ollama 服务地址

# === System Parameters ===
SYSTEM_TEMPERATURE = 0.1  # 推理温度（CodeAct 需要低温保证代码准确性）
MAX_ITERATIONS = 20  # 最大思考迭代次数

# === Tool Configuration ===
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"  # 工具检索用的 Embedding 模型
RETRIEVAL_TOP_K = 3  # 检索返回的相关包数量

# === Monitor Configuration ===
GPU_CACHE_TTL = 1.0  # GPU 监控数据缓存时间（秒）
MONITOR_UPDATE_INTERVAL = 2000  # 前端监控刷新间隔（毫秒）

# === Server Configuration ===
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
