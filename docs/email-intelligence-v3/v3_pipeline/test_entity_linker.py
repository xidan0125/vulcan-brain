#!/usr/bin/env python3
"""测试Entity Linker"""
import pymongo
import re

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client.vulcan_brain

def find_entity(name, entity_type=None):
    """简单的实体链接器 - O(1)查询"""
    # 先精确匹配
    query = {"$or": [
        {"canonical_name": name},
        {"aliases": name},
    ]}
    if entity_type:
        query["type"] = entity_type

    result = db.entities_v3.find_one(query)
    if result:
        return result, "exact"

    # 再忽略大小写匹配
    pattern = f"^{re.escape(name)}$"
    query = {"$or": [
        {"canonical_name": {"$regex": pattern, "$options": "i"}},
        {"aliases": {"$regex": pattern, "$options": "i"}},
    ]}
    if entity_type:
        query["type"] = entity_type

    result = db.entities_v3.find_one(query)
    if result:
        return result, "case-insensitive"

    return None, None

print("=== 测试Entity Linker ===\n")
test_cases = [
    ("VSG", "COMPANY"),
    ("vulcan shield", "COMPANY"),
    ("VULCAN SHEILD", "COMPANY"),
    ("Barry", "PERSON"),
    ("barry claypool", "PERSON"),
    ("Microsoft", "COMPANY"),
    ("SpaceX", "COMPANY"),
    ("space x", "COMPANY"),
    ("随便一个不存在的", "COMPANY"),
    ("DHL", "COMPANY"),
    ("Sheng Kai", "COMPANY"),
]

for name, etype in test_cases:
    result, match_type = find_entity(name, etype)
    if result:
        print(f"✅ '{name}' -> {result['canonical_name']} [{match_type}]")
    else:
        print(f"❌ '{name}' -> NOT FOUND")
