"""
InfoHub API 模块
五维度信息中心 API

模块结构:
- daily.py     日报相关
- chat.py      聊天相关
- email.py     邮件相关
- people.py    人员相关
- approval.py  审批相关
"""

from fastapi import APIRouter
from .daily import router as daily_router
from .chat import router as chat_router
from .email import router as email_router
from .people import router as people_router
from .approval import router as approval_router

# 主路由
router = APIRouter(prefix="/info-hub", tags=["InfoHub"])

# 注册子路由
router.include_router(daily_router)
router.include_router(chat_router)
router.include_router(email_router)
router.include_router(people_router)
router.include_router(approval_router)

__all__ = ["router"]
