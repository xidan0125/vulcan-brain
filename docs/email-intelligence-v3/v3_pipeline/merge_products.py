#!/usr/bin/env python3
"""合并产品实体"""
import pymongo
client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client.vulcan_brain

def merge_entities(entity_type, canonical, aliases_to_merge):
    """合并实体到主实体"""
    main_doc = db.entities_v3.find_one({'type': entity_type, 'canonical_name': canonical})
    if not main_doc:
        print(f'  ⚠️ 找不到主实体: {canonical}')
        return 0

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

    all_aliases.discard(canonical)
    db.entities_v3.update_one(
        {'_id': main_doc['_id']},
        {'$set': {
            'aliases': list(all_aliases),
            'stats.mention_count': total_mentions,
            'stats.merged_from': main_doc['stats'].get('merged_from', 0) + merged_count
        }}
    )
    if merged_count > 0:
        print(f'  ✅ {canonical}: 合并{merged_count}个 -> {total_mentions}次')
    return merged_count


print('='*60)
print('📦 合并产品实体')
print('='*60)

# Vulcan Shield 产品线
merge_entities('PRODUCT', 'Vulcan Shield', ['Vulcan Shield Global'])

# Microsoft 365
merge_entities('PRODUCT', 'Microsoft 365', ['Office 365', 'Microsoft Teams'])

# Alumina Fiber
merge_entities('PRODUCT', 'Alumina Fiber', [
    'Alumina Oxide Fiber', 'Alumina Fiber Products', 'alumina fiber'
])

# blanket
merge_entities('PRODUCT', 'blanket', ['blankets', 'Needled Blanket'])

# WP Mail SMTP
merge_entities('PRODUCT', 'WP Mail SMTP', ['WP Mail SMTP Pro'])

# bulk fiber
merge_entities('PRODUCT', 'bulk fiber', ['Bulk Fiber', 'BULK FIBER'])

print()
print('=== 合并后 Top 15 产品 ===')
for doc in db.entities_v3.find({'type': 'PRODUCT'}).sort('stats.mention_count', -1).limit(15):
    aliases = doc.get('aliases', [])
    print(f"[{doc['stats']['mention_count']:5d}] {doc['canonical_name']} ({len(aliases)} aliases)")
