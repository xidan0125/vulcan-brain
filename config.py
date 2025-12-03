# Vulcan Brain V4 - Configuration File
# ============================================
# 统一管理配置，从环境变量读取

import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# === JWT Authentication ===
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-fallback-secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 7天

if JWT_SECRET == "dev-only-fallback-secret":
    print("[WARNING] Using fallback JWT_SECRET! Set JWT_SECRET env var in production!")

# === LLM Configuration ===
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen3:30b-a3b")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_API_URL = os.getenv("LLM_API_URL", f"{LLM_BASE_URL}/api/generate")
LLM_PREDICTION_MODEL = os.getenv("LLM_PREDICTION_MODEL", "qwen2.5:7b")

# === Database ===
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "vulcan_brain")

# === Feishu Configuration ===
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BRAIN_APP_ID = os.getenv("FEISHU_BRAIN_APP_ID", "")
FEISHU_BRAIN_APP_SECRET = os.getenv("FEISHU_BRAIN_APP_SECRET", "")
FEISHU_BASE_URL = "https://open.larksuite.com/open-apis"

if not FEISHU_APP_SECRET:
    print("[WARNING] FEISHU_APP_SECRET not set!")
if not FEISHU_BRAIN_APP_SECRET:
    print("[WARNING] FEISHU_BRAIN_APP_SECRET not set!")

# === System Parameters ===
SYSTEM_TEMPERATURE = float(os.getenv("SYSTEM_TEMPERATURE", "0.1"))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "20"))

# === Tool Configuration ===
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "3"))

# === Monitor Configuration ===
GPU_CACHE_TTL = float(os.getenv("GPU_CACHE_TTL", "1.0"))
MONITOR_UPDATE_INTERVAL = int(os.getenv("MONITOR_UPDATE_INTERVAL", "2000"))

# === Server Configuration ===
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8001"))

# === 启动检查 ===
if __name__ == "__main__":
    print("=== Vulcan Brain Configuration ===")
    print(f"LLM_MODEL_NAME: {LLM_MODEL_NAME}")
    print(f"LLM_BASE_URL: {LLM_BASE_URL}")
    print(f"MONGO_URI: {MONGO_URI}")
    print(f"SERVER_PORT: {SERVER_PORT}")
    print(f"JWT configured: {JWT_SECRET != dev-only-fallback-secret}")
    print(f"Feishu configured: {bool(FEISHU_APP_SECRET)}")
