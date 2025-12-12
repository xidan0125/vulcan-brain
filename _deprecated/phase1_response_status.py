#!/usr/bin/env python3
"""
Phase 1: 实现三层状态模型
- Layer 1: lifecycle_status (单值) - pending → in_progress → completed
- Layer 2: response_status (数组) - 支持复合状态如 ["accepted", "blocked"]
- Layer 3: health (派生) - 根据 response_status 计算

互斥规则:
- on_track, at_risk, blocked 互斥（只能存在一个）
- accepted 会持续存在除非 rejected
"""

import re

# ===== 1. 修改 pm_api.py =====
with open("/home/xinyue/vulcan-brain/pm_api.py", "r") as f:
    pm_content = f.read()

# 修改任务创建时的字段
old_feedback = '''        # 反馈系统字段
        "feedback_status": "no_response",  # no_response/accepted/questioned/rejected/on_track/at_risk/blocked
        "feedback_at": None,
        "feedback_note": None,'''

new_feedback = '''        # 三层状态模型
        "lifecycle_status": "pending",  # Layer 1: pending → in_progress → completed
        "response_status": [],  # Layer 2: 数组，支持复合状态 ["accepted", "blocked"]
        "response_at": None,
        "response_notes": [],  # 备注历史'''

if old_feedback in pm_content:
    pm_content = pm_content.replace(old_feedback, new_feedback)
    print("✅ pm_api.py: 任务创建字段已更新")
else:
    print("❌ pm_api.py: 未找到旧字段定义")

with open("/home/xinyue/vulcan-brain/pm_api.py", "w") as f:
    f.write(pm_content)


# ===== 2. 创建状态管理帮助函数 =====
helper_code = '''
# ==================== 状态管理帮助函数 ====================

def update_response_status(current: list, new_status: str, note: str = "") -> tuple:
    """
    更新 response_status 数组，遵循互斥规则
    返回: (updated_array, note_entry)

    规则:
    1. on_track, at_risk, blocked 三者互斥
    2. accepted 持续存在除非 rejected
    3. questioned 可以与其他状态共存
    """
    from datetime import datetime

    result = current.copy() if current else []

    # 互斥组
    health_states = {"on_track", "at_risk", "blocked"}
    acceptance_states = {"accepted", "rejected"}

    # 如果新状态在健康组，移除其他健康状态
    if new_status in health_states:
        result = [s for s in result if s not in health_states]

    # 如果是 rejected，移除 accepted
    if new_status == "rejected":
        result = [s for s in result if s != "accepted"]

    # 如果是 accepted，移除 rejected
    if new_status == "accepted":
        result = [s for s in result if s != "rejected"]

    # 添加新状态（如果不存在）
    if new_status not in result:
        result.append(new_status)

    # 创建备注条目
    note_entry = {
        "status": new_status,
        "note": note,
        "at": datetime.now().isoformat()
    }

    return result, note_entry


def calculate_health(response_status: list) -> str:
    """
    根据 response_status 数组计算 health 状态
    返回: "healthy" | "at_risk" | "blocked" | "no_response"
    """
    if not response_status:
        return "no_response"

    # 优先级: blocked > at_risk > on_track > accepted > questioned
    if "blocked" in response_status:
        return "blocked"
    if "at_risk" in response_status:
        return "at_risk"
    if "on_track" in response_status:
        return "healthy"
    if "accepted" in response_status:
        return "healthy"
    if "questioned" in response_status:
        return "at_risk"
    if "rejected" in response_status:
        return "blocked"

    return "no_response"

'''

# 在 pm_api.py 中添加帮助函数（在 router 定义之前）
with open("/home/xinyue/vulcan-brain/pm_api.py", "r") as f:
    pm_content = f.read()

# 找到 router 定义的位置
router_marker = "router = APIRouter(prefix=\"/api/pm\""
if router_marker in pm_content and "def update_response_status" not in pm_content:
    pm_content = pm_content.replace(router_marker, helper_code + "\n" + router_marker)
    print("✅ pm_api.py: 帮助函数已添加")

with open("/home/xinyue/vulcan-brain/pm_api.py", "w") as f:
    f.write(pm_content)


# ===== 3. 修改 feishu_api.py 的回调处理 =====
with open("/home/xinyue/vulcan-brain/feishu_api.py", "r") as f:
    feishu_content = f.read()

# 在文件顶部添加 import
if "from pm_api import update_response_status" not in feishu_content:
    # 在 from datetime import datetime 后面添加
    old_import = "from datetime import datetime"
    new_import = """from datetime import datetime

# 状态管理函数
def update_response_status(current: list, new_status: str, note: str = "") -> tuple:
    \"\"\"更新 response_status 数组，遵循互斥规则\"\"\"
    result = current.copy() if current else []
    health_states = {"on_track", "at_risk", "blocked"}
    if new_status in health_states:
        result = [s for s in result if s not in health_states]
    if new_status == "rejected":
        result = [s for s in result if s != "accepted"]
    if new_status == "accepted":
        result = [s for s in result if s != "rejected"]
    if new_status not in result:
        result.append(new_status)
    note_entry = {"status": new_status, "note": note, "at": datetime.now().isoformat()}
    return result, note_entry"""

    if old_import in feishu_content:
        feishu_content = feishu_content.replace(old_import, new_import)
        print("✅ feishu_api.py: 帮助函数已添加")


# 修改 accept 回调
old_accept = '''    if action_type == "accept":
        now = datetime.now().isoformat()
        await store.update_task(task_id, {
            "status": "in_progress",
            "feedback_status": "accepted",
            "feedback_at": now,
            "feedback_note": notes if notes else "已确认接收任务"
        })
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "in_progress",
            "notes": notes if notes else "已确认接收任务"
        })
        return {"toast": {"type": "success", "content": "✅ 任务已确认，开始处理！"}}'''

new_accept = '''    if action_type == "accept":
        # 获取当前任务状态
        task = await store.get_task(task_id)
        current_response = task.get("response_status", []) if task else []

        # 更新状态数组
        new_response, note_entry = update_response_status(current_response, "accepted", notes if notes else "已确认接收任务")

        await store.update_task(task_id, {
            "lifecycle_status": "in_progress",
            "response_status": new_response,
            "response_at": datetime.now().isoformat(),
            "response_notes": (task.get("response_notes", []) if task else []) + [note_entry]
        })
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "in_progress",
            "notes": notes if notes else "已确认接收任务"
        })
        return {"toast": {"type": "success", "content": "✅ 任务已确认，开始处理！"}}'''

if old_accept in feishu_content:
    feishu_content = feishu_content.replace(old_accept, new_accept)
    print("✅ feishu_api.py: accept 回调已更新")


# 修改 submit_question 回调
old_question = '''    elif action_type == "submit_question":
        form_value = action.get("form_value", {})
        question_text = form_value.get("question_text", "")
        now = datetime.now().isoformat()
        await store.update_task(task_id, {
            "feedback_status": "questioned",
            "feedback_at": now,
            "feedback_note": question_text
        })
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "question",
            "notes": f"疑问: {question_text}"
        })
        return {"toast": {"type": "success", "content": "✅ 疑问已提交，等待回复"}}'''

new_question = '''    elif action_type == "submit_question":
        form_value = action.get("form_value", {})
        question_text = form_value.get("question_text", "")

        task = await store.get_task(task_id)
        current_response = task.get("response_status", []) if task else []
        new_response, note_entry = update_response_status(current_response, "questioned", question_text)

        await store.update_task(task_id, {
            "response_status": new_response,
            "response_at": datetime.now().isoformat(),
            "response_notes": (task.get("response_notes", []) if task else []) + [note_entry]
        })
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "question",
            "notes": f"疑问: {question_text}"
        })
        return {"toast": {"type": "success", "content": "✅ 疑问已提交，等待回复"}}'''

if old_question in feishu_content:
    feishu_content = feishu_content.replace(old_question, new_question)
    print("✅ feishu_api.py: question 回调已更新")


# 修改 on_track 回调
old_ontrack = '''    elif action_type == "on_track":
        now = datetime.now().isoformat()
        await store.update_task(task_id, {
            "feedback_status": "on_track",
            "feedback_at": now,
            "feedback_note": notes if notes else "进展顺利"
        })
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "on_track",
            "notes": notes if notes else "进展顺利"
        })
        return {"toast": {"type": "success", "content": "🟢 已记录：一切正常"}}'''

new_ontrack = '''    elif action_type == "on_track":
        task = await store.get_task(task_id)
        current_response = task.get("response_status", []) if task else []
        new_response, note_entry = update_response_status(current_response, "on_track", notes if notes else "进展顺利")

        await store.update_task(task_id, {
            "response_status": new_response,
            "response_at": datetime.now().isoformat(),
            "response_notes": (task.get("response_notes", []) if task else []) + [note_entry]
        })
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "on_track",
            "notes": notes if notes else "进展顺利"
        })
        return {"toast": {"type": "success", "content": "🟢 已记录：一切正常"}}'''

if old_ontrack in feishu_content:
    feishu_content = feishu_content.replace(old_ontrack, new_ontrack)
    print("✅ feishu_api.py: on_track 回调已更新")


# 修改 need_time (at_risk) 回调
old_needtime = '''    elif action_type == "need_time":
        now = datetime.now().isoformat()
        await store.update_task(task_id, {
            "status": "at_risk",
            "feedback_status": "at_risk",
            "feedback_at": now,
            "feedback_note": notes if notes else "需要更多时间"
        })
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "at_risk",
            "notes": notes if notes else "需要更多时间"
        })
        return {"toast": {"type": "warning", "content": "🟡 已记录延期"}}'''

new_needtime = '''    elif action_type == "need_time":
        task = await store.get_task(task_id)
        current_response = task.get("response_status", []) if task else []
        new_response, note_entry = update_response_status(current_response, "at_risk", notes if notes else "需要更多时间")

        await store.update_task(task_id, {
            "response_status": new_response,
            "response_at": datetime.now().isoformat(),
            "response_notes": (task.get("response_notes", []) if task else []) + [note_entry]
        })
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "at_risk",
            "notes": notes if notes else "需要更多时间"
        })
        return {"toast": {"type": "warning", "content": "🟡 已记录延期"}}'''

if old_needtime in feishu_content:
    feishu_content = feishu_content.replace(old_needtime, new_needtime)
    print("✅ feishu_api.py: need_time 回调已更新")


# 修改 blocked 回调
old_blocked = '''    elif action_type == "blocked":
        now = datetime.now().isoformat()
        await store.update_task(task_id, {
            "status": "blocked",
            "feedback_status": "blocked",
            "feedback_at": now,
            "feedback_note": notes if notes else "遇到阻塞"
        })
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "blocked",
            "notes": notes if notes else "遇到阻塞"
        })
        return {"toast": {"type": "error", "content": "🔴 已记录阻塞"}}'''

new_blocked = '''    elif action_type == "blocked":
        task = await store.get_task(task_id)
        current_response = task.get("response_status", []) if task else []
        new_response, note_entry = update_response_status(current_response, "blocked", notes if notes else "遇到阻塞")

        await store.update_task(task_id, {
            "response_status": new_response,
            "response_at": datetime.now().isoformat(),
            "response_notes": (task.get("response_notes", []) if task else []) + [note_entry]
        })
        await store.add_report({
            "task_id": task_id,
            "reporter_feishu_id": open_id,
            "status": "blocked",
            "notes": notes if notes else "遇到阻塞"
        })
        return {"toast": {"type": "error", "content": "🔴 已记录阻塞"}}'''

if old_blocked in feishu_content:
    feishu_content = feishu_content.replace(old_blocked, new_blocked)
    print("✅ feishu_api.py: blocked 回调已更新")


with open("/home/xinyue/vulcan-brain/feishu_api.py", "w") as f:
    f.write(feishu_content)


# ===== 4. 创建数据迁移脚本 =====
migration_script = '''#!/usr/bin/env python3
"""迁移现有任务数据到新的三层状态模型"""

from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["vulcan_brain"]
tasks = db["pm_tasks"]

# 状态映射
status_map = {
    "no_response": [],
    "accepted": ["accepted"],
    "questioned": ["questioned"],
    "rejected": ["rejected"],
    "on_track": ["accepted", "on_track"],
    "at_risk": ["accepted", "at_risk"],
    "blocked": ["accepted", "blocked"]
}

count = 0
for task in tasks.find({"feedback_status": {"$exists": True}}):
    old_status = task.get("feedback_status", "no_response")
    old_note = task.get("feedback_note", "")
    old_at = task.get("feedback_at")

    new_response = status_map.get(old_status, [])

    # 构建 response_notes
    response_notes = []
    if old_note and old_at:
        response_notes.append({
            "status": old_status,
            "note": old_note,
            "at": old_at
        })

    # 确定 lifecycle_status
    task_status = task.get("status", "pending")
    if task_status == "completed":
        lifecycle = "completed"
    elif "accepted" in new_response or task_status == "in_progress":
        lifecycle = "in_progress"
    else:
        lifecycle = "pending"

    # 更新任务
    tasks.update_one(
        {"_id": task["_id"]},
        {
            "$set": {
                "lifecycle_status": lifecycle,
                "response_status": new_response,
                "response_at": old_at,
                "response_notes": response_notes
            },
            "$unset": {
                "feedback_status": "",
                "feedback_at": "",
                "feedback_note": ""
            }
        }
    )
    count += 1
    print(f"  迁移: {task.get('title', 'unknown')}: {old_status} -> {new_response}")

print(f"\\n✅ 共迁移 {count} 个任务")
'''

with open("/home/xinyue/vulcan-brain/migrate_task_status.py", "w") as f:
    f.write(migration_script)
print("✅ 数据迁移脚本已创建: migrate_task_status.py")


print("\n" + "="*50)
print("Phase 1 后端修改完成！")
print("="*50)
print("\n下一步:")
print("1. 运行迁移脚本: python3 migrate_task_status.py")
print("2. 重启后端: pm2 restart vulcan-backend")
print("3. 更新前端显示逻辑")
