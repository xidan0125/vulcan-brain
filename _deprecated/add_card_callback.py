#!/usr/bin/env python3
"""Add card action callback handler for Brain bot"""

with open("/home/xinyue/vulcan-brain/feishu_api.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add card action handling to brain_webhook
old_code = '''        # 处理机器人菜单点击事件
        if header.get("event_type") == "application.bot.menu_v6":
            return await handle_brain_menu(event)

        return {"code": 0}'''

new_code = '''        # 处理机器人菜单点击事件
        if header.get("event_type") == "application.bot.menu_v6":
            return await handle_brain_menu(event)

        # 处理卡片交互事件（审批提交等）
        if header.get("event_type") == "card.action.trigger":
            return await handle_brain_card_action(event)

        return {"code": 0}'''

if old_code in content:
    content = content.replace(old_code, new_code)
    print("✅ 添加卡片事件路由成功")
else:
    print("❌ 未找到插入点1")

# Add the card action handler function
card_handler = '''

async def handle_brain_card_action(event):
    """处理Brain机器人的卡片交互事件"""
    action = event.get("action", {})
    value = action.get("value", {})
    form_value = action.get("form_value", {})

    operator = event.get("operator", {})
    open_id = operator.get("open_id", "")

    # 获取action类型
    action_type = value.get("action", "") if isinstance(value, dict) else ""

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
    title = form_value.get("title", "")
    content_text = form_value.get("content", "")

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
                            "content": f"**审批类型**: {approval['type_name']}\\n**标题**: {title}\\n**审批编号**: {approval['_id']}\\n\\n审批已进入流程，请等待审批结果。",
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

'''

# Insert before handle_brain_menu
if "async def handle_brain_menu(event):" in content and "async def handle_brain_card_action" not in content:
    content = content.replace(
        "async def handle_brain_menu(event):",
        card_handler + "async def handle_brain_menu(event):"
    )
    print("✅ 添加卡片处理函数成功")
else:
    if "async def handle_brain_card_action" in content:
        print("⚠️ 卡片处理函数已存在")
    else:
        print("❌ 未找到插入点2")

with open("/home/xinyue/vulcan-brain/feishu_api.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Done!")
