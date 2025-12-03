import os
#!/usr/bin/env python3
"""
飞书 API 工具模块
- FeishuClient: 飞书 API 客户端
- 两种卡片：任务分配卡、进度汇报卡
- 简单方案：按钮+提示回复文字
"""

import time
import json
from typing import Optional, Dict, Any
import httpx

# ==================== 配置 ====================
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "cli_a9a255eeb278de1a")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
if not FEISHU_APP_SECRET:
    print("[WARNING] FEISHU_APP_SECRET not set!")
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
        self._initialized = True
        print("[FeishuClient] 初始化完成")

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
            print(f"[FeishuClient] Token 刷新成功, 有效期: {data['expire']}s")
            return self._token

    async def send_to_user(self, open_id: str, text: str = None, card: Dict[str, Any] = None) -> Dict[str, Any]:
        """向用户私聊发送消息"""
        token = await self.get_token()

        if card:
            msg_type = "interactive"
            content = json.dumps(card)
        else:
            msg_type = "text"
            content = json.dumps({"text": text or "无内容"})

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/im/v1/messages",
                params={"receive_id_type": "open_id"},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": open_id,
                    "msg_type": msg_type,
                    "content": content
                }
            )
            result = resp.json()
            if result.get("code") != 0:
                print(f"[FeishuClient] 发送失败: {result}")
            return result

    async def reply_text(self, message_id: str, text: str) -> Dict[str, Any]:
        """回复消息"""
        token = await self.get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/im/v1/messages/{message_id}/reply",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "msg_type": "text",
                    "content": json.dumps({"text": text})
                }
            )
            return resp.json()


# ==================== 单例获取 ====================

_feishu_client: Optional[FeishuClient] = None

def get_feishu_client() -> FeishuClient:
    global _feishu_client
    if _feishu_client is None:
        _feishu_client = FeishuClient()
    return _feishu_client


# ==================== 卡片模板 ====================

def build_task_assignment_card(task: Dict[str, Any], project_name: str = "", assignee_name: str = "") -> Dict[str, Any]:
    """
    任务分配卡片
    按钮：收到 / 有疑问
    底部提示可回复文字
    """
    task_id = task.get("id", "unknown")
    deadline = task.get("deadline", "")
    if deadline and len(deadline) > 10:
        deadline = deadline[:10]

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📋 新任务分配"},
            "template": "blue"
        },
        "elements": [
            # 任务标题
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**{task.get('title', '未命名任务')}**"}
            },
            # 项目和截止日期
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**项目：** {project_name or '未指定'}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**截止：** {deadline or '未设置'}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**负责人：** {assignee_name or '未指定'}"}}
                ]
            },
            {"tag": "hr"},
            # 按钮区域
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 收到"},
                        "type": "primary",
                        "value": {"action": "accept", "task_id": task_id}
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❓ 有疑问（可聊天框文字补充）"},
                        "type": "default",
                        "value": {"action": "question", "task_id": task_id}
                    }
                ]
            },
            # 底部提示
            {"tag": "note", "elements": [
                {"tag": "plain_text", "content": f"任务ID: {task_id} | 点击按钮确认，也可回复文字说明"}
            ]}
        ]
    }

    if task.get("description"):
        card["elements"].insert(2, {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**描述：** {task.get('description')}"}
        })

    return card


def build_progress_check_card(task: Dict[str, Any], project_name: str = "", assignee_name: str = "") -> Dict[str, Any]:
    """
    进度汇报卡片
    按钮：绿灯/黄灯/红灯
    底部提示可回复文字
    """
    task_id = task.get("id", "unknown")

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📊 进度确认"},
            "template": "turquoise"
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**{task.get('title', '未命名任务')}**"}
            },
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"项目：{project_name or '未指定'}"}
            },
            {"tag": "hr"},
            # 按钮区域
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🟢 正常"},
                        "type": "primary",
                        "value": {"action": "on_track", "task_id": task_id}
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🟡 延期"},
                        "type": "default",
                        "value": {"action": "need_time", "task_id": task_id}
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🔴 阻塞"},
                        "type": "danger",
                        "value": {"action": "blocked", "task_id": task_id}
                    }
                ]
            },
            # 底部提示
            {"tag": "note", "elements": [
                {"tag": "plain_text", "content": f"任务ID: {task_id} | 点击按钮汇报进度，也可回复文字说明"}
            ]}
        ]
    }

    return card


# ==================== 发送通知函数 ====================

async def notify_task_assignment(task: Dict[str, Any], project_name: str = "") -> Dict[str, Any]:
    """发送任务分配通知"""
    from services.project_store import get_project_store

    store = get_project_store()
    client = get_feishu_client()

    feishu_open_id = task.get("assignee_feishu_id")
    if not feishu_open_id:
        print(f"[FeishuNotify] 任务没有assignee_feishu_id")
        return {"success": False, "reason": "no_assignee_feishu_id"}

    # 获取员工名字
    employee = await store.get_employee(feishu_open_id)
    assignee_name = employee.get("name", "未知") if employee else "未知"

    # 构建任务分配卡片
    card = build_task_assignment_card(task, project_name, assignee_name)

    # 发送
    result = await client.send_to_user(feishu_open_id, card=card)

    if result.get("code") == 0:
        print(f"[FeishuNotify] ✅ 任务分配通知已发送给 {assignee_name}")
        return {"success": True, "message_id": result.get("data", {}).get("message_id")}
    else:
        print(f"[FeishuNotify] ❌ 通知失败: {result}")
        return {"success": False, "reason": "send_failed", "detail": result}


async def send_progress_check(task: Dict[str, Any], project_name: str = "") -> Dict[str, Any]:
    """发送进度确认卡片"""
    from services.project_store import get_project_store

    store = get_project_store()
    client = get_feishu_client()

    feishu_open_id = task.get("assignee_feishu_id")
    if not feishu_open_id:
        return {"success": False, "reason": "no_assignee_feishu_id"}

    employee = await store.get_employee(feishu_open_id)
    assignee_name = employee.get("name", "未知") if employee else "未知"

    # 构建进度汇报卡片
    card = build_progress_check_card(task, project_name, assignee_name)

    result = await client.send_to_user(feishu_open_id, card=card)

    if result.get("code") == 0:
        print(f"[FeishuNotify] ✅ 进度确认卡片已发送给 {assignee_name}")
        return {"success": True, "message_id": result.get("data", {}).get("message_id")}
    else:
        return {"success": False, "reason": "send_failed", "detail": result}


# ===== 获取群聊信息 =====

async def get_chat_info(chat_id: str) -> dict:
    """
    获取群聊详情（包括群名）
    
    飞书API: GET /im/v1/chats/{chat_id}
    """
    import httpx
    import os
    
    app_id = os.getenv('FEISHU_APP_ID')
    app_secret = os.getenv('FEISHU_APP_SECRET')
    
    if not app_id or not app_secret:
        return {'chat_id': chat_id, 'name': f'群聊_{chat_id[-8:]}'}
    
    try:
        async with httpx.AsyncClient() as client:
            # 获取 tenant_access_token
            token_resp = await client.post(
                'https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal',
                json={'app_id': app_id, 'app_secret': app_secret}
            )
            token = token_resp.json().get('tenant_access_token')
            
            if not token:
                return {'chat_id': chat_id, 'name': f'群聊_{chat_id[-8:]}'}
            
            # 获取群聊信息
            chat_resp = await client.get(
                f'https://open.larksuite.com/open-apis/im/v1/chats/{chat_id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            
            data = chat_resp.json()
            if data.get('code') == 0:
                chat_data = data.get('data', {})
                return {
                    'chat_id': chat_id,
                    'name': chat_data.get('name', f'群聊_{chat_id[-8:]}'),
                    'description': chat_data.get('description', ''),
                    'owner_id': chat_data.get('owner_id', ''),
                    'chat_mode': chat_data.get('chat_mode', ''),
                    'member_count': chat_data.get('user_count', 0)
                }
            else:
                return {'chat_id': chat_id, 'name': f'群聊_{chat_id[-8:]}'}
                
    except Exception as e:
        print(f'[FeishuTools] 获取群聊信息失败: {e}')
        return {'chat_id': chat_id, 'name': f'群聊_{chat_id[-8:]}'}


async def update_chat_names_in_db():
    """
    批量更新数据库中的群聊名称
    """
    from motor.motor_asyncio import AsyncIOMotorClient
    
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['vulcan_brain']
    
    # 获取所有群聊ID
    chat_ids = await db.feishu_messages.distinct('chat_id')
    
    updated = 0
    for chat_id in chat_ids:
        info = await get_chat_info(chat_id)
        if info.get('name') and not info['name'].startswith('群聊_'):
            # 更新 chat_metadata
            await db.chat_metadata.update_one(
                {'chat_id': chat_id},
                {'$set': {'chat_name': info['name'], 'member_count': info.get('member_count', 0)}},
                upsert=True
            )
            updated += 1
            print(f'  更新: {chat_id} -> {info['name']}')
    
    print(f'[FeishuTools] 共更新 {updated} 个群聊名称')
    return updated
