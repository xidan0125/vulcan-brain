"""
Vulcan Brain - 统一异常处理
业务异常定义、FastAPI 异常处理器
"""
from typing import Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import os


# === 业务异常基类 ===
class VulcanException(Exception):
    """Vulcan Brain 业务异常基类"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Dict[str, Any] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


# === 具体业务异常 ===
class AuthenticationError(VulcanException):
    """认证失败 (401)"""
    def __init__(self, message: str = "Authentication failed", details: dict = None):
        super().__init__(message, "AUTH_FAILED", 401, details)


class AuthorizationError(VulcanException):
    """授权失败 (403)"""
    def __init__(self, message: str = "Access denied", details: dict = None):
        super().__init__(message, "ACCESS_DENIED", 403, details)


class NotFoundError(VulcanException):
    """资源不存在 (404)"""
    def __init__(self, resource: str = "Resource", resource_id: str = None):
        details = {"resource": resource}
        if resource_id:
            details["id"] = resource_id
        super().__init__(f"{resource} not found", "NOT_FOUND", 404, details)


class ValidationError(VulcanException):
    """参数验证失败 (422)"""
    def __init__(self, message: str, field: str = None):
        details = {"field": field} if field else {}
        super().__init__(message, "VALIDATION_ERROR", 422, details)


class ConflictError(VulcanException):
    """资源冲突 (409)"""
    def __init__(self, message: str = "Resource conflict", details: dict = None):
        super().__init__(message, "CONFLICT", 409, details)


class RateLimitError(VulcanException):
    """请求频率限制 (429)"""
    def __init__(self, message: str = "Too many requests", retry_after: int = 60):
        super().__init__(message, "RATE_LIMIT", 429, {"retry_after": retry_after})


class ExternalServiceError(VulcanException):
    """外部服务调用失败 (502)"""
    def __init__(self, service: str, message: str = "External service error"):
        super().__init__(message, "EXTERNAL_ERROR", 502, {"service": service})


class DatabaseError(VulcanException):
    """数据库操作失败 (500)"""
    def __init__(self, message: str = "Database operation failed", operation: str = None):
        details = {"operation": operation} if operation else {}
        super().__init__(message, "DATABASE_ERROR", 500, details)


class AIModelError(VulcanException):
    """AI 模型调用失败 (500)"""
    def __init__(self, model: str, message: str = "AI model error"):
        super().__init__(message, "AI_MODEL_ERROR", 500, {"model": model})


# === FastAPI 异常处理器 ===
def _get_logger():
    """延迟导入避免循环依赖"""
    from vulcan_libs.logger import api_logger, log_error
    return api_logger, log_error


async def vulcan_exception_handler(request: Request, exc: VulcanException) -> JSONResponse:
    """处理 VulcanException"""
    api_logger, log_error = _get_logger()
    log_error(exc, f"{request.method} {request.url.path}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """处理标准 HTTPException"""
    api_logger, _ = _get_logger()
    api_logger.warning(f"{request.method} {request.url.path} | HTTP {exc.status_code}: {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_code": "HTTP_ERROR",
            "message": str(exc.detail),
            "details": {}
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理未捕获的异常"""
    api_logger, log_error = _get_logger()
    log_error(exc, f"UNHANDLED {request.method} {request.url.path}")
    
    # 生产环境不暴露内部错误详情
    is_debug = os.getenv("APP_ENV", "development") != "production"
    
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_code": "INTERNAL_ERROR",
            "message": str(exc) if is_debug else "Internal server error",
            "details": {"type": type(exc).__name__} if is_debug else {}
        }
    )


def register_exception_handlers(app):
    """
    注册所有异常处理器到 FastAPI app
    
    Usage:
        from vulcan_libs.exceptions import register_exception_handlers
        register_exception_handlers(app)
    """
    app.add_exception_handler(VulcanException, vulcan_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    
    api_logger, _ = _get_logger()
    api_logger.info("[Startup] Exception handlers registered")


# === 工具函数 ===
def safe_execute(func, *args, default=None, error_msg: str = None, **kwargs):
    """安全执行函数，捕获异常返回默认值"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if error_msg:
            api_logger, _ = _get_logger()
            api_logger.warning(f"{error_msg}: {type(e).__name__}: {e}")
        return default


async def async_safe_execute(coro, default=None, error_msg: str = None):
    """安全执行异步函数"""
    try:
        return await coro
    except Exception as e:
        if error_msg:
            api_logger, _ = _get_logger()
            api_logger.warning(f"{error_msg}: {type(e).__name__}: {e}")
        return default
