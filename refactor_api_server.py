
import os

API_SERVER_PATH = os.path.expanduser("~/vulcan-brain/api_server.py")

with open(API_SERVER_PATH, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip_mode = False
has_inserted_new_routers = False

# Marker for where the legacy imports start (approximately)
# We look for "from auth_api import" or similar legacy patterns to start skipping
# But we need to keep the "startup" and "middleware" parts which are at the top.

# Strategy: 
# 1. Keep everything until we hit the "# ==================== 已有独立模块 ====================" or first legacy import.
# 2. Skip everything until `if __name__ == '__main__':` or End of File.
# 3. But wait, `if __name__` is at the bottom. We need to preserve it.

start_marker = "# ==================== 已有独立模块 ===================="
end_marker = "# ==================== 启动入口 ===================="

for line in lines:
    if start_marker in line:
        skip_mode = True
        new_lines.append(line)
        # Insert new imports here
        new_lines.append("\n# [Refactored] Consolidated Routers\n")
        new_lines.append("from api.routers.auth_router import router as auth_router\n")
        new_lines.append("from api.routers.chat_router import router as chat_router\n")
        new_lines.append("from api.routers.legacy_chat_router import router as legacy_chat_router\n")
        new_lines.append("from api.routers.mcp_router import router as mcp_router\n")
        new_lines.append("# soul_router is already imported above as soul_router_new\n")
        new_lines.append("from api.routers.project_router import router as pm_router\n")
        new_lines.append("from api.routers.message_router import router as message_router\n")
        new_lines.append("from api.routers.info_hub_router import router as info_hub_router\n")
        new_lines.append("from api.routers.email_router import router as email_router\n")
        new_lines.append("from api.routers.email_intel_router import router as email_intel_router\n")
        new_lines.append("from api.routers.approval_router import router as approval_router\n")
        new_lines.append("from api.routers.memory_v3_router import router as memory_v3_router\n")
        new_lines.append("from api.routers.monitor_router import router as monitor_router\n")
        
        new_lines.append("\n# Mounts\n")
        new_lines.append("app.include_router(auth_router, prefix='/api')\n")
        new_lines.append("app.include_router(chat_router, prefix='/api', tags=['Unified Chat'])\n")
        new_lines.append("app.include_router(legacy_chat_router, prefix='/api', tags=['Legacy Chat'])\n")
        new_lines.append("app.include_router(mcp_router, prefix='/api')\n")
        new_lines.append("app.include_router(pm_router, tags=['Project Management'])\n")
        new_lines.append("app.include_router(message_router, prefix='/api', tags=['Messages'])\n")
        new_lines.append("app.include_router(info_hub_router, prefix='/api', tags=['InfoHub'])\n")
        new_lines.append("app.include_router(email_router, prefix='/api', tags=['Email'])\n")
        new_lines.append("app.include_router(email_intel_router, prefix='/api', tags=['Email Intel'])\n")
        new_lines.append("app.include_router(approval_router, prefix='/api', tags=['Approval'])\n")
        new_lines.append("app.include_router(memory_v3_router, prefix='/api', tags=['Memory v3'])\n")
        new_lines.append("app.include_router(monitor_router, prefix='/api', tags=['V3 Monitor'])\n")
        new_lines.append("\n")
        continue
    
    if end_marker in line:
        skip_mode = False
    
    if not skip_mode:
        new_lines.append(line)

with open(API_SERVER_PATH, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Successfully refactored api_server.py")
