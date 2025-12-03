"""
Vulcan Brain - 结构化日志系统
统一的日志配置，支持文件+控制台输出
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# 确保日志目录存在
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    获取结构化日志记录器
    
    Args:
        name: 日志名称（通常是模块名）
        level: 日志级别
        
    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 日志格式
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件输出（按日期轮转，最大10MB，保留30个）
    log_file = os.path.join(LOG_DIR, f"{name}.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


# 预定义的日志器
api_logger = get_logger("api")
auth_logger = get_logger("auth")
kernel_logger = get_logger("kernel")
db_logger = get_logger("database")


def log_request(method: str, path: str, user: str = "anonymous", status: int = 200, duration_ms: float = 0):
    """记录API请求"""
    api_logger.info(f"{method} {path} | user={user} | status={status} | {duration_ms:.2f}ms")


def log_error(error: Exception, context: str = ""):
    """记录错误"""
    api_logger.error(f"[ERROR] {context} | {type(error).__name__}: {str(error)}")
