"""
Vulcan Brain - Feishu Client (共享客户端)
从 feishu_tools.py 提取，供所有飞书工具复用
"""

import os
import time
import json
from typing import Optional, Dict, Any, List
import httpx

# ==================== 配置 ====================
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "cli_a9a255eeb278de1a")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BASE_URL = "https://open.larksuite.com/open-apis"


class FeishuClient:
    """飞书 API 客户端 - 单例模式"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._token: Optional[str] = None
        self._token_expires: float = 0
        self._users_cache: Optional[List[Dict]] = None
        self._users_cache_time: float = 0
        self._initialized = True

    async def get_token(self) -> str:
        """获取 tenant_access_token (带缓存)"""
        if self._token and time.time() < self._token_expires:
            return self._token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": FEISHU_APP_ID,
                    "app_secret": FEISHU_APP_SECRET
                }
            )
            data = resp.json()

            if data.get("code") != 0:
                raise Exception(f"获取飞书 token 失败: {data}")

            self._token = data["tenant_access_token"]
            self._token_expires = time.time() + data["expire"] - 60
            return self._token

    async def send_message(
        self,
        receive_id: str,
        receive_id_type: str = "open_id",
        msg_type: str = "text",
        content: str = "",
        card: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """发送消息到飞书"""
        token = await self.get_token()

        if card:
            actual_msg_type = "interactive"
            actual_content = json.dumps(card)
        else:
            actual_msg_type = msg_type
            if msg_type == "text":
                actual_content = json.dumps({"text": content})
            else:
                actual_content = content

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/im/v1/messages",
                params={"receive_id_type": receive_id_type},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": receive_id,
                    "msg_type": actual_msg_type,
                    "content": actual_content
                }
            )
            return resp.json()

    async def get_all_visible_users(self, force_refresh: bool = False) -> List[Dict]:
        """
        获取机器人可见范围内的所有用户 (带缓存，5分钟)
        
        Returns:
            用户列表，每个用户包含: open_id, name, email, mobile, department_ids
        """
        # 检查缓存 (5分钟有效)
        cache_ttl = 300
        if not force_refresh and self._users_cache and time.time() - self._users_cache_time < cache_ttl:
            return self._users_cache
        
        token = await self.get_token()
        users = []

        async with httpx.AsyncClient() as client:
            # 1. 获取机器人可见的用户ID列表
            resp = await client.get(
                f"{FEISHU_BASE_URL}/contact/v3/scopes",
                headers={"Authorization": f"Bearer {token}"}
            )
            scopes = resp.json()
            
            if scopes.get("code") != 0:
                raise Exception(f"获取可见范围失败: {scopes}")
            
            user_ids = scopes.get("data", {}).get("user_ids", [])
            
            # 2. 获取每个用户详情
            for user_id in user_ids:
                resp = await client.get(
                    f"{FEISHU_BASE_URL}/contact/v3/users/{user_id}",
                    params={"user_id_type": "open_id"},
                    headers={"Authorization": f"Bearer {token}"}
                )
                data = resp.json()
                
                if data.get("code") == 0:
                    user = data.get("data", {}).get("user", {})
                    users.append({
                        "open_id": user.get("open_id"),
                        "name": user.get("name"),
                        "email": user.get("email"),
                        "mobile": user.get("mobile"),
                        "department_ids": user.get("department_ids", []),
                    })
        
        # 更新缓存
        self._users_cache = users
        self._users_cache_time = time.time()
        
        return users


# 单例获取
_client: Optional[FeishuClient] = None

def get_feishu_client() -> FeishuClient:
    global _client
    if _client is None:
        _client = FeishuClient()
    return _client
