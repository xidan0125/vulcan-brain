#!/usr/bin/env python3
"""导出高频实体名册，供AI聚类使用"""
import pymongo
import json
from collections import defaultdict

client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client.vulcan_brain

print('='*60)
print('📋 导出高频实体名册')
print('='*60)

# 聚合所有实体文本及其频次（忽略type）
entity_freq = defaultdict(int)

for doc in db.v2_entities.find():
    for e in doc.get('entities', []):
        if isinstance(e, dict):
            text = e.get('text', '').strip()
            etype = e.get('type', '')
            if etype in ['company', 'person', 'product', 'location'] and len(text) >= 2:
                entity_freq[text] += 1

print(f'总共 {len(entity_freq)} 个唯一实体文本')

# 过滤≥3次
high_freq = {k: v for k, v in entity_freq.items() if v >= 3}
print(f'高频实体(≥3次): {len(high_freq)}')

# 按频次排序
sorted_entities = sorted(high_freq.items(), key=lambda x: -x[1])

# 导出到文件
output = {
    'total': len(sorted_entities),
    'entities': [{'name': name, 'count': count} for name, count in sorted_entities]
}

with open('/tmp/entity_roster.json', 'w') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'已导出到 /tmp/entity_roster.json')

# 显示前50个
print('\n=== Top 50 高频实体 ===')
for i, (name, count) in enumerate(sorted_entities[:50], 1):
    print(f'{i:3d}. [{count:5d}] {name[:50]}')

# 按类型粗略统计（基于关键词）
print('\n=== 需要重点聚类的实体 ===')
keywords = {
    'vulcan/vsg': ['vulcan', 'vsg'],
    'barry': ['barry'],
    'david': ['david'],
    'microsoft': ['microsoft'],
    'spacex': ['spacex', 'space x'],
    'shengkai': ['sheng kai', 'shengkai'],
}

for group, kws in keywords.items():
    matches = [(n, c) for n, c in sorted_entities if any(kw in n.lower() for kw in kws)]
    if matches:
        print(f'\n{group}: {len(matches)} 个变体')
        for name, count in matches[:10]:
            print(f'  [{count:5d}] {name}')
