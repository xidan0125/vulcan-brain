#!/usr/bin/env python3
#!/usr/bin/env python3
"""
飞书机器人 API - 处理消息和卡片交互
"""

import json
from typing import Dict, Any
from collections import defaultdict
from fastapi import APIRouter, Request

from tools.feishu_tools import get_feishu_client
from config import FEISHU_BRAIN_APP_ID as BRAIN_APP_ID, FEISHU_BRAIN_APP_SECRET as BRAIN_APP_SECRET
from datetime import datetime
import httpx
from vulcan_libs.ai_service import get_ai_service

# 消息存储 (五纬度系统-维度1)
_message_store = None
def get_msg_store():
    global _message_store
    if _message_store is None:
        try:
            from services.message_store import MessageStore
            _message_store = MessageStore()
        except Exception as e:
            print(f"[Feishu] MessageStore 加载失败: {e}")
    return _message_store


router = APIRouter()

def log(msg: str):
    print(f"[Feishu] {msg}", flush=True)

# ===== 消息去重 =====
_processed: set = set()

def is_dup(msg_id: str) -> bool:
    if msg_id in _processed:
        return True
    _processed.add(msg_id)
    if len(_processed) > 500:
        _processed.clear()
    return False


# ===== 记录最近发送者 =====
_recent_senders: list = []

# ===== 群聊对话历史 =====
_chat_history: dict = defaultdict(list)
MAX_HISTORY = 20  # 保留最近20条


# ===== Webhook =====

@router.post("/feishu/webhook")
async def feishu_webhook(request: Request):
    try:
        body = await request.json()
        log(f"收到: {json.dumps(body, ensure_ascii=False)[:500]}")

        # URL 验证
        if body.get("challenge"):
            return {"challenge": body.get("challenge")}

        # 消息事件
        header = body.get("header", {})
        event = body.get("event", {})

        if header.get("event_type") == "im.message.receive_v1":
            return await handle_msg(event)

        # 卡片交互事件 (按钮点击)
        if header.get("event_type") == "card.action.trigger":
            return await handle_card_action(event)

        # PMO机器人菜单点击事件
        if header.get("event_type") == "application.bot.menu_v6":
            return await handle_pmo_menu(event)

        return {"code": 0}
    except Exception as e:
        log(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return {"code": 0}


async def handle_msg(event: Dict[str, Any]):
    """处理文本消息"""
    msg = event.get("message", {})
    msg_id = msg.get("message_id", "")
    chat_id = msg.get("chat_id", "")

    if is_dup(msg_id):
        return {"code": 0}

    # 获取发送者
    sender = event.get("sender", {})
    sender_id = sender.get("sender_id", {})
    open_id = sender_id.get("open_id", "")

    log(f"发送者: open_id={open_id}")

    # 记录最近发送者
    if open_id:
        _recent_senders.append({"open_id": open_id, "chat_id": chat_id})
        if len(_recent_senders) > 10:
            _recent_senders.pop(0)

    # 只处理文本
    if msg.get("message_type") != "text":
        return {"code": 0}

    content = json.loads(msg.get("content", "{}"))
    text = content.get("text", "").strip()

    log(f"用户消息: {text}")

    # 简单回复
    client = get_feishu_client()

    # 检查是否是任务相关的回复（比如完成）
    if text in ["完成", "做完了", "搞定", "done", "Done"]:
        reply = "✅ 收到！请问是哪个任务完成了？可以告诉我任务名称"
    elif text.startswith("阻塞") or text.startswith("卡住"):
        reply = "🔴 收到阻塞反馈，请说明具体卡在哪里"
    else:
        reply = f"收到: {text}\n\n(项目管理功能升级中，请通过卡片按钮操作)"

    await client.reply_text(msg_id, reply)
    return {"code": 0}


async def handle_pmo_menu(event: Dict[str, Any]):
    """处理PMO机器人菜单点击事件"""
    from tools.feishu_tools import send_my_tasks_card, send_update_status_form

    event_key = event.get("event_key", "").strip()  # 去除首尾空格
    operator = event.get("operator", {})
    operator_id = operator.get("operator_id", {})
    open_id = operator_id.get("open_id", "")

    log(f"[PMO] 菜单点击: event_key={event_key}, user={open_id}")

    try:
        if event_key == "my_tasks":
            # 我的任务
            await send_my_tasks_card(open_id)
            return {"code": 0}

        elif event_key == "update_status":
            # 更新任务状态
            await send_update_status_form(open_id)
            return {"code": 0}

        else:
            log(f"[PMO] 未知菜单事件: {event_key}")
            return {"code": 0}

    except Exception as e:
        log(f"[PMO] 菜单处理错误: {e}")
        import traceback
        traceback.print_exc()
        return {"code": 0}


async def handle_card_action(event: Dict[str, Any]):
    """处理卡片按钮点击（含表单）"""
    from services.project_store import get_project_store

    action = event.get("action", {})
    value = action.get("value", {})

    # 获取表单输入值
    form_value = action.get("form_value", {})
    notes = form_value.get("notes", "")

    # 获取操作者信息
    operator = event.get("operator", {})
    open_id = operator.get("open_id", "")

    if not isinstance(value, dict):
        return {"code": 0}

    action_type = value.get("action")
    task_id = value.get("task_id")

    log(f"卡片操作: action={action_type}, task_id={task_id}, user={open_id}, notes={notes}")

    store = get_project_store()

    # ===== 任务分配卡片的回调 =====
    if action_type == "accept":
        await store.update_task_status(task_id, "in_progress")
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "in_progress",
            "notes": notes if notes else "已确认接收任务"
        })
        return {"toast": {"type": "success", "content": "✅ 任务已确认，开始处理！"}}

    elif action_type == "question":
        task = await store.get_task(task_id)
        task_title = task.get("title", "未知任务") if task else "未知任务"
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "❓ 请说明疑问"},
                "template": "orange"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"任务: **{task_title}**"}
                },
                {"tag": "hr"},
                {
                    "tag": "form",
                    "name": "question_form",
                    "elements": [
                        {
                            "tag": "input",
                            "name": "question_text",
                            "placeholder": {"content": "请输入你的疑问...", "tag": "plain_text"},
                            "width": "fill",
                            "max_length": 500
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "提交疑问"},
                            "type": "primary",
                            "action_type": "form_submit",
                            "name": "submit_question",
                            "value": {"action": "submit_question", "task_id": task_id}
                        }
                    ]
                }
            ]
        }

    elif action_type == "submit_question":
        form_value = action.get("form_value", {})
        question_text = form_value.get("question_text", "")
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "question",
            "notes": f"疑问: {question_text}"
        })
        return {"toast": {"type": "success", "content": "✅ 疑问已提交，等待回复"}}

    # ===== 进度汇报卡片的回调 =====
    elif action_type == "on_track":
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "on_track",
            "notes": notes if notes else "进展顺利"
        })
        return {"toast": {"type": "success", "content": "🟢 已记录：一切正常"}}

    elif action_type == "need_time":
        await store.update_task_status(task_id, "at_risk")
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "at_risk",
            "notes": notes if notes else "需要更多时间"
        })
        return {"toast": {"type": "warning", "content": "🟡 已记录延期"}}

    elif action_type == "blocked":
        await store.update_task_status(task_id, "blocked")
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "blocked",
            "notes": notes if notes else "遇到阻塞"
        })
        return {"toast": {"type": "error", "content": "🔴 已记录阻塞"}}


    # ===== V3 卡片统一回调处理 =====

    # 任务分配卡片 V3 - 统一回调
    elif action_type == "assignment_response":
        form_value = action.get("form_value", {})
        response_status = form_value.get("response_status", "")
        notes = form_value.get("notes", "")

        if not response_status:
            return {"toast": {"type": "error", "content": "请先选择回复状态"}}

        task = await store.get_task(task_id)

        # 状态映射: 用户选择 -> 保存到 response_status 数组
        response_status_map = {
            "accept": "accepted",
            "question": "questioned",
            "reject": "rejected"
        }
        mapped_response_status = response_status_map.get(response_status, "unknown")

        # 构建更新数据
        now = datetime.now().isoformat()
        update_data = {
            "response_at": now,
        }

        # 获取当前 response_status 数组并更新
        current_response_status = task.get("response_status", []) if task else []
        if mapped_response_status not in current_response_status:
            current_response_status.append(mapped_response_status)
        update_data["response_status"] = current_response_status

        # 添加 response_notes 历史
        current_notes = task.get("response_notes", []) if task else []
        current_notes.append({
            "status": mapped_response_status,
            "note": notes if notes else response_status,
            "at": now
        })
        update_data["response_notes"] = current_notes

        # 根据回复类型更新任务状态
        if response_status == "accept":
            update_data["status"] = "in_progress"
            update_data["lifecycle_status"] = "in_progress"
            update_data["started_at"] = now
        elif response_status == "question":
            update_data["status"] = "questioned"
        elif response_status == "reject":
            update_data["status"] = "rejected"

        await store.update_task(task_id, update_data)

        # 添加汇报记录
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": mapped_response_status,
            "notes": notes if notes else response_status
        })

        log(f"任务 {task_id} 状态更新: response_status={response_status}, mapped={mapped_response_status}")

        toast_map = {
            "accept": "已确认接受任务，开始执行！",
            "question": "疑问已提交，等待回复",
            "reject": "已提交拒绝，请等待处理"
        }
        return {"toast": {"type": "success", "content": toast_map.get(response_status, "已提交")}}

    # 进度确认卡片 V3 - 统一回调
    elif action_type == "progress_update":
        form_value = action.get("form_value", {})
        progress_status = form_value.get("progress_status", "")
        notes = form_value.get("notes", "")

        if not progress_status:
            return {"toast": {"type": "error", "content": "请先选择进度状态"}}

        task = await store.get_task(task_id)

        # 状态映射
        status_map = {
            "on_track": "on_track",
            "need_time": "at_risk",
            "blocked": "blocked",
            "completed": "completed"
        }
        mapped_status = status_map.get(progress_status, "unknown")

        now = datetime.now().isoformat()
        update_data = {"response_at": now}

        # 更新 response_status 数组
        current_response_status = task.get("response_status", []) if task else []
        # 健康状态互斥：移除旧的健康状态
        health_states = {"on_track", "at_risk", "blocked"}
        if mapped_status in health_states:
            current_response_status = [s for s in current_response_status if s not in health_states]
        if mapped_status not in current_response_status:
            current_response_status.append(mapped_status)
        update_data["response_status"] = current_response_status

        # 添加 response_notes 历史
        current_notes = task.get("response_notes", []) if task else []
        current_notes.append({
            "status": mapped_status,
            "note": notes if notes else progress_status,
            "at": now
        })
        update_data["response_notes"] = current_notes

        # 根据进度状态更新任务状态
        if progress_status == "completed":
            update_data["status"] = "completed"
            update_data["lifecycle_status"] = "completed"
            update_data["completed_at"] = now
        elif progress_status == "blocked":
            update_data["status"] = "blocked"
        elif progress_status == "need_time":
            update_data["status"] = "at_risk"
        else:
            update_data["status"] = "in_progress"

        await store.update_task(task_id, update_data)

        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": mapped_status,
            "notes": notes if notes else progress_status
        })

        log(f"任务 {task_id} 进度更新: progress_status={progress_status}, mapped={mapped_status}")

        toast_map = {
            "on_track": "已记录：进展顺利",
            "need_time": "已记录：需要更多时间",
            "blocked": "已记录：遇到阻塞",
            "completed": "已标记任务完成"
        }
        return {"toast": {"type": "success", "content": toast_map.get(progress_status, "已提交")}}

    # 逾期提醒卡片 V3 - 统一回调
    elif action_type == "overdue_response":
        form_value = action.get("form_value", {})
        overdue_action = form_value.get("overdue_action", "")
        notes = form_value.get("notes", "")

        if not overdue_action:
            return {"toast": {"type": "error", "content": "请先选择处理方式"}}

        task = await store.get_task(task_id)

        status_map = {
            "complete_today": "committed",
            "request_extension": "extension_requested",
            "mark_completed": "completed",
            "blocked": "blocked"
        }
        mapped_status = status_map.get(overdue_action, "unknown")

        now = datetime.now().isoformat()
        update_data = {"response_at": now}

        # 更新 response_status 数组
        current_response_status = task.get("response_status", []) if task else []
        if mapped_status not in current_response_status:
            current_response_status.append(mapped_status)
        update_data["response_status"] = current_response_status

        # 添加 response_notes 历史
        current_notes = task.get("response_notes", []) if task else []
        current_notes.append({
            "status": mapped_status,
            "note": notes if notes else overdue_action,
            "at": now
        })
        update_data["response_notes"] = current_notes

        # 根据逾期处理方式更新任务状态
        if overdue_action == "mark_completed":
            update_data["status"] = "completed"
            update_data["lifecycle_status"] = "completed"
            update_data["completed_at"] = now
        elif overdue_action == "blocked":
            update_data["status"] = "blocked"
        elif overdue_action == "complete_today":
            update_data["status"] = "in_progress"  # 承诺今日完成，保持进行中

        await store.update_task(task_id, update_data)

        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": mapped_status,
            "notes": notes if notes else overdue_action
        })

        log(f"任务 {task_id} 逾期处理: overdue_action={overdue_action}, mapped={mapped_status}")

        toast_map = {
            "complete_today": "已记录：承诺今日完成",
            "request_extension": "延期申请已提交",
            "mark_completed": "已标记任务完成",
            "blocked": "阻塞已上报"
        }
        return {"toast": {"type": "success", "content": toast_map.get(overdue_action, "已提交")}}


    # ===== 用户主动操作的卡片回调 =====

    # 刷新"我的任务"卡片
    elif action_type == "refresh_my_tasks":
        from tools.feishu_tools import send_my_tasks_card
        await send_my_tasks_card(open_id)
        return {"toast": {"type": "success", "content": "已刷新任务列表"}}

    # 显示更新状态表单
    elif action_type == "show_update_status_form":
        from tools.feishu_tools import send_update_status_form
        await send_update_status_form(open_id)
        return {"toast": {"type": "success", "content": "请在新卡片中更新状态"}}

    # 提交状态更新（用户主动更新）
    elif action_type == "submit_status_update":
        form_value = action.get("form_value", {})
        selected_task_id = form_value.get("task_id", "")
        new_status = form_value.get("new_status", "")
        notes = form_value.get("notes", "")

        if not selected_task_id:
            return {"toast": {"type": "error", "content": "请选择要更新的任务"}}
        if not new_status:
            return {"toast": {"type": "error", "content": "请选择新状态"}}

        task = await store.get_task(selected_task_id)
        if not task:
            return {"toast": {"type": "error", "content": "任务不存在"}}

        # 状态映射
        status_map = {
            "on_track": ("in_progress", "on_track", "进展顺利"),
            "need_time": ("at_risk", "at_risk", "需要更多时间"),
            "blocked": ("blocked", "blocked", "遇到阻塞"),
            "completed": ("completed", "completed", "已完成")
        }

        if new_status not in status_map:
            return {"toast": {"type": "error", "content": "无效的状态"}}

        task_status, report_status, default_note = status_map[new_status]
        now = datetime.now().isoformat()

        # 更新任务状态
        update_data = {
            "status": task_status,
            "response_at": now
        }

        if new_status == "completed":
            update_data["lifecycle_status"] = "completed"
            update_data["completed_at"] = now
            update_data["progress"] = 100

        # 更新 response_status 数组
        current_response_status = task.get("response_status", [])
        # 移除旧的健康状态
        health_states = {"on_track", "at_risk", "blocked", "completed"}
        current_response_status = [s for s in current_response_status if s not in health_states]
        current_response_status.append(report_status)
        update_data["response_status"] = current_response_status

        # 添加 response_notes 历史
        current_notes = task.get("response_notes", [])
        current_notes.append({
            "status": report_status,
            "note": notes if notes else default_note,
            "at": now
        })
        update_data["response_notes"] = current_notes

        await store.update_task(selected_task_id, update_data)

        # 添加汇报记录
        await store.add_report({
            "task_id": selected_task_id,
            "reporter_feishu_id": open_id,
            "status": report_status,
            "notes": notes if notes else default_note
        })

        task_title = task.get("title", "未知任务")
        log(f"用户 {open_id} 主动更新任务 {task_title} 状态为 {new_status}")

        toast_map = {
            "on_track": f"✅ {task_title} - 进展顺利",
            "need_time": f"⏰ {task_title} - 已记录延期",
            "blocked": f"🚫 {task_title} - 已记录阻塞",
            "completed": f"🎉 {task_title} - 已完成！"
        }
        return {"toast": {"type": "success", "content": toast_map.get(new_status, "已更新")}}


    return {"code": 0}


# ===== API 端点 =====

@router.get("/feishu/test")
async def test():
    try:
        client = get_feishu_client()
        token = await client.get_token()
        return {"status": "ok", "token": token[:20] + "..."}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


@router.get("/feishu/recent-senders")
async def get_recent_senders():
    return {"senders": _recent_senders}


# ===== Vulcan-Brain Bot Webhook =====


@router.post("/feishu/brain/webhook")
async def brain_webhook(request: Request):
    """Vulcan-Brain AI对话机器人的webhook"""
    try:
        body = await request.json()
        log(f"[Brain] 收到: {json.dumps(body, ensure_ascii=False)[:500]}")

        # URL 验证 - 返回challenge
        if body.get("challenge"):
            challenge = body.get("challenge")
            log(f"[Brain] Challenge验证: {challenge}")
            return {"challenge": challenge}

        # 消息事件
        header = body.get("header", {})
        event = body.get("event", {})

        if header.get("event_type") == "im.message.receive_v1":
            return await handle_brain_msg(event)

        # 处理机器人菜单点击事件
        if header.get("event_type") == "application.bot.menu_v6":
            return await handle_brain_menu(event)

        # 处理卡片交互事件（审批提交等）
        if header.get("event_type") == "card.action.trigger":
            return await handle_brain_card_action(event)

        return {"code": 0}
    except Exception as e:
        log(f"[Brain] 错误: {e}")
        import traceback
        traceback.print_exc()
        return {"code": 0}






async def handle_brain_card_action(event):
    """处理Brain机器人的卡片交互事件"""
    action = event.get("action", {})
    value = action.get("value", {})
    form_value = action.get("form_value", {})

    operator = event.get("operator", {})
    open_id = operator.get("open_id", "")

    # 获取action类型
    action_type = value.get("action", "") if isinstance(value, dict) else ""
    # form_submit 模式：从 action.name 或 form name 判断
    if not action_type and action.get("name") == "submit_btn":
        action_type = "bot_approval_submit"

    log(f"[Brain] 卡片操作: action={action_type}, user={open_id}, form={form_value}")

    # 审批提交
    if action_type == "bot_approval_submit":
        return await handle_approval_submit(open_id, form_value, event)

    # 审批通过
    elif action_type == "bot_approval_approve":
        approval_id = value.get("approval_id", "")
        return await handle_approval_action(approval_id, open_id, "approve", form_value)

    # 审批拒绝
    elif action_type == "bot_approval_reject":
        approval_id = value.get("approval_id", "")
        return await handle_approval_action(approval_id, open_id, "reject", form_value)

    return {"code": 0}


async def handle_approval_submit(open_id: str, form_value: dict, event: dict):
    """处理审批表单提交"""
    from services.approval_bot_service import get_approval_bot_service, build_approval_request_card

    # 获取表单数据
    approval_type = form_value.get("approval_type", "other")
    title = form_value.get("approval_title", "")
    content_text = form_value.get("approval_content", "")

    log(f"[Brain] 审批提交: type={approval_type}, title={title}, content={content_text}")

    # 获取用户信息 (简化处理，实际应该查询用户名)
    applicant_name = f"用户_{open_id[-6:]}"

    try:
        service = get_approval_bot_service()

        # 创建审批记录
        approval = await service.create_approval(
            approval_type=approval_type,
            applicant_id=open_id,
            applicant_name=applicant_name,
            form_data={
                "title": title,
                "content": content_text,
            },
            approver_ids=[],  # 暂时不指定审批人
        )

        log(f"[Brain] 审批已创建: {approval['_id']}")

        # 回复用户确认
        async with httpx.AsyncClient(timeout=30) as hc:
            resp = await hc.post(
                "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": BRAIN_APP_ID, "app_secret": BRAIN_APP_SECRET}
            )
            token = resp.json().get("tenant_access_token")

            # 发送确认消息
            confirm_card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "✅ 审批已提交"},
                    "template": "green",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**审批类型**: {approval['type_name']}\n**标题**: {title}\n**审批编号**: {approval['_id']}\n\n审批已进入流程，请等待审批结果。",
                        },
                    },
                ],
            }

            await hc.post(
                "https://open.larksuite.com/open-apis/im/v1/messages",
                params={"receive_id_type": "open_id"},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": open_id,
                    "msg_type": "interactive",
                    "content": json.dumps(confirm_card)
                }
            )
            log(f"[Brain] 审批确认已发送给 {open_id}")

    except Exception as e:
        log(f"[Brain] 审批提交失败: {e}")
        import traceback
        traceback.print_exc()

    return {"code": 0}


async def handle_approval_action(approval_id: str, approver_id: str, action: str, form_value: dict):
    """处理审批通过/拒绝"""
    from services.approval_bot_service import get_approval_bot_service, build_approval_result_card

    comment = form_value.get("comment", "")
    approver_name = f"审批人_{approver_id[-6:]}"

    try:
        service = get_approval_bot_service()

        if action == "approve":
            approval = await service.approve(approval_id, approver_id, approver_name, comment)
            result_action = "approved"
        else:
            approval = await service.reject(approval_id, approver_id, approver_name, comment)
            result_action = "rejected"

        log(f"[Brain] 审批{action}: {approval_id}")

        # 通知申请人
        applicant_id = approval.get("applicant_id", "")
        if applicant_id:
            result_card = build_approval_result_card(approval, result_action, approver_name, comment)

            async with httpx.AsyncClient(timeout=30) as hc:
                resp = await hc.post(
                    "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": BRAIN_APP_ID, "app_secret": BRAIN_APP_SECRET}
                )
                token = resp.json().get("tenant_access_token")

                await hc.post(
                    "https://open.larksuite.com/open-apis/im/v1/messages",
                    params={"receive_id_type": "open_id"},
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "receive_id": applicant_id,
                        "msg_type": "interactive",
                        "content": json.dumps(result_card)
                    }
                )
                log(f"[Brain] 审批结果已通知申请人 {applicant_id}")

    except Exception as e:
        log(f"[Brain] 审批操作失败: {e}")
        import traceback
        traceback.print_exc()

    return {"code": 0}

async def handle_brain_menu(event):
    """处理Bot菜单点击事件"""
    event_key = event.get("event_key", "")
    operator = event.get("operator", {})
    operator_id = operator.get("operator_id", {})
    open_id = operator_id.get("open_id", "")

    log(f"[Brain] 菜单点击: event_key={event_key}, user={open_id}")

    if event_key == "start_approval":
        # 发起审批 - 发送审批表单卡片
        from services.approval_bot_service import build_approval_submit_card
        card = build_approval_submit_card()

        try:
            async with httpx.AsyncClient(timeout=30) as hc:
                resp = await hc.post(
                    "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": BRAIN_APP_ID, "app_secret": BRAIN_APP_SECRET}
                )
                token = resp.json().get("tenant_access_token")

                # 发送卡片给用户（私聊）
                await hc.post(
                    "https://open.larksuite.com/open-apis/im/v1/messages",
                    params={"receive_id_type": "open_id"},
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "receive_id": open_id,
                        "msg_type": "interactive",
                        "content": json.dumps(card)
                    }
                )
                log(f"[Brain] 审批表单卡片已发送给 {open_id}")
        except Exception as e:
            log(f"[Brain] 发送审批卡片失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        log(f"[Brain] 未知菜单事件: {event_key}")

    return {"code": 0}

async def handle_brain_msg(event):
    """处理Brain机器人的消息 - AI对话（支持群聊上下文记忆）"""

    msg = event.get("message", {})
    msg_id = msg.get("message_id", "")
    chat_id = msg.get("chat_id", "")  # 群聊/私聊ID
    chat_type = msg.get("chat_type", "")  # p2p私聊 / group群聊

    if is_dup(msg_id):
        return {"code": 0}

    msg_type = msg.get("message_type", "")
    msg_content = msg.get("content", "{}")

    if msg_type == "text":
        try:
            text = json.loads(msg_content).get("text", "")
        except:
            text = msg_content
    else:
        log(f"[Brain] 非文本消息，跳过: {msg_type}")
        return {"code": 0}

    sender = event.get("sender", {})
    open_id = sender.get("sender_id", {}).get("open_id", "")

    log(f"[Brain] 用户消息: {text}, chat_id={chat_id}, chat_type={chat_type}, from={open_id}")

    # ===== 审批命令拦截 =====
    if text in ["发起审批", "/审批", "审批", "/approval"]:
        log(f"[Brain] 识别到审批命令，发送审批表单卡片")
        from services.approval_bot_service import build_approval_submit_card
        card = build_approval_submit_card()

        try:
            async with httpx.AsyncClient(timeout=30) as hc:
                resp = await hc.post(
                    "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": BRAIN_APP_ID, "app_secret": BRAIN_APP_SECRET}
                )
                token = resp.json().get("tenant_access_token")

                # 发送卡片消息
                await hc.post(
                    "https://open.larksuite.com/open-apis/im/v1/messages",
                    params={"receive_id_type": "chat_id"},
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "receive_id": chat_id,
                        "msg_type": "interactive",
                        "content": json.dumps(card)
                    }
                )
                log(f"[Brain] 审批表单卡片已发送到 {chat_id}")
        except Exception as e:
            log(f"[Brain] 发送审批卡片失败: {e}")
            import traceback
            traceback.print_exc()
        return {"code": 0}

    # ===== 消息保存已移至定时/手动采集 =====
    # 不再实时保存，由 /messages/collect API 统一采集
    # (保持数据流简洁：定时采集 -> 去重入库 -> AI分析)

    # ===== 群聊@检测: 只有被@才回复 =====
    if chat_type == "group":
        mentions = msg.get("mentions", [])
        # 检查是否@了机器人 (通过检查mentions列表)
        is_mentioned = False
        for m in mentions:
            # mentions 里有 id.open_id 或直接检查 key 是否是 @_all
            if m.get("key") == "@_all":
                is_mentioned = True
                break
            # 也可以检查 id 字段
            m_id = m.get("id", {})
            if isinstance(m_id, dict) and m_id.get("open_id"):
                is_mentioned = True
                break
            elif m.get("key", "").startswith("@_user_"):
                is_mentioned = True
                break
        
        if not is_mentioned:
            log(f"[Brain] 群聊消息未@机器人，仅保存不回复: {text[:50]}...")
            return {"code": 0}

    # 获取对话历史
    history = _chat_history[chat_id]
    
    # 添加当前用户消息
    history.append({"role": "user", "content": text})
    
    # 只保留最近的历史
    if len(history) > MAX_HISTORY * 2:
        _chat_history[chat_id] = history[-MAX_HISTORY:]
        history = _chat_history[chat_id]

    # 构建消息列表（用于多轮对话）
    messages = [{"role": h["role"], "content": h["content"]} for h in history[-MAX_HISTORY:]]

    # 调用统一AI服务（支持多轮对话）
    try:
        ai = get_ai_service()
        reply_text = await ai.chat(messages)

        if len(reply_text) > 4000:
            reply_text = reply_text[:4000] + "...(截断)"

        log(f"[Brain] AI生成回复: {reply_text[:100]}...")
        
        # 保存AI回复到历史
        history.append({"role": "assistant", "content": reply_text})

    except Exception as e:
        log(f"[Brain] AI调用失败: {e}")
        reply_text = f"AI处理出错: {str(e)[:100]}"

    # 发送回复
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": BRAIN_APP_ID, "app_secret": BRAIN_APP_SECRET}
            )
            token = resp.json().get("tenant_access_token")

            # 根据聊天类型选择回复方式
            if chat_type == "group":
                # 群聊：回复消息
                await client.post(
                    f"https://open.larksuite.com/open-apis/im/v1/messages/{msg_id}/reply",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "msg_type": "text",
                        "content": json.dumps({"text": reply_text})
                    }
                )
            else:
                # 私聊：直接发送
                await client.post(
                    "https://open.larksuite.com/open-apis/im/v1/messages",
                    params={"receive_id_type": "open_id"},
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "receive_id": open_id,
                        "msg_type": "text",
                        "content": json.dumps({"text": reply_text})
                    }
                )
            log(f"[Brain] 已回复 chat_id={chat_id}")
    except Exception as e:
        log(f"[Brain] 发送回复失败: {e}")

    return {"code": 0}

    msg_type = msg.get("message_type", "")
    msg_content = msg.get("content", "{}")

    if msg_type == "text":
        try:
            text = json.loads(msg_content).get("text", "")
        except:
            text = msg_content
    else:
        log(f"[Brain] 非文本消息，跳过: {msg_type}")
        return {"code": 0}

    sender = event.get("sender", {})
    open_id = sender.get("sender_id", {}).get("open_id", "")

    log(f"[Brain] 用户消息: {text}, from={open_id}")

    # 调用统一AI服务
    try:
        ai = get_ai_service()
        reply_text = await ai.generate(text)

        if len(reply_text) > 4000:
            reply_text = reply_text[:4000] + "...(截断)"

        log(f"[Brain] AI生成回复: {reply_text[:100]}...")

    except Exception as e:
        log(f"[Brain] AI调用失败: {e}")
        reply_text = f"AI处理出错: {str(e)[:100]}"

    # 发送回复
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": BRAIN_APP_ID, "app_secret": BRAIN_APP_SECRET}
            )
            token = resp.json().get("tenant_access_token")

            await client.post(
                "https://open.larksuite.com/open-apis/im/v1/messages",
                params={"receive_id_type": "open_id"},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": open_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": reply_text})
                }
            )
            log(f"[Brain] 已回复用户 {open_id}")
    except Exception as e:
        log(f"[Brain] 发送回复失败: {e}")

    return {"code": 0}
