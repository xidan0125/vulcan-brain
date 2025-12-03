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

        return {"code": 0}
    except Exception as e:
        log(f"[Brain] 错误: {e}")
        import traceback
        traceback.print_exc()
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
