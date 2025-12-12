#!/usr/bin/env python3
"""
更新 api_server.py 添加新飞书模块
"""

import re

# 读取文件
with open('/home/xinyue/vulcan-brain/api_server.py', 'r') as f:
    content = f.read()

# 找到飞书模块部分并替换
old_feishu_section = '''# ==================== 飞书机器人模块 ====================

try:
    from feishu_api import router as feishu_router
    app.include_router(feishu_router, prefix="/api", tags=["Feishu"])
    print("[INFO] 飞书 API 模块已加载")
except ImportError as e:
    print(f"[WARNING] 飞书 API 模块加载失败: {e}")'''

new_feishu_section = '''# ==================== 飞书机器人模块 ====================

# 新版飞书模块 (重构后)
try:
    from feishu import feishu_router as new_feishu_router
    app.include_router(new_feishu_router, tags=["Feishu-V2"])
    print("[INFO] 飞书 V2 模块已加载 (新架构)")
except ImportError as e:
    print(f"[WARNING] 飞书 V2 模块加载失败: {e}")

# 旧版飞书模块 (兼容)
try:
    from feishu_api import router as feishu_router
    app.include_router(feishu_router, prefix="/api", tags=["Feishu"])
    print("[INFO] 飞书旧版模块已加载 (兼容)")
except ImportError as e:
    print(f"[WARNING] 飞书旧版模块加载失败: {e}")'''

if old_feishu_section in content:
    content = content.replace(old_feishu_section, new_feishu_section)
    with open('/home/xinyue/vulcan-brain/api_server.py', 'w') as f:
        f.write(content)
    print("SUCCESS: api_server.py 已更新")
else:
    print("WARNING: 未找到目标代码段，请手动更新")
