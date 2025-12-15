#!/usr/bin/env python3
"""
Step 2.0 - V2实体迁移：构建entities_v3种子库

从V2的50137条实体记录中：
1. 聚合所有实体，统计出现频率
2. 过滤低频实体（<3次）
3. 对高频实体做初步归一化聚类
4. 写入entities_v3作为种子数据
"""
import pymongo
from collections import Counter, defaultdict
from datetime import datetime
import re
import hashlib

client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client.vulcan_brain


def normalize_text(text: str) -> str:
    """基础文本标准化"""
    if not text:
        return ""
    # 转小写
    text = text.lower().strip()
    # 全角转半角
    text = text.translate(str.maketrans(
        'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９',
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    ))
    # 移除多余空格
    text = re.sub(r'\s+', ' ', text)
    # 移除标点
    text = re.sub(r'[.,;:!?\-_()（）【】\[\]{}""''\"\']+', '', text)
    return text.strip()


def generate_normalized_key(text: str, entity_type: str) -> str:
    """生成归一化key，用于聚类"""
    normalized = normalize_text(text)
    # 对于公司名，额外处理常见后缀
    if entity_type == 'company':
        for suffix in ['pte ltd', 'pte', 'ltd', 'inc', 'corp', 'co', 'llc', 'gmbh', 'sa', 'ag']:
            normalized = re.sub(rf'\b{suffix}\b', '', normalized)
    normalized = re.sub(r'\s+', '_', normalized.strip())
    return normalized.upper()


def cluster_entities(entities: dict, entity_type: str) -> list:
    """
    对实体进行聚类归一化
    输入: {text: count, ...}
    输出: [{canonical_name, aliases, total_count, normalized_key}, ...]
    """
    # 按normalized_key分组
    clusters = defaultdict(list)
    for text, count in entities.items():
        key = generate_normalized_key(text, entity_type)
        if key:  # 过滤空key
            clusters[key].append((text, count))

    # 构建聚类结果
    results = []
    for key, items in clusters.items():
        # 按出现频率排序，最高频的作为canonical_name
        items.sort(key=lambda x: -x[1])
        canonical = items[0][0]
        total_count = sum(count for _, count in items)
        aliases = [text for text, _ in items if text != canonical]

        results.append({
            'normalized_key': key,
            'canonical_name': canonical,
            'aliases': aliases[:20],  # 最多保留20个别名
            'total_count': total_count,
            'variant_count': len(items)
        })

    return results


def main():
    print('='*60)
    print('🚀 V2实体迁移 - 构建entities_v3种子库')
    print('='*60)

    # Step 1: 聚合所有实体
    print('\n📊 Step 1: 扫描V2实体...')
    entity_freq = defaultdict(Counter)

    for doc in db.v2_entities.find():
        for e in doc.get('entities', []):
            if isinstance(e, dict) and e.get('text'):
                etype = e.get('type', 'unknown')
                text = e.get('text', '').strip()
                if len(text) > 2 and etype in ['company', 'person', 'product', 'location']:
                    entity_freq[etype][text] += 1

    # Step 2: 过滤低频实体
    print('\n🔍 Step 2: 过滤低频实体 (保留≥3次)...')
    filtered = {}
    for etype, counter in entity_freq.items():
        filtered[etype] = {text: count for text, count in counter.items() if count >= 3}
        print(f'   {etype}: {len(counter)} -> {len(filtered[etype])}')

    # Step 3: 聚类归一化
    print('\n🔗 Step 3: 聚类归一化...')
    clustered = {}
    for etype, entities in filtered.items():
        clustered[etype] = cluster_entities(entities, etype)
        original = len(entities)
        after = len(clustered[etype])
        print(f'   {etype}: {original} 个变体 -> {after} 个聚类')

    # Step 4: 写入entities_v3
    print('\n💾 Step 4: 写入entities_v3...')

    # 清空现有数据
    db.entities_v3.delete_many({})

    total_inserted = 0
    for etype, clusters in clustered.items():
        docs = []
        for c in clusters:
            entity_id = f"ent_{etype}_{hashlib.md5(c['normalized_key'].encode()).hexdigest()[:12]}"
            doc = {
                'entity_id': entity_id,
                'type': etype.upper(),
                'canonical_name': c['canonical_name'],
                'normalized_key': c['normalized_key'],
                'aliases': c['aliases'],
                'stats': {
                    'mention_count': c['total_count'],
                    'variant_count': c['variant_count'],
                    'source': 'v2_migration'
                },
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            docs.append(doc)

        if docs:
            db.entities_v3.insert_many(docs)
            total_inserted += len(docs)
            print(f'   {etype}: {len(docs)} 条')

    # 创建索引
    print('\n📇 创建索引...')
    db.entities_v3.create_index('entity_id', unique=True)
    db.entities_v3.create_index('type')
    db.entities_v3.create_index('normalized_key')
    db.entities_v3.create_index('canonical_name')
    db.entities_v3.create_index([('aliases', 1)])

    print('\n' + '='*60)
    print(f'✅ 迁移完成! 共写入 {total_inserted} 个实体')
    print('='*60)

    # 展示一些样本
    print('\n📋 样本展示:')
    for etype in ['COMPANY', 'PERSON', 'PRODUCT']:
        print(f'\n{etype} Top 3:')
        for doc in db.entities_v3.find({'type': etype}).sort('stats.mention_count', -1).limit(3):
            print(f"  [{doc['stats']['mention_count']:4d}] {doc['canonical_name']}")
            if doc['aliases']:
                print(f"        别名: {doc['aliases'][:3]}")


if __name__ == '__main__':
    main()
