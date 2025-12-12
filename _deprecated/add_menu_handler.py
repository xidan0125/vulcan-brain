#!/usr/bin/env python3
"""Add bot menu event handler to Brain bot webhook"""

with open("/home/xinyue/vulcan-brain/feishu_api.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the brain_webhook function and add menu event handling
old_code = '''        if header.get("event_type") == "im.message.receive_v1":
            return await handle_brain_msg(event)

        return {"code": 0}
    except Exception as e:
        log(f"[Brain] 错误: {e}")'''

new_code = '''        if header.get("event_type") == "im.message.receive_v1":
            return await handle_brain_msg(event)

        # 处理机器人菜单点击事件
        if header.get("event_type") == "application.bot.menu_v6":
            return await handle_brain_menu(event)

        return {"code": 0}
    except Exception as e:
        log(f"[Brain] 错误: {e}")'''

if old_code in content:
    content = content.replace(old_code, new_code)
    print("✅ 添加菜单事件路由成功")
else:
    print("❌ 未找到插入点1")

# Now add the handle_brain_menu function after handle_brain_msg function
# Find a good insertion point - after the brain_webhook function's return
menu_handler = '''

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

'''

# Insert before the line "async def handle_brain_msg"
if "async def handle_brain_msg(event):" in content and "async def handle_brain_menu" not in content:
    content = content.replace(
        "async def handle_brain_msg(event):",
        menu_handler + "async def handle_brain_msg(event):"
    )
    print("✅ 添加菜单处理函数成功")
else:
    if "async def handle_brain_menu" in content:
        print("⚠️ 菜单处理函数已存在")
    else:
        print("❌ 未找到插入点2")

with open("/home/xinyue/vulcan-brain/feishu_api.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Done!")
