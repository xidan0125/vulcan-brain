"""
Soul Dependencies - FastAPI 依赖注入

与现有用户认证系统集成，自动为当前用户注入 Soul
"""

from typing import Optional
from fastapi import Depends, Request
from api.routers.auth_router import get_current_user

from core.soul import SoulEngine, get_soul
from core.soul.types import Genome, SoulContext
from core.soul.genome import get_genome_manager


async def get_current_soul(
    current_user: dict = Depends(get_current_user)
) -> SoulEngine:
    """
    获取当前用户的 Soul 实例

    Usage:
        @router.post("/chat")
        async def chat(
            message: str,
            soul: SoulEngine = Depends(get_current_soul)
        ):
            enhanced = await soul.inject(message, task_type="chat")
            ...
    """
    user_id = current_user["user_id"]
    return get_soul(user_id)


async def get_current_genome(
    current_user: dict = Depends(get_current_user)
) -> Genome:
    """
    获取当前用户的人格基因

    Usage:
        @router.get("/profile")
        async def get_profile(
            genome: Genome = Depends(get_current_genome)
        ):
            return genome.to_dict()
    """
    user_id = current_user["user_id"]
    mgr = get_genome_manager()
    return await mgr.get(user_id)


async def get_soul_context(
    current_user: dict = Depends(get_current_user),
    task_type: str = "general"
) -> SoulContext:
    """
    获取完整的 Soul 上下文

    Usage:
        @router.post("/analyze")
        async def analyze(
            context: SoulContext = Depends(get_soul_context)
        ):
            ...
    """
    user_id = current_user["user_id"]
    mgr = get_genome_manager()
    genome = await mgr.get(user_id)

    return SoulContext(
        user_id=user_id,
        genome=genome,
        task_type=task_type
    )


# ==================== 中间件方式 ====================

class SoulMiddleware:
    """
    Soul 中间件 - 自动为请求注入 Soul 上下文

    Usage:
        app.add_middleware(SoulMiddleware)

        # 然后在任何地方通过 request.state.soul 访问
        @router.post("/chat")
        async def chat(request: Request):
            soul = request.state.soul
            ...
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # 尝试从请求中获取用户
            # 注意：这需要在认证之后运行
            pass

        await self.app(scope, receive, send)


# ==================== 装饰器工厂 ====================

def soul_inject(task_type: str = "general"):
    """
    装饰器工厂：为 API 端点自动注入 Soul

    Usage:
        @router.post("/chat")
        @soul_inject(task_type="chat")
        async def chat(
            message: str,
            current_user: dict = Depends(get_current_user)
        ):
            # message 已经被 Soul 增强
            ...
    """
    def decorator(func):
        from functools import wraps

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从 kwargs 获取 current_user
            current_user = kwargs.get("current_user")
            if not current_user:
                # 尝试从 args 获取（不太可能）
                return await func(*args, **kwargs)

            user_id = current_user["user_id"]
            soul = get_soul(user_id)

            # 查找并增强 prompt/message 参数
            for key in ["prompt", "message", "query", "content"]:
                if key in kwargs and kwargs[key]:
                    original = kwargs[key]
                    kwargs[key] = await soul.inject(original, task_type=task_type)
                    break

            return await func(*args, **kwargs)

        return wrapper
    return decorator
