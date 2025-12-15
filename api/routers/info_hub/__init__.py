"""
信息中心 API - 聚合所有子路由
"""

from fastapi import APIRouter
from .daily_router import router as daily_router
from .chat_router import router as chat_router  
from .people_router import router as people_router
from .approval_router import router as approval_router
from .misc_router import router as misc_router

# 主路由，聚合所有子路由
router = APIRouter(prefix="/info-hub", tags=["InfoHub"])

# 注册所有子路由
router.include_router(daily_router)
router.include_router(chat_router)
router.include_router(people_router)
router.include_router(approval_router)
router.include_router(misc_router)
