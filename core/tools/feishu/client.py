"""
Vulcan Brain - Feishu Client (完整版)
支持消息、群聊、审批、日历、任务等全功能
"""

import os
import time
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
import httpx

# ==================== 配置 ====================
FEISHU_APP_ID = os.getenv("FEISHU_BRAIN_APP_ID", "cli_a9a3995b80389e1a")
FEISHU_APP_SECRET = os.getenv("FEISHU_BRAIN_APP_SECRET", "")
FEISHU_BASE_URL = "https://open.larksuite.com/open-apis"


class FeishuClient:
    """飞书 API 客户端 - 单例模式，全功能版"""

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

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """通用请求方法"""
        token = await self.get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "GET":
                resp = await client.get(f"{FEISHU_BASE_URL}{endpoint}", headers=headers, **kwargs)
            elif method.upper() == "POST":
                resp = await client.post(f"{FEISHU_BASE_URL}{endpoint}", headers=headers, **kwargs)
            elif method.upper() == "PUT":
                resp = await client.put(f"{FEISHU_BASE_URL}{endpoint}", headers=headers, **kwargs)
            elif method.upper() == "DELETE":
                resp = await client.delete(f"{FEISHU_BASE_URL}{endpoint}", headers=headers, **kwargs)
            else:
                raise ValueError(f"不支持的 HTTP 方法: {method}")
            return resp.json()

    # ==================== 消息相关 ====================
    
    async def send_message(
        self,
        receive_id: str,
        receive_id_type: str = "open_id",
        msg_type: str = "text",
        content: str = "",
        card: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """发送消息到飞书"""
        if card:
            actual_msg_type = "interactive"
            actual_content = json.dumps(card)
        else:
            actual_msg_type = msg_type
            if msg_type == "text":
                actual_content = json.dumps({"text": content})
            else:
                actual_content = content

        return await self._request(
            "POST",
            "/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            json={
                "receive_id": receive_id,
                "msg_type": actual_msg_type,
                "content": actual_content
            }
        )

    async def reply_message(
        self,
        message_id: str,
        msg_type: str = "text",
        content: str = ""
    ) -> Dict[str, Any]:
        """回复消息"""
        if msg_type == "text":
            actual_content = json.dumps({"text": content})
        else:
            actual_content = content

        return await self._request(
            "POST",
            f"/im/v1/messages/{message_id}/reply",
            json={
                "msg_type": msg_type,
                "content": actual_content
            }
        )

    async def get_chat_history(
        self,
        container_id: str,
        container_id_type: str = "chat",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """获取聊天历史记录"""
        params = {
            "container_id_type": container_id_type,
            "container_id": container_id,
            "page_size": page_size
        }
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/im/v1/messages", params=params)

    # ==================== 群聊管理 ====================

    async def create_chat(
        self,
        name: str,
        description: str = "",
        user_ids: Optional[List[str]] = None,
        user_id_type: str = "open_id"
    ) -> Dict[str, Any]:
        """创建群聊"""
        body = {
            "name": name,
            "description": description,
        }
        if user_ids:
            body["user_id_list"] = user_ids

        return await self._request(
            "POST",
            "/im/v1/chats",
            params={"user_id_type": user_id_type},
            json=body
        )

    async def add_chat_members(
        self,
        chat_id: str,
        user_ids: List[str],
        user_id_type: str = "open_id"
    ) -> Dict[str, Any]:
        """添加群成员"""
        return await self._request(
            "POST",
            f"/im/v1/chats/{chat_id}/members",
            params={"member_id_type": user_id_type},
            json={"id_list": user_ids}
        )

    async def remove_chat_members(
        self,
        chat_id: str,
        user_ids: List[str],
        user_id_type: str = "open_id"
    ) -> Dict[str, Any]:
        """移除群成员"""
        return await self._request(
            "DELETE",
            f"/im/v1/chats/{chat_id}/members",
            params={"member_id_type": user_id_type},
            json={"id_list": user_ids}
        )

    async def list_chat_members(
        self,
        chat_id: str,
        user_id_type: str = "open_id",
        page_size: int = 100
    ) -> Dict[str, Any]:
        """获取群成员列表"""
        return await self._request(
            "GET",
            f"/im/v1/chats/{chat_id}/members",
            params={
                "member_id_type": user_id_type,
                "page_size": page_size
            }
        )

    async def list_chats(
        self,
        user_id_type: str = "open_id",
        page_size: int = 100
    ) -> Dict[str, Any]:
        """获取机器人所在的群聊列表"""
        return await self._request(
            "GET",
            "/im/v1/chats",
            params={
                "user_id_type": user_id_type,
                "page_size": page_size
            }
        )

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """获取群信息"""
        return await self._request("GET", f"/im/v1/chats/{chat_id}")

    async def update_chat(
        self,
        chat_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """更新群信息"""
        body = {}
        if name:
            body["name"] = name
        if description:
            body["description"] = description
        
        return await self._request("PUT", f"/im/v1/chats/{chat_id}", json=body)

    # ==================== 用户/通讯录 ====================

    async def get_all_visible_users(self, force_refresh: bool = False) -> List[Dict]:
        """获取机器人可见范围内的所有用户 (带缓存，5分钟)"""
        cache_ttl = 300
        if not force_refresh and self._users_cache and time.time() - self._users_cache_time < cache_ttl:
            return self._users_cache
        
        users = []
        scopes = await self._request("GET", "/contact/v3/scopes")
        
        if scopes.get("code") != 0:
            raise Exception(f"获取可见范围失败: {scopes}")
        
        user_ids = scopes.get("data", {}).get("user_ids", [])
        
        for user_id in user_ids:
            data = await self._request(
                "GET",
                f"/contact/v3/users/{user_id}",
                params={"user_id_type": "open_id"}
            )
            
            if data.get("code") == 0:
                user = data.get("data", {}).get("user", {})
                users.append({
                    "open_id": user.get("open_id"),
                    "name": user.get("name"),
                    "email": user.get("email"),
                    "mobile": user.get("mobile"),
                    "department_ids": user.get("department_ids", []),
                })
        
        self._users_cache = users
        self._users_cache_time = time.time()
        return users

    async def get_user_info(
        self,
        user_id: str,
        user_id_type: str = "open_id"
    ) -> Dict[str, Any]:
        """获取单个用户详情"""
        return await self._request(
            "GET",
            f"/contact/v3/users/{user_id}",
            params={"user_id_type": user_id_type}
        )

    async def list_department_users(
        self,
        department_id: str,
        user_id_type: str = "open_id",
        page_size: int = 50
    ) -> Dict[str, Any]:
        """获取部门成员列表"""
        return await self._request(
            "GET",
            f"/contact/v3/users/find_by_department",
            params={
                "department_id": department_id,
                "user_id_type": user_id_type,
                "page_size": page_size
            }
        )

    async def list_departments(
        self,
        parent_department_id: str = "0",
        page_size: int = 50
    ) -> Dict[str, Any]:
        """获取部门列表"""
        return await self._request(
            "GET",
            "/contact/v3/departments",
            params={
                "parent_department_id": parent_department_id,
                "page_size": page_size
            }
        )

    # ==================== 审批 ====================

    async def list_approval_instances(
        self,
        approval_code: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """获取审批实例列表"""
        body = {
            "approval_code": approval_code,
            "page_size": page_size
        }
        if start_time:
            body["start_time"] = str(start_time)
        if end_time:
            body["end_time"] = str(end_time)

        return await self._request("POST", "/approval/v4/instances/query", json=body)

    async def get_approval_instance(self, instance_id: str) -> Dict[str, Any]:
        """获取审批实例详情"""
        return await self._request("GET", f"/approval/v4/instances/{instance_id}")

    async def list_user_approval_tasks(
        self,
        user_id: str,
        user_id_type: str = "open_id",
        page_size: int = 50
    ) -> Dict[str, Any]:
        """获取用户的待审批任务列表"""
        return await self._request(
            "GET",
            "/approval/v4/tasks/query",
            params={
                "user_id": user_id,
                "user_id_type": user_id_type,
                "page_size": page_size
            }
        )

    async def approve_task(
        self,
        approval_code: str,
        instance_code: str,
        user_id: str,
        task_id: str,
        comment: str = "",
        user_id_type: str = "open_id"
    ) -> Dict[str, Any]:
        """同意审批"""
        return await self._request(
            "POST",
            "/approval/v4/tasks/approve",
            json={
                "approval_code": approval_code,
                "instance_code": instance_code,
                "user_id": user_id,
                "user_id_type": user_id_type,
                "task_id": task_id,
                "comment": comment
            }
        )

    async def reject_task(
        self,
        approval_code: str,
        instance_code: str,
        user_id: str,
        task_id: str,
        comment: str = "",
        user_id_type: str = "open_id"
    ) -> Dict[str, Any]:
        """拒绝审批"""
        return await self._request(
            "POST",
            "/approval/v4/tasks/reject",
            json={
                "approval_code": approval_code,
                "instance_code": instance_code,
                "user_id": user_id,
                "user_id_type": user_id_type,
                "task_id": task_id,
                "comment": comment
            }
        )

    async def create_approval_instance(
        self,
        approval_code: str,
        user_id: str,
        form: str,
        user_id_type: str = "open_id"
    ) -> Dict[str, Any]:
        """创建审批实例"""
        return await self._request(
            "POST",
            "/approval/v4/instances",
            json={
                "approval_code": approval_code,
                "user_id": user_id,
                "form": form
            }
        )

    async def list_approval_definitions(self, page_size: int = 100) -> Dict[str, Any]:
        """获取审批定义列表"""
        return await self._request(
            "GET",
            "/approval/v4/approvals",
            params={"page_size": page_size}
        )

    # ==================== 日历 ====================

    async def list_calendars(self, page_size: int = 50) -> Dict[str, Any]:
        """获取日历列表"""
        return await self._request(
            "GET",
            "/calendar/v4/calendars",
            params={"page_size": page_size}
        )

    async def create_calendar_event(
        self,
        calendar_id: str,
        summary: str,
        start_time: Dict[str, Any],
        end_time: Dict[str, Any],
        description: str = "",
        attendees: Optional[List[Dict]] = None,
        need_notification: bool = True
    ) -> Dict[str, Any]:
        """创建日历事件"""
        body = {
            "summary": summary,
            "description": description,
            "start_time": start_time,
            "end_time": end_time,
            "need_notification": need_notification
        }
        if attendees:
            body["attendee_ability"] = "can_modify_event"
            body["attendees"] = attendees

        return await self._request(
            "POST",
            f"/calendar/v4/calendars/{calendar_id}/events",
            json=body
        )

    async def list_calendar_events(
        self,
        calendar_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """获取日历事件列表"""
        params = {"page_size": page_size}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request(
            "GET",
            f"/calendar/v4/calendars/{calendar_id}/events",
            params=params
        )

    async def get_primary_calendar(self) -> Dict[str, Any]:
        """获取主日历"""
        return await self._request("GET", "/calendar/v4/calendars/primary")

    async def check_free_busy(
        self,
        time_min: str,
        time_max: str,
        user_ids: List[str],
        user_id_type: str = "open_id"
    ) -> Dict[str, Any]:
        """查询忙闲"""
        return await self._request(
            "POST",
            "/calendar/v4/freebusy/query",
            json={
                "time_min": time_min,
                "time_max": time_max,
                "user_id_type": user_id_type,
                "user_ids": user_ids
            }
        )

    # ==================== 任务 ====================

    async def create_task(
        self,
        summary: str,
        description: str = "",
        due: Optional[Dict[str, Any]] = None,
        members: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """创建任务"""
        body = {
            "summary": summary,
            "description": description
        }
        if due:
            body["due"] = due
        if members:
            body["members"] = members

        return await self._request("POST", "/task/v2/tasks", json=body)

    async def list_tasks(
        self,
        page_size: int = 50,
        completed: Optional[bool] = None
    ) -> Dict[str, Any]:
        """获取任务列表"""
        params = {"page_size": page_size}
        if completed is not None:
            params["completed"] = str(completed).lower()

        return await self._request("GET", "/task/v2/tasks", params=params)

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """获取任务详情"""
        return await self._request("GET", f"/task/v2/tasks/{task_id}")

    async def update_task(
        self,
        task_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        completed: Optional[bool] = None
    ) -> Dict[str, Any]:
        """更新任务"""
        body = {}
        update_fields = []
        
        if summary is not None:
            body["task"] = body.get("task", {})
            body["task"]["summary"] = summary
            update_fields.append("summary")
        if description is not None:
            body["task"] = body.get("task", {})
            body["task"]["description"] = description
            update_fields.append("description")
        if completed is not None:
            body["task"] = body.get("task", {})
            body["task"]["completed_at"] = str(int(time.time() * 1000)) if completed else "0"
            update_fields.append("completed_at")
        
        if update_fields:
            body["update_fields"] = update_fields

        return await self._request("PATCH", f"/task/v2/tasks/{task_id}", json=body)

    async def complete_task(self, task_id: str) -> Dict[str, Any]:
        """完成任务"""
        return await self.update_task(task_id, completed=True)


# 单例获取
_client: Optional[FeishuClient] = None

def get_feishu_client() -> FeishuClient:
    global _client
    if _client is None:
        _client = FeishuClient()
    return _client
