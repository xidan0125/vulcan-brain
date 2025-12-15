#!/usr/bin/env python3
"""Add approval API router to api_server.py"""

with open("/home/xinyue/vulcan-brain/api_server.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add after email_api import
old_code = '''    from email_api import router as email_router
    app.include_router(email_router, prefix="/api", tags=["Email"])'''

new_code = '''    from email_api import router as email_router
    app.include_router(email_router, prefix="/api", tags=["Email"])

# === 审批模块 ===
try:
    from approval_api import router as approval_router
    app.include_router(approval_router, tags=["Approval"])
    print("✅ 审批模块已加载")
except Exception as e:
    print(f"❌ 审批模块加载失败: {e}")'''

if old_code in content and "approval_api" not in content:
    content = content.replace(old_code, new_code)
    print("✅ 添加审批路由成功")
else:
    if "approval_api" in content:
        print("⚠️ 审批路由已存在")
    else:
        print("❌ 未找到插入点")

with open("/home/xinyue/vulcan-brain/api_server.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Done!")
