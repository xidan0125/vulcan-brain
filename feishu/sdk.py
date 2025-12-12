"""
Vulcan Brain 飞书 SDK 封装
统一管理飞书 API 调用、Token 缓存、错误处理
"""

import os
import time
import json
import logging
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger("FeishuSDK")

# ==================== 配置 ====================
FEISHU_BASE_URL = "https://open.larksuite.com/open-apis"

# PMO Bot (项目管理)
FEISHU_PMO_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_PMO_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

# Brain Bot (综合助手)
FEISHU_BRAIN_APP_ID = os.getenv("FEISHU_BRAIN_APP_ID", "")
FEISHU_BRAIN_APP_SECRET = os.getenv("FEISHU_BRAIN_APP_SECRET", "")


class FeishuSDK:
    """
    飞书 SDK 封装 - 单例模式

    支持两个机器人:
    - PMO Bot: 项目管理专用
    - Brain Bot: 综合助手 (有通讯录权限)
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Token 缓存
        self._pmo_token: Optional[str] = None
        self._pmo_token_expires: float = 0
        self._brain_token: Optional[str] = None
        self._brain_token_expires: float = 0

        self._initialized = True
        logger.info("[FeishuSDK] 初始化完成")

    # ==================== Token 管理 ====================

    async def get_pmo_token(self) -> str:
        """获取 PMO Bot 的 tenant_access_token"""
        if self._pmo_token and time.time() < self._pmo_token_expires:
            return self._pmo_token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": FEISHU_PMO_APP_ID,
                    "app_secret": FEISHU_PMO_APP_SECRET
                }
            )
            data = resp.json()

            if data.get("code") != 0:
                logger.error(f"[FeishuSDK] PMO Token 获取失败: {data}")
                raise Exception(f"获取 PMO Token 失败: {data}")

            self._pmo_token = data["tenant_access_token"]
            self._pmo_token_expires = time.time() + data["expire"] - 60
            logger.info(f"[FeishuSDK] PMO Token 刷新成功")
            return self._pmo_token

    async def get_brain_token(self) -> str:
        """获取 Brain Bot 的 tenant_access_token (有通讯录权限)"""
        if self._brain_token and time.time() < self._brain_token_expires:
            return self._brain_token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": FEISHU_BRAIN_APP_ID,
                    "app_secret": FEISHU_BRAIN_APP_SECRET
                }
            )
            data = resp.json()

            if data.get("code") != 0:
                logger.error(f"[FeishuSDK] Brain Token 获取失败: {data}")
                raise Exception(f"获取 Brain Token 失败: {data}")

            self._brain_token = data["tenant_access_token"]
            self._brain_token_expires = time.time() + data["expire"] - 60
            logger.info(f"[FeishuSDK] Brain Token 刷新成功")
            return self._brain_token

    # ==================== 消息发送 ====================

    async def send_card(
        self,
        open_id: str,
        card: Dict[str, Any],
        bot: str = "brain"
    ) -> Dict[str, Any]:
        """
        发送卡片消息给用户

        Args:
            open_id: 用户的 open_id
            card: 卡片内容 (dict)
            bot: 使用哪个机器人 ("pmo" 或 "brain")

        Returns:
            飞书 API 响应
        """
        token = await self.get_brain_token() if bot == "brain" else await self.get_pmo_token()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/im/v1/messages",
                params={"receive_id_type": "open_id"},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": open_id,
                    "msg_type": "interactive",
                    "content": json.dumps(card)
                }
            )
            result = resp.json()

            if result.get("code") == 0:
                logger.info(f"[FeishuSDK] 卡片发送成功: {open_id}")
            else:
                logger.error(f"[FeishuSDK] 卡片发送失败: {result}")

            return result

    async def send_text(
        self,
        open_id: str,
        text: str,
        bot: str = "brain"
    ) -> Dict[str, Any]:
        """
        发送文本消息给用户

        Args:
            open_id: 用户的 open_id
            text: 文本内容
            bot: 使用哪个机器人

        Returns:
            飞书 API 响应
        """
        token = await self.get_brain_token() if bot == "brain" else await self.get_pmo_token()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/im/v1/messages",
                params={"receive_id_type": "open_id"},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": open_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text})
                }
            )
            result = resp.json()

            if result.get("code") == 0:
                logger.info(f"[FeishuSDK] 文本发送成功: {open_id}")
            else:
                logger.error(f"[FeishuSDK] 文本发送失败: {result}")

            return result

    async def send_to_chat(
        self,
        chat_id: str,
        card: Dict[str, Any] = None,
        text: str = None,
        bot: str = "brain"
    ) -> Dict[str, Any]:
        """
        发送消息到群聊

        Args:
            chat_id: 群聊 ID
            card: 卡片内容 (可选)
            text: 文本内容 (可选)
            bot: 使用哪个机器人

        Returns:
            飞书 API 响应
        """
        token = await self.get_brain_token() if bot == "brain" else await self.get_pmo_token()

        if card:
            msg_type = "interactive"
            content = json.dumps(card)
        else:
            msg_type = "text"
            content = json.dumps({"text": text or ""})

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": chat_id,
                    "msg_type": msg_type,
                    "content": content
                }
            )
            return resp.json()

    async def send_card_to_chat(
        self,
        chat_id: str,
        card: Dict[str, Any],
        bot: str = "brain"
    ) -> Dict[str, Any]:
        """
        发送卡片到群聊

        Args:
            chat_id: 群聊 ID
            card: 卡片内容
            bot: 使用哪个机器人

        Returns:
            飞书 API 响应
        """
        return await self.send_to_chat(chat_id, card=card, bot=bot)

    async def reply_message(
        self,
        message_id: str,
        text: str,
        bot: str = "brain"
    ) -> Dict[str, Any]:
        """
        回复消息

        Args:
            message_id: 要回复的消息 ID
            text: 回复文本
            bot: 使用哪个机器人

        Returns:
            飞书 API 响应
        """
        token = await self.get_brain_token() if bot == "brain" else await self.get_pmo_token()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/im/v1/messages/{message_id}/reply",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "msg_type": "text",
                    "content": json.dumps({"text": text})
                }
            )
            result = resp.json()

            if result.get("code") == 0:
                logger.info(f"[FeishuSDK] 回复发送成功: {message_id}")
            else:
                logger.error(f"[FeishuSDK] 回复发送失败: {result}")

            return result

    async def reply_card(
        self,
        message_id: str,
        card: Dict[str, Any],
        bot: str = "brain"
    ) -> Dict[str, Any]:
        """
        回复卡片消息

        Args:
            message_id: 要回复的消息 ID
            card: 卡片内容
            bot: 使用哪个机器人

        Returns:
            飞书 API 响应
        """
        token = await self.get_brain_token() if bot == "brain" else await self.get_pmo_token()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/im/v1/messages/{message_id}/reply",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "msg_type": "interactive",
                    "content": json.dumps(card)
                }
            )
            return resp.json()

    # ==================== 用户信息 ====================

    async def get_user_info(self, open_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户信息

        Args:
            open_id: 用户的 open_id

        Returns:
            用户信息 dict 或 None
        """
        token = await self.get_brain_token()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{FEISHU_BASE_URL}/contact/v3/users/{open_id}",
                params={"user_id_type": "open_id"},
                headers={"Authorization": f"Bearer {token}"}
            )
            data = resp.json()

            if data.get("code") == 0:
                return data.get("data", {}).get("user")
            else:
                logger.error(f"[FeishuSDK] 获取用户信息失败: {data}")
                return None

    async def get_user_name(self, open_id: str) -> str:
        """获取用户名称，失败返回默认名称"""
        user = await self.get_user_info(open_id)
        if user:
            return user.get("name", f"用户_{open_id[-6:]}")
        return f"用户_{open_id[-6:]}"

    # ==================== 通讯录 ====================

    async def list_department_users(self, department_id: str = "0") -> List[Dict]:
        """
        获取部门下的用户列表

        Args:
            department_id: 部门 ID，"0" 表示根部门

        Returns:
            用户列表
        """
        token = await self.get_brain_token()
        users = []
        page_token = None

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                params = {
                    "department_id": department_id,
                    "user_id_type": "open_id",
                    "page_size": 50
                }
                if page_token:
                    params["page_token"] = page_token

                resp = await client.get(
                    f"{FEISHU_BASE_URL}/contact/v3/users",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"}
                )
                data = resp.json()

                if data.get("code") != 0:
                    logger.error(f"[FeishuSDK] 获取用户列表失败: {data}")
                    break

                items = data.get("data", {}).get("items", [])
                users.extend(items)

                if not data.get("data", {}).get("has_more"):
                    break
                page_token = data.get("data", {}).get("page_token")

        return users

    # ==================== 卡片更新 ====================

    async def update_card(
        self,
        message_id: str,
        card: Dict[str, Any],
        bot: str = "brain"
    ) -> Dict[str, Any]:
        """
        更新已发送的卡片

        Args:
            message_id: 消息 ID
            card: 新的卡片内容
            bot: 使用哪个机器人

        Returns:
            飞书 API 响应
        """
        token = await self.get_brain_token() if bot == "brain" else await self.get_pmo_token()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{FEISHU_BASE_URL}/im/v1/messages/{message_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "msg_type": "interactive",
                    "content": json.dumps(card)
                }
            )
            return resp.json()


# ==================== 单例获取 ====================

_sdk_instance: Optional[FeishuSDK] = None

def get_feishu_sdk() -> FeishuSDK:
    """获取 FeishuSDK 单例"""
    global _sdk_instance
    if _sdk_instance is None:
        _sdk_instance = FeishuSDK()
    return _sdk_instance
