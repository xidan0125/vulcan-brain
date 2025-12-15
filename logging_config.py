"""
Vulcan Brain 统一日志配置
提供结构化日志、级别控制、文件轮转
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Optional

# 日志目录
LOG_DIR = Path.home() / "vulcan-brain" / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志格式
DETAILED_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
SIMPLE_FORMAT = "%(levelname)s: %(message)s"
JSON_FORMAT = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'

# 颜色支持 (终端)
COLORS = {
    'DEBUG': '\033[36m',     # Cyan
    'INFO': '\033[32m',      # Green
    'WARNING': '\033[33m',   # Yellow
    'ERROR': '\033[31m',     # Red
    'CRITICAL': '\033[35m',  # Magenta
    'RESET': '\033[0m'
}


class ColoredFormatter(logging.Formatter):
    """带颜色的终端日志格式"""
    
    def format(self, record):
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            color = COLORS.get(record.levelname, COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{COLORS['RESET']}"
        return super().format(record)


class ContextFilter(logging.Filter):
    """添加上下文信息的过滤器"""
    
    def __init__(self, default_context: dict = None):
        super().__init__()
        self.default_context = default_context or {}
    
    def filter(self, record):
        # 添加默认上下文
        for key, value in self.default_context.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


def get_logger(
    name: str,
    level: int = None,
    log_file: str = None,
    add_console: bool = True
) -> logging.Logger:
    """
    获取配置好的 logger
    
    Args:
        name: logger 名称（通常用 __name__）
        level: 日志级别，默认从环境变量读取
        log_file: 日志文件名（可选）
        add_console: 是否输出到控制台
    
    Returns:
        配置好的 logger 实例
    """
    # 确定日志级别
    if level is None:
        env_level = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)
    
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    logger.propagate = False
    
    # 控制台 handler
    if add_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(ColoredFormatter(DETAILED_FORMAT))
        logger.addHandler(console_handler)
    
    # 文件 handler（带轮转）
    if log_file:
        file_path = LOG_DIR / log_file
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
        logger.addHandler(file_handler)
    
    return logger


def get_api_logger() -> logging.Logger:
    """获取 API 专用 logger"""
    return get_logger("api", log_file="api.log")


def get_kernel_logger() -> logging.Logger:
    """获取 AI 内核专用 logger"""
    return get_logger("kernel", log_file="kernel.log")


def get_feishu_logger() -> logging.Logger:
    """获取飞书 API 专用 logger"""
    return get_logger("feishu", log_file="feishu.log")


def log_exception(logger: logging.Logger, exc: Exception, context: str = ""):
    """
    统一的异常日志记录
    
    Args:
        logger: logger 实例
        exc: 异常对象
        context: 额外上下文信息
    """
    import traceback
    
    exc_type = type(exc).__name__
    exc_msg = str(exc)
    exc_tb = traceback.format_exc()
    
    logger.error(
        f"{context} | {exc_type}: {exc_msg}\n"
        f"Traceback:\n{exc_tb}"
    )


# === 请求日志辅助函数 ===
def log_request(logger: logging.Logger, method: str, path: str, 
                user: str = "anonymous", status: int = None, 
                duration_ms: float = None, extra: dict = None):
    """
    统一的请求日志格式
    
    Args:
        logger: logger 实例
        method: HTTP 方法
        path: 请求路径
        user: 用户标识
        status: 响应状态码
        duration_ms: 请求耗时（毫秒）
        extra: 额外信息
    """
    parts = [f"{method} {path}", f"user={user}"]
    
    if status:
        parts.append(f"status={status}")
    if duration_ms is not None:
        parts.append(f"{duration_ms:.2f}ms")
    if extra:
        for k, v in extra.items():
            parts.append(f"{k}={v}")
    
    msg = " | ".join(parts)
    
    if status and status >= 500:
        logger.error(msg)
    elif status and status >= 400:
        logger.warning(msg)
    else:
        logger.info(msg)


# === 初始化默认 logger ===
# 在模块导入时设置根 logger
logging.basicConfig(
    level=logging.INFO,
    format=DETAILED_FORMAT,
    handlers=[logging.StreamHandler(sys.stderr)]
)

# 降低第三方库的日志级别
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


if __name__ == "__main__":
    # 测试日志
    logger = get_logger("test", level=logging.DEBUG)
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    
    # 测试请求日志
    api_logger = get_api_logger()
    log_request(api_logger, "GET", "/api/test", "user123", 200, 15.5)
    log_request(api_logger, "POST", "/api/error", "user456", 500, 100.0)
