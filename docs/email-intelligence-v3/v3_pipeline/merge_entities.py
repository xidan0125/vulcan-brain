#!/usr/bin/env python3
"""手动合并实体"""
import pymongo
client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client.vulcan_brain

def merge_entities(entity_type, canonical, aliases_to_merge):
    """合并实体到主实体"""
    main_doc = db.entities_v3.find_one({'type': entity_type, 'canonical_name': canonical})
    if not main_doc:
        print(f'⚠️ 找不到主实体: {canonical}')
        return

    total_mentions = main_doc['stats']['mention_count']
    all_aliases = set(main_doc.get('aliases', []))
    merged_count = 0

    for alias in aliases_to_merge:
        alias_doc = db.entities_v3.find_one({'type': entity_type, 'canonical_name': alias})
        if alias_doc and alias_doc['_id'] != main_doc['_id']:
            total_mentions += alias_doc['stats']['mention_count']
            all_aliases.add(alias)
            all_aliases.update(alias_doc.get('aliases', []))
            db.entities_v3.delete_one({'_id': alias_doc['_id']})
            merged_count += 1
            print(f'  合并: {alias} ({alias_doc["stats"]["mention_count"]})')

    all_aliases.discard(canonical)
    db.entities_v3.update_one(
        {'_id': main_doc['_id']},
        {'$set': {
            'aliases': list(all_aliases),
            'stats.mention_count': total_mentions,
            'stats.merged_from': merged_count
        }}
    )
    print(f'✅ 合并完成: {merged_count}个 -> {canonical} (总计{total_mentions}次)')


print('=== 合并 Vulcan 公司 ===')
merge_entities('COMPANY', 'Vulcan Shield Global Pte.', [
    'VSG', 'VULCAN SHIELD GLOBALPTE.', 'Vulcan Shield', 'Vulcan',
    'vulcanshield.com', 'vulcanshield', 'VULCAN SHELD GLOBAL',
    'VULCAN SHEILD', 'Vulcan Shield Global (VSG)', 'Vulcan Shield Group',
    'Vulcan Shiled', 'Vulcan Global Shield', 'VULCAN SHIELD GLOBAL PTE LTD-INV2025',
    'VULCAN SHIELD GLOBAL PTE LTD-INV2024', 'Vulcan Shield Global Pt',
    'Vulcan Shield Global Pty.', 'Vulcan Shield Global PL',
    'Vulcan Shielf Global Pte.', 'Vulcan Shield Singapor'
])

print()
print('=== 合并 Barry 人名 ===')
merge_entities('PERSON', 'Barry Claypool', [
    'Barry', 'Barry Vsg', 'Barry.Claypool', 'Barry C', 'Barry.C',
    'Barry Thomas', 'Claypool/Barry Thomas'
])

print()
print('=== 聚类后统计 ===')
for etype in ['COMPANY', 'PERSON', 'PRODUCT', 'LOCATION']:
    count = db.entities_v3.count_documents({'type': etype})
    print(f'{etype}: {count}')
