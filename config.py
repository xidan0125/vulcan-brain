# Vulcan Brain V4 - Configuration File
# ============================================
# 向后兼容层：从 settings.py 获取配置，同时保持原有接口

import os
import sys

# 尝试使用新配置系统
try:
    from settings import get_settings, print_config_summary
    _settings = get_settings()
    _USE_NEW_SETTINGS = True
except Exception as e:
    print(f"[WARNING] 新配置系统加载失败，回退到旧模式: {e}")
    _USE_NEW_SETTINGS = False
    from dotenv import load_dotenv
    load_dotenv()

# === JWT Authentication ===
if _USE_NEW_SETTINGS:
    JWT_SECRET = _settings.jwt_secret
    JWT_ALGORITHM = _settings.jwt_algorithm
    JWT_EXPIRE_HOURS = _settings.jwt_expire_hours
else:
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-fallback-secret")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_HOURS = 24 * 7

if JWT_SECRET == "dev-only-fallback-secret":
    print("[WARNING] Using fallback JWT_SECRET! Set JWT_SECRET env var in production!")

# === LLM Configuration ===
# vLLM 配置 (替代 Ollama)
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")

def _get_vllm_model():
    import httpx
    try:
        resp = httpx.get(f"{VLLM_BASE_URL}/v1/models", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            if models:
                return models[0]["id"]
    except:
        pass
    return "default-model"

# 兼容旧变量名 (逐步废弃)
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "auto")  # auto = 从 vLLM 获取
LLM_BASE_URL = VLLM_BASE_URL  # 指向 vLLM
LLM_API_URL = f"{VLLM_BASE_URL}/v1/chat/completions"
LLM_PREDICTION_MODEL = os.getenv("LLM_PREDICTION_MODEL", "qwen2.5:7b")

# === Database ===
if _USE_NEW_SETTINGS:
    MONGO_URI = _settings.mongo_uri
    MONGO_DB_NAME = _settings.mongo_db_name
else:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "vulcan_brain")

# === Feishu Configuration ===
if _USE_NEW_SETTINGS:
    FEISHU_APP_ID = _settings.feishu_app_id or ""
    FEISHU_APP_SECRET = _settings.feishu_app_secret or ""
else:
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
if _USE_NEW_SETTINGS:
    SERVER_HOST = _settings.api_host
    SERVER_PORT = _settings.api_port
    CORS_ORIGINS = _settings.get_cors_origins_list()
else:
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8001"))
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,https://vsg-brain.com").split(",")

# === 导出新配置系统接口（可选使用）===
def get_new_settings():
    """获取新配置系统实例"""
    if _USE_NEW_SETTINGS:
        return _settings
    raise RuntimeError("新配置系统未启用")

# === 启动检查 ===
if __name__ == "__main__":
    print("=== Vulcan Brain Configuration ===")
    print(f"使用新配置系统: {_USE_NEW_SETTINGS}")
    print(f"LLM_MODEL_NAME: {LLM_MODEL_NAME}")
    print(f"LLM_BASE_URL: {LLM_BASE_URL}")
    print(f"MONGO_URI: {MONGO_URI}")
    print(f"SERVER_PORT: {SERVER_PORT}")
    print(f"CORS_ORIGINS: {CORS_ORIGINS}")
    print(f"JWT configured: {JWT_SECRET != 'dev-only-fallback-secret'}")
    print(f"Feishu configured: {bool(FEISHU_APP_SECRET)}")
    
    if _USE_NEW_SETTINGS:
        print_config_summary(_settings)
