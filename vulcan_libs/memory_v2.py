"""
Vulcan Brain - MongoDB 记忆系统
"""
from datetime import datetime
from typing import Dict, List
from pymongo import MongoClient

mongo_client = MongoClient("mongodb://localhost:27017")
db = mongo_client["vulcan_brain"]
memories_col = db["memories"]

class VulcanMemoryV2:
    def __init__(self, user_id="default"):
        self.user_id = user_id

    def remember(self, key, value, category="general"):
        memories_col.update_one(
            {"user_id": self.user_id, "key": key},
            {"$set": {"user_id": self.user_id, "key": key, "value": value, "category": category, "updated_at": datetime.now()},
             "$setOnInsert": {"created_at": datetime.now()}},
            upsert=True
        )
        return f"✅ 已记住: {key} = {value}"

    def recall(self, key):
        doc = memories_col.find_one({"user_id": self.user_id, "key": key})
        return doc["value"] if doc else f"❌ 没有「{key}」的记忆"

    def forget(self, key):
        r = memories_col.delete_one({"user_id": self.user_id, "key": key})
        return f"✅ 已忘记: {key}" if r.deleted_count else f"❌ 没找到: {key}"

    def get_all_memories(self):
        docs = list(memories_col.find({"user_id": self.user_id}))
        if not docs: return "【暂无记忆】"
        return "\n".join([f"- {d['key']}: {d['value']}" for d in docs])

    def search(self, query, limit=5):
        return list(memories_col.find({
            "user_id": self.user_id,
            "$or": [{"key": {"$regex": query, "$options": "i"}}, {"value": {"$regex": query, "$options": "i"}}]
        }).limit(limit))

# 便捷函数
_mgr = None
def get_manager(user_id="default"):
    global _mgr
    if _mgr is None: _mgr = VulcanMemoryV2(user_id)
    return _mgr

def remember(key, value): return get_manager().remember(key, value)
def recall(key): return get_manager().recall(key)
def get_all_memories(): return get_manager().get_all_memories()
def forget(key): return get_manager().forget(key)

if __name__ == "__main__":
    memories_col.delete_many({"user_id": "test"})
    m = VulcanMemoryV2("test")
    print(m.remember("name", "张三"))
    print(m.remember("job", "AI工程师"))
    print(f"回忆name: {m.recall('name')}")
    print(f"所有记忆:\n{m.get_all_memories()}")
