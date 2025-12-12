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
FEISHU_BRAIN_APP_ID = os.getenv("FEISHU_BRAIN_APP_ID", "cli_a9a3995b80389e1a")
FEISHU_BRAIN_APP_SECRET = os.getenv("FEISHU_BRAIN_APP_SECRET", "")
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


    async def get_brain_token(self) -> str:
        """获取 Brain 机器人的 token (有通讯录权限)"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": FEISHU_BRAIN_APP_ID,
                    "app_secret": FEISHU_BRAIN_APP_SECRET
                }
            )
            data = resp.json()
            if data.get("code") == 0:
                print(f"[FeishuClient] Brain Token 获取成功")
                return data.get("tenant_access_token", "")
            else:
                print(f"[FeishuClient] Brain Token 获取失败: {data}")
                return ""

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



    async def get_department_users(self, department_id: str = "0") -> list:
        """获取机器人可见范围内的所有用户
        使用 /contact/v3/scopes 获取可见用户ID，然后逐个获取详情
        """
        token = await self.get_token()  # PMO机器人
        users = []

        async with httpx.AsyncClient() as client:
            # 1. 获取机器人可见的用户ID列表
            resp = await client.get(
                f"{FEISHU_BASE_URL}/contact/v3/scopes",
                headers={"Authorization": f"Bearer {token}"}
            )
            scopes = resp.json()
            
            if scopes.get("code") != 0:
                print(f"[FeishuClient] 获取可见范围失败: {scopes}")
                return []
            
            user_ids = scopes.get("data", {}).get("user_ids", [])
            print(f"[FeishuClient] 可见用户数: {len(user_ids)}")
            
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
                        "avatar": user.get("avatar", {}).get("avatar_72", ""),
                        "status": user.get("status", {})
                    })
                else:
                    print(f"[FeishuClient] 获取用户 {user_id} 失败: {data}")

        print(f"[FeishuClient] 获取到 {len(users)} 个用户")
        return users

    async def get_departments(self, parent_id: str = "0") -> list:
        """获取部门列表"""
        token = await self.get_token()  # PMO机器人  # 使用Brain机器人(有通讯录权限)
        departments = []

        async with httpx.AsyncClient() as client:
            params = {
                "parent_department_id": parent_id,
                "department_id_type": "open_department_id",
                "fetch_child": True
            }

            resp = await client.get(
                f"{FEISHU_BASE_URL}/contact/v3/departments",
                params=params,
                headers={"Authorization": f"Bearer {token}"}
            )
            data = resp.json()

            if data.get("code") != 0:
                print(f"[FeishuClient] 获取部门列表失败: {data}")
                return []

            items = data.get("data", {}).get("items", [])
            for dept in items:
                departments.append({
                    "department_id": dept.get("open_department_id"),
                    "name": dept.get("name"),
                    "parent_id": dept.get("parent_department_id"),
                    "member_count": dept.get("member_count", 0)
                })

        print(f"[FeishuClient] 获取到 {len(departments)} 个部门")
        return departments


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
    任务分配卡片 V3
    统一交互模式：下拉选择 → 输入框 → 提交按钮
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
            # Form 包裹选择器、输入框和按钮
            {
                "tag": "form",
                "name": "assignment_form",
                "elements": [
                    # 1. 状态选择（必选）
                    {
                        "tag": "select_static",
                        "name": "response_status",
                        "placeholder": {"tag": "plain_text", "content": "请选择回复状态"},
                        "options": [
                            {"text": {"tag": "plain_text", "content": "✅ 收到，开始执行"}, "value": "accept"},
                            {"text": {"tag": "plain_text", "content": "❓ 有疑问需要确认"}, "value": "question"},
                            {"text": {"tag": "plain_text", "content": "❌ 无法接受"}, "value": "reject"}
                        ]
                    },
                    # 2. 备注输入框
                    {
                        "tag": "input",
                        "name": "notes",
                        "placeholder": {"tag": "plain_text", "content": "请填写备注（如有疑问或无法接受请说明）"},
                        "max_length": 500,
                        "label": {"tag": "plain_text", "content": "备注说明:"},
                        "label_position": "top"
                    },
                    # 3. 提交按钮
                    {
                        "tag": "button",
                        "action_type": "form_submit",
                        "name": "submit_btn",
                        "text": {"tag": "plain_text", "content": "📤 提交回复"},
                        "type": "primary",
                        "value": {"action": "assignment_response", "task_id": task_id}
                    }
                ]
            },
            # 底部提示
            {"tag": "note", "elements": [
                {"tag": "plain_text", "content": f"任务ID: {task_id}"}
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
    进度确认卡片 V3
    统一交互模式：下拉选择 → 输入框 → 提交按钮
    """
    task_id = task.get("id", "unknown")
    deadline = task.get("deadline", "")
    if deadline and len(deadline) > 10:
        deadline = deadline[:10]

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📊 进度确认"},
            "template": "turquoise"
        },
        "elements": [
            # 任务标题
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**{task.get('title', '未命名任务')}**"}
            },
            # 项目信息
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**项目：** {project_name or '未指定'}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**截止：** {deadline or '未设置'}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**负责人：** {assignee_name or '未指定'}"}}
                ]
            },
            {"tag": "hr"},
            # Form 包裹选择器、输入框和按钮
            {
                "tag": "form",
                "name": "progress_form",
                "elements": [
                    # 1. 进度状态选择（必选）
                    {
                        "tag": "select_static",
                        "name": "progress_status",
                        "placeholder": {"tag": "plain_text", "content": "请选择当前进度状态"},
                        "options": [
                            {"text": {"tag": "plain_text", "content": "🟢 正常推进中"}, "value": "on_track"},
                            {"text": {"tag": "plain_text", "content": "🟡 需要更多时间"}, "value": "need_time"},
                            {"text": {"tag": "plain_text", "content": "🔴 遇到阻塞"}, "value": "blocked"},
                            {"text": {"tag": "plain_text", "content": "🎉 已完成"}, "value": "completed"}
                        ]
                    },
                    # 2. 进度说明输入框
                    {
                        "tag": "input",
                        "name": "notes",
                        "placeholder": {"tag": "plain_text", "content": "请填写进度说明（如需延期或遇到阻塞请说明）"},
                        "max_length": 500,
                        "label": {"tag": "plain_text", "content": "进度说明:"},
                        "label_position": "top"
                    },
                    # 3. 提交按钮
                    {
                        "tag": "button",
                        "action_type": "form_submit",
                        "name": "submit_btn",
                        "text": {"tag": "plain_text", "content": "📤 提交进度"},
                        "type": "primary",
                        "value": {"action": "progress_update", "task_id": task_id}
                    }
                ]
            },
            # 底部提示
            {"tag": "note", "elements": [
                {"tag": "plain_text", "content": f"任务ID: {task_id}"}
            ]}
        ]
    }

    return card



def build_overdue_reminder_card(task: Dict[str, Any], project_name: str = "", assignee_name: str = "", days_overdue: int = 0) -> Dict[str, Any]:
    """
    逾期提醒卡片 V3
    统一交互模式：下拉选择 → 输入框 → 提交按钮
    """
    task_id = task.get("id", "unknown")
    deadline = task.get("deadline", "")
    if deadline and len(deadline) > 10:
        deadline = deadline[:10]

    overdue_text = f"已逾期 {days_overdue} 天" if days_overdue > 0 else "即将逾期"

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "⚠️ 任务逾期提醒"},
            "template": "red"
        },
        "elements": [
            # 逾期警告
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"🔴 **{overdue_text}**"}
            },
            # 任务标题
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**任务：** {task.get('title', '未命名任务')}"}
            },
            # 项目和截止日期
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**项目：** {project_name or '未指定'}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**原截止：** {deadline or '未设置'}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**负责人：** {assignee_name or '未指定'}"}}
                ]
            },
            {"tag": "hr"},
            # Form 包裹选择器、输入框和按钮
            {
                "tag": "form",
                "name": "overdue_form",
                "elements": [
                    # 1. 处理方式选择（必选）
                    {
                        "tag": "select_static",
                        "name": "overdue_action",
                        "placeholder": {"tag": "plain_text", "content": "请选择处理方式"},
                        "options": [
                            {"text": {"tag": "plain_text", "content": "✅ 今日内完成"}, "value": "complete_today"},
                            {"text": {"tag": "plain_text", "content": "📅 申请延期"}, "value": "request_extension"},
                            {"text": {"tag": "plain_text", "content": "🎉 已经完成"}, "value": "mark_completed"},
                            {"text": {"tag": "plain_text", "content": "🚧 遇到阻塞"}, "value": "blocked"}
                        ]
                    },
                    # 2. 说明输入框
                    {
                        "tag": "input",
                        "name": "notes",
                        "placeholder": {"tag": "plain_text", "content": "请填写说明（如申请延期或遇到阻塞请说明）"},
                        "max_length": 500,
                        "label": {"tag": "plain_text", "content": "说明:"},
                        "label_position": "top"
                    },
                    # 3. 提交按钮
                    {
                        "tag": "button",
                        "action_type": "form_submit",
                        "name": "submit_btn",
                        "text": {"tag": "plain_text", "content": "📤 提交回复"},
                        "type": "primary",
                        "value": {"action": "overdue_response", "task_id": task_id}
                    }
                ]
            },
            # 底部提示
            {"tag": "note", "elements": [
                {"tag": "plain_text", "content": f"任务ID: {task_id}"}
            ]}
        ]
    }

    return card



def build_blocker_report_card(task: Dict[str, Any], project_name: str = "", assignee_name: str = "") -> Dict[str, Any]:
    """
    阻塞上报卡片 V2
    带输入框，用户选择阻塞类型后可以直接填写原因
    """
    task_id = task.get("id", "unknown")

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🚧 阻塞原因上报"},
            "template": "orange"
        },
        "elements": [
            # 任务标题
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**任务：** {task.get('title', '未命名任务')}"}
            },
            # 项目信息
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**项目：** {project_name or '未指定'}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**负责人：** {assignee_name or '未指定'}"}}
                ]
            },
            {"tag": "hr"},
            # Form 包裹选择器、输入框和按钮
            {
                "tag": "form",
                "name": "blocker_form",
                "elements": [
                    # 阻塞类型选择
                    {
                        "tag": "select_static",
                        "name": "blocker_type",
                        "placeholder": {"tag": "plain_text", "content": "选择阻塞类型"},
                        "options": [
                            {"text": {"tag": "plain_text", "content": "⏳ 等待依赖"}, "value": "dependency"},
                            {"text": {"tag": "plain_text", "content": "🔧 资源不足"}, "value": "resource"},
                            {"text": {"tag": "plain_text", "content": "❓ 需要决策"}, "value": "decision"},
                            {"text": {"tag": "plain_text", "content": "📝 其他原因"}, "value": "other"}
                        ]
                    },
                    # 原因输入框
                    {
                        "tag": "input",
                        "name": "blocker_reason",
                        "placeholder": {"tag": "plain_text", "content": "请描述具体阻塞原因"},
                        "max_length": 500,
                        "label": {"tag": "plain_text", "content": "阻塞原因:"},
                        "label_position": "top"
                    },
                    # 提交按钮
                    {
                        "tag": "button",
                        "action_type": "form_submit",
                        "name": "submit_btn",
                        "text": {"tag": "plain_text", "content": "📤 提交阻塞报告"},
                        "type": "primary",
                        "value": {"action": "submit_blocker", "task_id": task_id}
                    }
                ]
            },
            # 底部提示
            {"tag": "note", "elements": [
                {"tag": "plain_text", "content": f"任务ID: {task_id}"}
            ]}
        ]
    }

    return card


def build_daily_summary_card(tasks_summary: Dict[str, Any], date: str = "") -> Dict[str, Any]:
    """
    每日任务汇总卡片
    给员工展示今日任务情况
    """
    total = tasks_summary.get("total", 0)
    pending = tasks_summary.get("pending", 0)
    in_progress = tasks_summary.get("in_progress", 0)
    completed = tasks_summary.get("completed", 0)
    overdue = tasks_summary.get("overdue", 0)

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📅 {date or '今日'} 任务概览"},
            "template": "indigo"
        },
        "elements": [
            # 统计数字
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**总任务：** {total}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**待处理：** {pending}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**进行中：** {in_progress}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**已完成：** {completed}"}}
                ]
            },
            {"tag": "hr"}
        ]
    }

    # 逾期警告
    if overdue > 0:
        card["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"⚠️ **{overdue} 个任务已逾期，请尽快处理！**"}
        })

    # 任务列表（如果有）
    task_list = tasks_summary.get("tasks", [])
    if task_list:
        tasks_text = "\n".join([f"• {t.get('title', '未命名')} ({t.get('status', 'pending')})" for t in task_list[:5]])
        card["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**任务列表：**\n{tasks_text}"}
        })
        if len(task_list) > 5:
            card["elements"].append({
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": f"还有 {len(task_list) - 5} 个任务..."}]
            })

    return card


# ==================== 发送通知函数 ====================

async def notify_overdue_reminder(task: Dict[str, Any], project_name: str = "", days_overdue: int = 0) -> Dict[str, Any]:
    """发送逾期提醒通知"""
    from services.project_store import get_project_store

    assignee_id = task.get("assignee_feishu_id")
    if not assignee_id:
        return {"success": False, "error": "No assignee"}

    store = get_project_store()
    employee = await store.get_employee(assignee_id)
    assignee_name = employee.get("name", "") if employee else ""

    card = build_overdue_reminder_card(task, project_name, assignee_name, days_overdue)

    client = FeishuClient()
    result = await client.send_to_user(assignee_id, card=card)

    if result.get("code") == 0:
        print(f"[FeishuNotify] ⚠️ 逾期提醒已发送给 {assignee_name}")
        return {"success": True, "message_id": result.get("data", {}).get("message_id")}
    else:
        print(f"[FeishuNotify] 逾期提醒发送失败: {result}")
        return {"success": False, "error": result}


async def notify_blocker_report(task: Dict[str, Any], project_name: str = "") -> Dict[str, Any]:
    """发送阻塞上报卡片"""
    from services.project_store import get_project_store

    assignee_id = task.get("assignee_feishu_id")
    if not assignee_id:
        return {"success": False, "error": "No assignee"}

    store = get_project_store()
    employee = await store.get_employee(assignee_id)
    assignee_name = employee.get("name", "") if employee else ""

    card = build_blocker_report_card(task, project_name, assignee_name)

    client = FeishuClient()
    result = await client.send_to_user(assignee_id, card=card)

    if result.get("code") == 0:
        print(f"[FeishuNotify] 🚧 阻塞上报卡片已发送给 {assignee_name}")
        return {"success": True, "message_id": result.get("data", {}).get("message_id")}
    else:
        print(f"[FeishuNotify] 阻塞上报卡片发送失败: {result}")
        return {"success": False, "error": result}


async def notify_progress_check(task: Dict[str, Any], project_name: str = "") -> Dict[str, Any]:
    """发送进度询问卡片"""
    from services.project_store import get_project_store

    assignee_id = task.get("assignee_feishu_id")
    if not assignee_id:
        return {"success": False, "error": "No assignee"}

    store = get_project_store()
    employee = await store.get_employee(assignee_id)
    assignee_name = employee.get("name", "") if employee else ""

    card = build_progress_check_card(task, project_name, assignee_name)

    client = FeishuClient()
    result = await client.send_to_user(assignee_id, card=card)

    if result.get("code") == 0:
        print(f"[FeishuNotify] 📊 进度询问卡片已发送给 {assignee_name}")
        return {"success": True, "message_id": result.get("data", {}).get("message_id")}
    else:
        print(f"[FeishuNotify] 进度询问卡片发送失败: {result}")
        return {"success": False, "error": result}



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


# ==================== 用户主动查询/更新卡片 ====================

def build_my_tasks_card(tasks: list, user_name: str = "") -> Dict[str, Any]:
    """
    我的任务列表卡片
    按状态分组显示用户的所有任务
    """
    # 按状态分组
    blocked = [t for t in tasks if t.get("status") == "blocked"]
    at_risk = [t for t in tasks if t.get("status") == "at_risk"]
    in_progress = [t for t in tasks if t.get("status") == "in_progress"]
    pending = [t for t in tasks if t.get("status") == "pending"]
    completed = [t for t in tasks if t.get("status") == "completed"]

    # 排除已完成，计算活跃任务
    active_tasks = blocked + at_risk + in_progress + pending

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📋 {user_name or '我'}的任务 (共{len(active_tasks)}个进行中)"},
            "template": "blue"
        },
        "elements": []
    }

    # 统计概览
    card["elements"].append({
        "tag": "div",
        "fields": [
            {"is_short": True, "text": {"tag": "lark_md", "content": f"🔴 **阻塞:** {len(blocked)}"}},
            {"is_short": True, "text": {"tag": "lark_md", "content": f"🟡 **风险:** {len(at_risk)}"}},
            {"is_short": True, "text": {"tag": "lark_md", "content": f"🔵 **进行中:** {len(in_progress)}"}},
            {"is_short": True, "text": {"tag": "lark_md", "content": f"⚪ **待开始:** {len(pending)}"}}
        ]
    })
    card["elements"].append({"tag": "hr"})

    # 阻塞任务（优先显示）
    if blocked:
        card["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**🔴 阻塞中**"}
        })
        for t in blocked[:5]:
            deadline = t.get("deadline", "")[:10] if t.get("deadline") else "无截止"
            note = ""
            if t.get("response_notes"):
                note = t["response_notes"][-1].get("note", "")[:30]
            card["elements"].append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"• {t.get('title', '未命名')} | 截止: {deadline}" + (f"\n  └ _{note}_" if note else "")}
            })

    # 风险任务
    if at_risk:
        card["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**🟡 有风险**"}
        })
        for t in at_risk[:5]:
            deadline = t.get("deadline", "")[:10] if t.get("deadline") else "无截止"
            card["elements"].append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"• {t.get('title', '未命名')} | 截止: {deadline}"}
            })

    # 进行中任务
    if in_progress:
        card["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**🔵 进行中**"}
        })
        for t in in_progress[:5]:
            deadline = t.get("deadline", "")[:10] if t.get("deadline") else "无截止"
            card["elements"].append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"• {t.get('title', '未命名')} | 截止: {deadline}"}
            })
        if len(in_progress) > 5:
            card["elements"].append({
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": f"还有 {len(in_progress) - 5} 个进行中..."}]
            })

    # 待开始任务
    if pending:
        card["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**⚪ 待开始**"}
        })
        for t in pending[:3]:
            deadline = t.get("deadline", "")[:10] if t.get("deadline") else "无截止"
            card["elements"].append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"• {t.get('title', '未命名')} | 截止: {deadline}"}
            })
        if len(pending) > 3:
            card["elements"].append({
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": f"还有 {len(pending) - 3} 个待开始..."}]
            })

    # 无任务提示
    if not active_tasks:
        card["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "🎉 **太棒了！没有待处理的任务**"}
        })

    card["elements"].append({"tag": "hr"})

    # 操作按钮
    card["elements"].append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📊 更新任务状态"},
                "type": "primary",
                "value": {"action": "show_update_status_form"}
            },
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "🔄 刷新"},
                "type": "default",
                "value": {"action": "refresh_my_tasks"}
            }
        ]
    })

    return card


def build_update_status_form_card(tasks: list, user_name: str = "") -> Dict[str, Any]:
    """
    主动更新任务状态的表单卡片
    让用户选择任务并更新状态
    """
    # 只显示活跃任务（非完成）
    active_tasks = [t for t in tasks if t.get("status") != "completed"]

    if not active_tasks:
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📊 更新任务状态"},
                "template": "orange"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": "🎉 **没有需要更新的任务**"}}
            ]
        }

    # 构建任务选项
    task_options = []
    for t in active_tasks:
        deadline = t.get("deadline", "")[:10] if t.get("deadline") else ""
        status_emoji = {"blocked": "🔴", "at_risk": "🟡", "in_progress": "🔵", "pending": "⚪"}.get(t.get("status"), "⚪")
        label = f"{status_emoji} {t.get('title', '未命名')}"
        if deadline:
            label += f" (截止: {deadline})"
        task_options.append({
            "text": {"tag": "plain_text", "content": label[:50]},  # 限制长度
            "value": t.get("id")
        })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📊 更新任务状态"},
            "template": "orange"
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**{user_name or '你'}** 有 **{len(active_tasks)}** 个任务可以更新"}},
            {"tag": "hr"},
            {
                "tag": "form",
                "name": "update_status_form",
                "elements": [
                    # 1. 选择任务
                    {
                        "tag": "select_static",
                        "name": "task_id",
                        "placeholder": {"tag": "plain_text", "content": "选择要更新的任务"},
                        "options": task_options
                    },
                    # 2. 选择新状态
                    {
                        "tag": "select_static",
                        "name": "new_status",
                        "placeholder": {"tag": "plain_text", "content": "选择新状态"},
                        "options": [
                            {"text": {"tag": "plain_text", "content": "✅ 进展顺利"}, "value": "on_track"},
                            {"text": {"tag": "plain_text", "content": "⏰ 需要更多时间"}, "value": "need_time"},
                            {"text": {"tag": "plain_text", "content": "🚫 遇到阻塞"}, "value": "blocked"},
                            {"text": {"tag": "plain_text", "content": "🎉 已完成"}, "value": "completed"}
                        ]
                    },
                    # 3. 备注
                    {
                        "tag": "input",
                        "name": "notes",
                        "placeholder": {"tag": "plain_text", "content": "备注说明（可选）"},
                        "max_length": 500
                    },
                    # 4. 提交按钮
                    {
                        "tag": "button",
                        "action_type": "form_submit",
                        "name": "submit_btn",
                        "text": {"tag": "plain_text", "content": "📤 提交更新"},
                        "type": "primary",
                        "value": {"action": "submit_status_update"}
                    }
                ]
            }
        ]
    }

    return card


async def send_my_tasks_card(open_id: str) -> Dict[str, Any]:
    """
    发送"我的任务"卡片给用户
    """
    from services.project_store import get_project_store

    store = get_project_store()
    client = get_feishu_client()

    # 获取用户信息
    employee = await store.get_employee(open_id)
    user_name = employee.get("name", "") if employee else ""

    # 获取该用户的所有任务
    tasks = await store.list_tasks(assignee_feishu_id=open_id)

    # 构建卡片
    card = build_my_tasks_card(tasks, user_name)

    # 发送
    result = await client.send_to_user(open_id, card=card)

    if result.get("code") == 0:
        print(f"[FeishuNotify] 📋 任务列表已发送给 {user_name or open_id}")
        return {"success": True, "message_id": result.get("data", {}).get("message_id")}
    else:
        print(f"[FeishuNotify] 任务列表发送失败: {result}")
        return {"success": False, "error": result}


async def send_update_status_form(open_id: str) -> Dict[str, Any]:
    """
    发送"更新状态"表单卡片给用户
    """
    from services.project_store import get_project_store

    store = get_project_store()
    client = get_feishu_client()

    # 获取用户信息
    employee = await store.get_employee(open_id)
    user_name = employee.get("name", "") if employee else ""

    # 获取该用户的所有任务
    tasks = await store.list_tasks(assignee_feishu_id=open_id)

    # 构建卡片
    card = build_update_status_form_card(tasks, user_name)

    # 发送
    result = await client.send_to_user(open_id, card=card)

    if result.get("code") == 0:
        print(f"[FeishuNotify] 📊 更新状态表单已发送给 {user_name or open_id}")
        return {"success": True, "message_id": result.get("data", {}).get("message_id")}
    else:
        print(f"[FeishuNotify] 更新状态表单发送失败: {result}")
        return {"success": False, "error": result}
