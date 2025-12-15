#!/usr/bin/env python3
"""深入分析V2数据质量"""
import pymongo
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client.vulcan_brain

print("=== V2数据结构 ===")
sample = db.v2_entities.find_one()
print(f"字段: {list(sample.keys())}")
print(f"entities字段样本: {sample.get('entities', [])[:2]}")

print("\n=== V2整体type分布 ===")
type_counts = {}
total = 0
for doc in db.v2_entities.find():
    for e in doc.get("entities", []):
        if isinstance(e, dict):
            t = e.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
            total += 1

for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c} ({100*c//total}%)")

print(f"\n总实体数: {total}")

print("\n=== 分析：同一个text被标记为多种type的情况 ===")
# 收集每个text的type分布
text_types = {}
for doc in db.v2_entities.find():
    for e in doc.get("entities", []):
        if isinstance(e, dict):
            text = e.get("text", "").strip()
            t = e.get("type", "unknown")
            if text:
                if text not in text_types:
                    text_types[text] = {}
                text_types[text][t] = text_types[text].get(t, 0) + 1

# 找出被标记为多种type的实体
ambiguous = []
for text, types in text_types.items():
    if len(types) > 1:
        total_count = sum(types.values())
        if total_count >= 10:  # 只看高频的
            ambiguous.append((text, types, total_count))

ambiguous.sort(key=lambda x: -x[2])

print(f"被标记为多种type的高频实体 (≥10次): {len(ambiguous)}")
print("\nTop 20:")
for text, types, total in ambiguous[:20]:
    types_str = ", ".join([f"{t}:{c}" for t, c in sorted(types.items(), key=lambda x:-x[1])])
    print(f"  [{total:5d}] '{text[:30]}' -> {types_str}")

print("\n=== 结论：V2数据质量分析 ===")
# 计算歧义率
high_freq_texts = [t for t, types in text_types.items() if sum(types.values()) >= 10]
ambiguous_high_freq = [t for t, types in text_types.items() if len(types) > 1 and sum(types.values()) >= 10]
print(f"高频实体(≥10次): {len(high_freq_texts)}")
print(f"其中有歧义的: {len(ambiguous_high_freq)} ({100*len(ambiguous_high_freq)//len(high_freq_texts)}%)")
