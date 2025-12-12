"""
Vulcan Brain 飞书统一网关
所有飞书事件的统一入口，根据事件类型路由到对应处理器
"""

import json
import logging
import hashlib
import base64
from typing import Dict, Any, Callable, Awaitable
from fastapi import APIRouter, Request, HTTPException

# AES 加密是可选的
try:
    from Crypto.Cipher import AES
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

logger = logging.getLogger("FeishuGateway")

router = APIRouter(prefix="/api/feishu", tags=["Feishu"])

# ==================== 事件处理器注册表 ====================

# 格式: {"action_type": handler_function}
# handler_function 签名: async def handler(event: Dict) -> Dict

CARD_ACTION_HANDLERS: Dict[str, Callable[[Dict], Awaitable[Dict]]] = {}
MENU_EVENT_HANDLERS: Dict[str, Callable[[Dict], Awaitable[Dict]]] = {}
MESSAGE_HANDLERS: Dict[str, Callable[[Dict], Awaitable[Dict]]] = {}


def register_card_action(action_type: str):
    """注册卡片动作处理器的装饰器"""
    def decorator(func: Callable[[Dict], Awaitable[Dict]]):
        CARD_ACTION_HANDLERS[action_type] = func
        logger.info(f"[Gateway] 注册卡片动作: {action_type}")
        return func
    return decorator


def register_menu_event(event_key: str):
    """注册菜单事件处理器的装饰器"""
    def decorator(func: Callable[[Dict], Awaitable[Dict]]):
        MENU_EVENT_HANDLERS[event_key] = func
        logger.info(f"[Gateway] 注册菜单事件: {event_key}")
        return func
    return decorator


def register_message_handler(msg_type: str):
    """注册消息处理器的装饰器"""
    def decorator(func: Callable[[Dict], Awaitable[Dict]]):
        MESSAGE_HANDLERS[msg_type] = func
        logger.info(f"[Gateway] 注册消息处理: {msg_type}")
        return func
    return decorator


# ==================== 初始化处理器 ====================

def init_handlers():
    """初始化所有处理器"""
    from feishu.handlers.task_handler import get_task_handler
    from feishu.handlers.approval_handler import get_approval_handler
    from feishu.handlers.menu_handler import get_menu_handler
    from feishu.handlers.message_handler import get_message_handler

    task = get_task_handler()
    approval = get_approval_handler()
    menu = get_menu_handler()
    message = get_message_handler()

    # ===== 任务卡片动作 =====
    CARD_ACTION_HANDLERS.update({
        # 任务分配响应
        "task_accept": task.handle_accept,
        "task_difficulty": task.handle_difficulty,
        "task_clarify": task.handle_clarify,
        # 任务进度
        "task_update_progress": task.handle_progress_update,
        "task_complete": task.handle_complete,
        "task_delay": task.handle_delay_request,
        "submit_task_status_update": task.handle_progress_update,
        # 告警卡片动作
        "send_task_reminder": task.handle_send_reminder,
        "view_overdue_tasks": task.handle_view_overdue_tasks,
        # 兼容旧版
        "assignment_response": task.handle_accept,
        "progress_update": task.handle_progress_update,
        "overdue_response": task.handle_accept,
    })

    # ===== 审批卡片动作 =====
    CARD_ACTION_HANDLERS.update({
        "approval_submit": approval.handle_submit,
        "approval_approve": approval.handle_approve,
        "approval_reject": approval.handle_reject,
        "approval_cancel": approval.handle_cancel,
        # 兼容旧版
        "bot_approval_submit": approval.handle_submit,
        "bot_approval_approve": approval.handle_approve,
        "bot_approval_reject": approval.handle_reject,
    })

    # ===== 菜单事件 (Brain Bot) =====
    MENU_EVENT_HANDLERS.update({
        "my_tasks": menu.show_my_tasks,
        "update_status": menu.show_update_status_form,
        "start_approval": menu.show_approval_form,
        "my_approvals": menu.show_my_approvals,
        "daily_report": menu.show_daily_report,
        "start_chat": menu.start_chat,
    })

    # ===== 卡片按钮刷新动作 =====
    CARD_ACTION_HANDLERS.update({
        "refresh_my_tasks": menu.refresh_my_tasks,
        "show_update_status_form": menu.show_update_status_form,
        "refresh_my_approvals": menu.refresh_my_approvals,
    })

    # ===== 消息处理器 =====
    MESSAGE_HANDLERS.update({
        "text": message.handle_text_message,
    })

    logger.info(f"[Gateway] 处理器初始化完成: "
                f"card_actions={len(CARD_ACTION_HANDLERS)}, "
                f"menu_events={len(MENU_EVENT_HANDLERS)}, "
                f"message_handlers={len(MESSAGE_HANDLERS)}")


# ==================== Webhook 端点 ====================

@router.post("/webhook/brain")
async def brain_webhook(request: Request):
    """
    Vulcan Brain 机器人 Webhook

    处理:
    - URL 验证
    - 卡片回调
    - 菜单事件
    - 消息事件
    """
    body = await request.json()

    # URL 验证
    if "challenge" in body:
        logger.info("[Gateway] Brain Bot URL 验证")
        return {"challenge": body["challenge"]}

    # 解密事件 (如果需要)
    event = decrypt_event(body) if body.get("encrypt") else body

    return await route_event(event, bot="brain")


@router.post("/webhook/pmo")
async def pmo_webhook(request: Request):
    """
    PMO Bot 机器人 Webhook

    主要处理项目管理相关事件
    """
    body = await request.json()

    # URL 验证
    if "challenge" in body:
        logger.info("[Gateway] PMO Bot URL 验证")
        return {"challenge": body["challenge"]}

    event = decrypt_event(body) if body.get("encrypt") else body

    return await route_event(event, bot="pmo")


@router.post("/webhook")
async def unified_webhook(request: Request):
    """
    统一 Webhook (兼容旧版)

    自动识别机器人类型并路由
    """
    body = await request.json()

    if "challenge" in body:
        return {"challenge": body["challenge"]}

    event = decrypt_event(body) if body.get("encrypt") else body

    # 尝试识别机器人
    header = event.get("header", {})
    app_id = header.get("app_id", "")

    # 根据 app_id 判断机器人类型
    import os
    brain_app_id = os.getenv("FEISHU_BRAIN_APP_ID", "")
    bot = "brain" if app_id == brain_app_id else "pmo"

    return await route_event(event, bot=bot)


# ==================== 事件路由 ====================

async def route_event(event: Dict[str, Any], bot: str = "brain") -> Dict:
    """
    路由事件到对应处理器

    Args:
        event: 飞书事件数据
        bot: 机器人类型 ("brain" 或 "pmo")

    Returns:
        处理结果
    """
    header = event.get("header", {})
    event_type = header.get("event_type", "")

    logger.info(f"[Gateway] 收到事件: type={event_type}, bot={bot}")

    # 1. 卡片回调事件
    if event_type == "card.action.trigger":
        return await handle_card_action(event)

    # 2. 机器人菜单事件
    if event_type == "application.bot.menu_v6":
        return await handle_menu_event(event)

    # 3. 消息事件
    if event_type == "im.message.receive_v1":
        return await handle_message_event(event, bot)

    # 4. 其他事件
    logger.info(f"[Gateway] 未处理的事件类型: {event_type}")
    return {"code": 0}


async def handle_card_action(event: Dict) -> Dict:
    """处理卡片动作事件"""
    event_data = event.get("event", {})
    action = event_data.get("action", {})
    value = action.get("value", {})

    # 获取 action_type
    action_type = ""
    if isinstance(value, dict):
        action_type = value.get("action", "")

    # 去除空格 (兼容飞书的奇怪行为)
    action_type = action_type.strip()

    # 检查 form_submit 模式
    if not action_type and action.get("name") == "submit_btn":
        # 从 form_value 中获取
        form_value = action.get("form_value", {})
        if "approval_type" in form_value:
            action_type = "bot_approval_submit"

    logger.info(f"[Gateway] 卡片动作: {action_type}")

    handler = CARD_ACTION_HANDLERS.get(action_type)
    if handler:
        return await handler(event_data)

    logger.warning(f"[Gateway] 未注册的卡片动作: {action_type}")
    return {"code": 0}


async def handle_menu_event(event: Dict) -> Dict:
    """处理菜单事件"""
    event_data = event.get("event", {})
    event_key = event_data.get("event_key", "").strip()

    logger.info(f"[Gateway] 菜单事件: {event_key}")

    handler = MENU_EVENT_HANDLERS.get(event_key)
    if handler:
        return await handler(event_data)

    logger.warning(f"[Gateway] 未注册的菜单事件: {event_key}")
    return {"code": 0}


async def handle_message_event(event: Dict, bot: str) -> Dict:
    """处理消息事件"""
    event_data = event.get("event", {})
    message = event_data.get("message", {})
    msg_type = message.get("message_type", "")
    chat_type = message.get("chat_type", "")

    logger.info(f"[Gateway] 消息事件: type={msg_type}, chat={chat_type}")

    handler = MESSAGE_HANDLERS.get(msg_type)
    if handler:
        return await handler(event_data, bot)

    # 默认忽略非文本消息
    logger.info(f"[Gateway] 未处理的消息类型: {msg_type}")
    return {"code": 0}


# ==================== 加密解密 ====================

def decrypt_event(body: Dict) -> Dict:
    """解密飞书加密事件"""
    if not HAS_CRYPTO:
        logger.warning("[Gateway] 未安装 pycryptodome，无法解密")
        return body

    import os
    encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "")

    if not encrypt_key:
        logger.warning("[Gateway] 未配置加密密钥，无法解密")
        return body

    try:
        encrypted = body.get("encrypt", "")
        cipher = AES.new(
            hashlib.sha256(encrypt_key.encode()).digest(),
            AES.MODE_CBC,
            encrypted[:16].encode()
        )
        decrypted = cipher.decrypt(base64.b64decode(encrypted))
        # 去除 PKCS7 padding
        pad_len = decrypted[-1]
        decrypted = decrypted[:-pad_len]
        return json.loads(decrypted.decode())
    except Exception as e:
        logger.error(f"[Gateway] 解密失败: {e}")
        return body


# ==================== 模块初始化 ====================

# 在模块导入时初始化处理器
try:
    init_handlers()
except Exception as e:
    logger.error(f"[Gateway] 初始化处理器失败: {e}")
