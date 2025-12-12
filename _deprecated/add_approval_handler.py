#!/usr/bin/env python3
"""Add approval keyword handler to Brain bot"""

with open("/home/xinyue/vulcan-brain/feishu_api.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the insertion point - after the log line in handle_brain_msg
old_code = '''    log(f"[Brain] 用户消息: {text}, chat_id={chat_id}, chat_type={chat_type}, from={open_id}")

    # ===== 消息保存已移至定时/手动采集 ====='''

new_code = '''    log(f"[Brain] 用户消息: {text}, chat_id={chat_id}, chat_type={chat_type}, from={open_id}")

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

    # ===== 消息保存已移至定时/手动采集 ====='''

if old_code in content:
    content = content.replace(old_code, new_code)
    print("✅ 添加审批命令处理成功")
else:
    print("❌ 未找到插入点")

with open("/home/xinyue/vulcan-brain/feishu_api.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Done!")
