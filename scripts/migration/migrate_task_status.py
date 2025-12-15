#!/usr/bin/env python3
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

print(f"\n✅ 共迁移 {count} 个任务")
