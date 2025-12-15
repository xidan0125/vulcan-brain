#!/usr/bin/env python3
"""
添加飞书调度器启动代码到 api_server.py
"""

# 读取文件
with open('/home/xinyue/vulcan-brain/api_server.py', 'r') as f:
    content = f.read()

# 找到启动事件代码
old_startup = '''# 启动初始化：数据库索引
@app.on_event("startup")
async def initialize_app():
    try:
        await store.initialize_indexes()
        api_logger.info("[Startup] MongoDB indexes initialized")
    except Exception as e:
        log_error(e, "startup.initialize_indexes")'''

new_startup = '''# 启动初始化：数据库索引 + 飞书调度器
@app.on_event("startup")
async def initialize_app():
    try:
        await store.initialize_indexes()
        api_logger.info("[Startup] MongoDB indexes initialized")
    except Exception as e:
        log_error(e, "startup.initialize_indexes")

    # 启动飞书定时任务调度器
    try:
        from feishu import start_scheduler
        import asyncio
        asyncio.create_task(start_scheduler())
        api_logger.info("[Startup] Feishu scheduler started")
    except Exception as e:
        api_logger.warning(f"[Startup] Feishu scheduler failed: {e}")'''

if old_startup in content:
    content = content.replace(old_startup, new_startup)
    with open('/home/xinyue/vulcan-brain/api_server.py', 'w') as f:
        f.write(content)
    print("SUCCESS: 调度器启动代码已添加")
else:
    print("WARNING: 未找到目标代码段")
