"""
Vulcan Brain 飞书集成模块

统一管理飞书相关功能:
- sdk: 飞书 API 封装
- gateway: 统一事件网关
- handlers: 事件处理器
- cards: 卡片模板
- scheduler: 定时任务调度器
- notification: 统一通知服务
"""

from .sdk import get_feishu_sdk, FeishuSDK
from .gateway import router as feishu_router
from .scheduler import get_feishu_scheduler, start_scheduler, stop_scheduler
from .notification import get_notification_service, NotificationService

__all__ = [
    # SDK
    "get_feishu_sdk",
    "FeishuSDK",
    # Gateway
    "feishu_router",
    # Scheduler
    "get_feishu_scheduler",
    "start_scheduler",
    "stop_scheduler",
    # Notification
    "get_notification_service",
    "NotificationService",
]
