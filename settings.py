"""
Vulcan Brain 配置管理系统
使用 Pydantic BaseSettings，支持环境变量和 .env 文件
"""
import sys
import os
from typing import Optional, List
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, validator

class Settings(BaseSettings):
    """应用配置 - 所有敏感信息从环境变量/.env 读取"""
    
    # === 基础配置 ===
    app_name: str = "Vulcan Brain"
    app_env: str = Field(default="development", description="development/staging/production")
    debug: bool = Field(default=True)
    
    # === 安全配置 (必需) ===
    jwt_secret: str = Field(..., description="JWT 签名密钥，必须设置")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_hours: int = Field(default=24)
    
    # === 数据库 ===
    mongo_uri: str = Field(default="mongodb://localhost:27017", description="MongoDB 连接 URI")
    mongo_db_name: str = Field(default="vulcan_brain")
    postgres_uri: Optional[str] = Field(default=None, description="PostgreSQL 连接 URI (可选)")
    
    # === API 服务 ===
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8001)
    cors_origins: str = Field(
        default="http://localhost:3000,https://vsg-brain.com",
        description="允许的 CORS 源，逗号分隔"
    )
    
    # === 飞书配置 ===
    feishu_app_id: Optional[str] = Field(default=None)
    feishu_app_secret: Optional[str] = Field(default=None)
    feishu_encrypt_key: Optional[str] = Field(default=None)
    feishu_verification_token: Optional[str] = Field(default=None)
    
    # === Acontext 配置 ===
    acontext_api_url: str = Field(default="http://localhost:8029")
    acontext_core_url: str = Field(default="http://localhost:8019")
    acontext_bearer_token: Optional[str] = Field(default=None)
    
    # === AI 模型配置 ===
    vllm_base_url: str = Field(default="http://localhost:8000")
    vllm_model: str = Field(default="auto")  # auto = 从 vLLM 获取
    gemini_api_key: Optional[str] = Field(default=None)
    
    @validator("cors_origins")
    def parse_cors_origins(cls, v):
        """确保 CORS origins 格式正确"""
        return v.strip()
    
    def get_cors_origins_list(self) -> List[str]:
        """获取 CORS origins 列表"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    def is_production(self) -> bool:
        return self.app_env == "production"
    
    def is_development(self) -> bool:
        return self.app_env == "development"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # 允许额外环境变量  # 环境变量不区分大小写

@lru_cache()
def get_settings() -> Settings:
    """
    获取配置实例（缓存）
    启动时会验证必需配置，失败则退出
    """
    try:
        settings = Settings()
        return settings
    except Exception as e:
        print(f"\n❌ 配置错误: {e}")
        print("\n请检查 .env 文件或环境变量是否正确设置。")
        print("参考 .env.example 获取配置模板。\n")
        sys.exit(1)

def print_config_summary(settings: Settings):
    """打印配置摘要（脱敏）"""
    def mask(value: Optional[str], show_chars: int = 4) -> str:
        if not value:
            return "<未设置>"
        if len(value) <= show_chars * 2:
            return "***"
        return f"{value[:show_chars]}...{value[-show_chars:]}"
    
    print("\n" + "="*50)
    print("  Vulcan Brain 配置摘要")
    print("="*50)
    print(f"  环境: {settings.app_env}")
    print(f"  Debug: {settings.debug}")
    print(f"  API: {settings.api_host}:{settings.api_port}")
    print(f"  CORS: {settings.cors_origins[:50]}...")
    print(f"  MongoDB: {mask(settings.mongo_uri, 10)}")
    print(f"  JWT Secret: {mask(settings.jwt_secret)}")
    print(f"  飞书 App: {mask(settings.feishu_app_id)}")
    print(f"  Gemini Key: {mask(settings.gemini_api_key)}")
    print("="*50 + "\n")

# 模块级别的配置实例
# 注意：首次导入时会触发配置验证
# settings = get_settings()  # 暂时注释，渐进迁移时启用

if __name__ == "__main__":
    # 测试配置加载
    s = get_settings()
    print_config_summary(s)

# ===== 日报配置 =====
# 日报时间边界 (24小时制)
# 默认7点：每天7:00生成前一天7:00到今天7:00的日报
DAILY_REPORT_HOUR: int = 7

# 时区 (用于日报生成)
TIMEZONE_OFFSET: int = 8  # UTC+8 (新加坡/中国)
