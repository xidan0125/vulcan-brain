#!/usr/bin/env python3
"""
V2实体迁移 V2版 - 正确的实体归一化

核心逻辑：
1. 先按normalized_key聚合所有变体（忽略type）
2. 用投票机制确定主type
3. 一个normalized_key = 一个entity_id
4. 所有变体都进aliases

验收标准：
- 搜"VSG"返回的entity_id = 搜"Vulcan Shield Global"的entity_id
- 搜"Barry"返回的entity_id = 搜"Barry Claypool"的entity_id
"""
import pymongo
import re
import hashlib
from collections import defaultdict
from datetime import datetime

client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client.vulcan_brain


def normalize_key(text: str) -> str:
    """生成归一化key"""
    if not text:
        return ""
    # 转小写
    text = text.lower().strip()
    # 全角转半角
    text = text.translate(str.maketrans(
        'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９',
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    ))
    # 移除标点和多余空格
    text = re.sub(r'[.,;:!?\-_()（）【】\[\]{}""\'\'\"\']+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # 移除公司后缀
    for suffix in ['pte ltd', 'pte', 'ltd', 'inc', 'corp', 'co', 'llc', 'gmbh']:
        text = re.sub(rf'\b{suffix}\b', '', text)
    text = re.sub(r'\s+', '_', text.strip())
    return text.upper() if text else ""


def main():
    print('=' * 60)
    print('🚀 V2实体迁移 V2版 - 正确的实体归一化')
    print('=' * 60)

    # Step 1: 聚合所有变体（忽略type）
    print('\n📊 Step 1: 聚合所有变体...')

    # {normalized_key: {text: {type: count}}}
    entity_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    total_records = 0
    for doc in db.v2_entities.find():
        for e in doc.get('entities', []):
            if isinstance(e, dict):
                text = e.get('text', '').strip()
                etype = e.get('type', 'unknown')

                # 跳过无效type
                if etype not in ['company', 'person', 'product', 'location']:
                    continue

                # 跳过太短的
                if len(text) < 2:
                    continue

                nkey = normalize_key(text)
                if nkey and len(nkey) >= 2:
                    entity_data[nkey][text][etype] += 1
                    total_records += 1

    print(f'   扫描完成: {total_records} 条记录 -> {len(entity_data)} 个normalized_key')

    # Step 2: 构建实体，投票确定type
    print('\n📊 Step 2: 构建实体（投票确定type）...')

    entities = []
    for nkey, variants in entity_data.items():
        # 统计这个key下所有type的总出现次数
        type_votes = defaultdict(int)
        total_mentions = 0
        all_texts = set()

        for text, type_counts in variants.items():
            all_texts.add(text)
            for etype, count in type_counts.items():
                type_votes[etype] += count
                total_mentions += count

        # 投票确定主type
        main_type = max(type_votes.keys(), key=lambda t: type_votes[t])

        # 选择最高频的text作为canonical_name
        text_counts = {text: sum(tc.values()) for text, tc in variants.items()}
        canonical = max(text_counts.keys(), key=lambda t: text_counts[t])

        # 过滤低频（<3次）
        if total_mentions < 3:
            continue

        entities.append({
            'normalized_key': nkey,
            'canonical_name': canonical,
            'type': main_type.upper(),
            'aliases': list(all_texts - {canonical}),
            'mention_count': total_mentions,
            'type_votes': dict(type_votes)
        })

    print(f'   构建完成: {len(entities)} 个实体（≥3次）')

    # Step 3: 写入数据库
    print('\n📊 Step 3: 写入entities_v3...')

    # 清空
    db.entities_v3.drop()

    docs = []
    for e in entities:
        entity_id = f"ent_{hashlib.md5(e['normalized_key'].encode()).hexdigest()[:16]}"
        doc = {
            'entity_id': entity_id,
            'type': e['type'],
            'canonical_name': e['canonical_name'],
            'normalized_key': e['normalized_key'],
            'aliases': e['aliases'][:50],  # 最多50个别名
            'stats': {
                'mention_count': e['mention_count'],
                'type_votes': e['type_votes'],
                'source': 'v2_migration_v2'
            },
            'created_at': datetime.utcnow()
        }
        docs.append(doc)

    if docs:
        db.entities_v3.insert_many(docs)

    # 创建索引
    db.entities_v3.create_index('entity_id', unique=True)
    db.entities_v3.create_index('type')
    db.entities_v3.create_index('normalized_key', unique=True)
    db.entities_v3.create_index('canonical_name')
    db.entities_v3.create_index('aliases')

    print(f'   写入完成: {len(docs)} 个实体')

    # Step 4: 统计
    print('\n' + '=' * 60)
    print('📈 迁移结果统计')
    print('=' * 60)

    for etype in ['COMPANY', 'PERSON', 'PRODUCT', 'LOCATION']:
        count = db.entities_v3.count_documents({'type': etype})
        print(f'   {etype}: {count}')

    total = db.entities_v3.count_documents({})
    print(f'   总计: {total}')

    # Step 5: 验收测试
    print('\n' + '=' * 60)
    print('✅ 验收测试')
    print('=' * 60)

    def find_entity(name):
        """查找实体"""
        # 精确匹配
        result = db.entities_v3.find_one({
            '$or': [
                {'canonical_name': name},
                {'aliases': name}
            ]
        })
        if result:
            return result

        # 忽略大小写
        nkey = normalize_key(name)
        return db.entities_v3.find_one({'normalized_key': nkey})

    test_cases = [
        # (搜索词1, 搜索词2, 期望是同一实体)
        ('VSG', 'Vulcan Shield Global Pte.', True),
        ('vulcanshield', 'Vulcan Shield', True),
        ('Barry', 'Barry Claypool', True),
        ('David', 'David Kneale', True),
        ('Microsoft', 'Microsoft Teams', True),
    ]

    all_pass = True
    for name1, name2, expect_same in test_cases:
        r1 = find_entity(name1)
        r2 = find_entity(name2)

        if not r1:
            print(f'   ❌ 找不到: {name1}')
            all_pass = False
            continue
        if not r2:
            print(f'   ❌ 找不到: {name2}')
            all_pass = False
            continue

        same = r1['entity_id'] == r2['entity_id']
        if same == expect_same:
            print(f'   ✅ "{name1}" 和 "{name2}" -> {r1["entity_id"][:20]}...')
        else:
            print(f'   ❌ "{name1}"({r1["entity_id"][:12]}) != "{name2}"({r2["entity_id"][:12]})')
            all_pass = False

    print('\n' + '=' * 60)
    if all_pass:
        print('🎉 验收通过！')
    else:
        print('⚠️ 验收未通过，需要检查')
    print('=' * 60)


if __name__ == '__main__':
    main()
