#!/usr/bin/env python3
"""检查实体ID结构"""
import pymongo
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client.vulcan_brain

# 查Vulcan主实体
doc = db.entities_v3.find_one({"canonical_name": "Vulcan Shield Global Pte."})
print("=== Vulcan Shield Global Pte. 完整结构 ===")
print(f"_id: {doc['_id']}")
print(f"entity_id: {doc['entity_id']}")
print(f"type: {doc['type']}")
print(f"canonical_name: {doc['canonical_name']}")
print(f"normalized_key: {doc['normalized_key']}")
print(f"aliases数量: {len(doc.get('aliases', []))}")
print(f"mention_count: {doc['stats']['mention_count']}")

print("\n=== 检查：搜VSG能否找到这个entity_id ===")
# 模拟Entity Linker
test_names = ["VSG", "vulcanshield", "VULCAN SHEILD", "Vulcan Shield"]
target_id = doc['entity_id']

for name in test_names:
    result = db.entities_v3.find_one({
        "$or": [
            {"canonical_name": name},
            {"aliases": name}
        ]
    })
    if result and result['entity_id'] == target_id:
        print(f"✅ '{name}' -> {target_id}")
    elif result:
        print(f"⚠️ '{name}' -> {result['entity_id']} (不同实体!)")
    else:
        print(f"❌ '{name}' -> 找不到")

print("\n=== 是否还有独立的Vulcan/VSG实体？ ===")
count = 0
for d in db.entities_v3.find({"type": "COMPANY"}):
    name_lower = d['canonical_name'].lower()
    if 'vulcan' in name_lower or name_lower == 'vsg':
        count += 1
        print(f"[{d['entity_id']}] {d['canonical_name']}")

print(f"\n共 {count} 个Vulcan/VSG相关COMPANY实体")
