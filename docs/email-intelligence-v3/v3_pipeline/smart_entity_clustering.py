#!/usr/bin/env python3
"""
智能实体聚类 V2
使用vLLM服务对高频实体进行归一化聚类
"""
import pymongo
import requests
import json
from collections import defaultdict

client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client.vulcan_brain

# vLLM API (本地部署)
VLLM_URL = 'http://localhost:8000/v1/chat/completions'
MODEL = 'Qwen/Qwen3-VL-30B-A3B-Thinking-FP8'


def ask_llm(prompt: str) -> str:
    """调用vLLM服务"""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2048,
        "temperature": 0.1
    }
    resp = requests.post(VLLM_URL, json=payload, timeout=180)
    resp.raise_for_status()
    result = resp.json()
    content = result["choices"][0]["message"]["content"]

    # 处理thinking模式的输出
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()

    return content


def cluster_company_variants(variants: list) -> dict:
    """让AI聚类公司名变体"""
    variants_json = json.dumps(variants, ensure_ascii=False, indent=2)
    prompt = f'''你是一个B2B企业数据专家。以下是从邮件中提取的公司名列表，它们可能是同一家公司的不同写法。

请分析并将它们归类。返回JSON格式：
{{
  "clusters": [
    {{
      "canonical_name": "最标准的公司全名",
      "aliases": ["别名1", "别名2"]
    }}
  ]
}}

公司名列表:
{variants_json}

只返回JSON，不要解释。'''

    response = ask_llm(prompt)

    # 解析JSON
    try:
        if '```json' in response:
            response = response.split('```json')[1].split('```')[0]
        elif '```' in response:
            response = response.split('```')[1].split('```')[0]
        return json.loads(response.strip())
    except:
        return {'clusters': [], 'raw': response[:500]}


def cluster_person_variants(variants: list) -> dict:
    """让AI聚类人名变体"""
    variants_json = json.dumps(variants, ensure_ascii=False, indent=2)
    prompt = f'''你是一个B2B企业数据专家。以下是从邮件中提取的人名列表，它们可能是同一个人的不同写法。

请分析并将它们归类。注意：
- "Barry" 和 "Barry Claypool" 如果经常一起出现，很可能是同一个人
- "Barry Vsg" 可能是 Barry from VSG公司
- 邮箱格式如 "Barry.Claypool" 也是人名

返回JSON格式：
{{
  "clusters": [
    {{
      "canonical_name": "最完整的人名",
      "aliases": ["别名1", "别名2"]
    }}
  ]
}}

人名列表:
{variants_json}

只返回JSON，不要解释。'''

    response = ask_llm(prompt)

    try:
        if '```json' in response:
            response = response.split('```json')[1].split('```')[0]
        elif '```' in response:
            response = response.split('```')[1].split('```')[0]
        return json.loads(response.strip())
    except:
        return {'clusters': [], 'raw': response[:500]}


def apply_clustering(clusters: list, entity_type: str):
    """将聚类结果应用到数据库"""
    for cluster in clusters:
        canonical = cluster.get('canonical_name')
        aliases = cluster.get('aliases', [])

        if not canonical or not aliases:
            continue

        # 找到canonical对应的文档
        main_doc = db.entities_v3.find_one({
            'type': entity_type,
            'canonical_name': canonical
        })

        if not main_doc:
            # 尝试在aliases中找
            main_doc = db.entities_v3.find_one({
                'type': entity_type,
                'canonical_name': {'$in': aliases}
            })

        if not main_doc:
            print(f"      ⚠️ 找不到主实体: {canonical}")
            continue

        # 收集所有要合并的实体
        total_mentions = main_doc['stats']['mention_count']
        all_aliases = set(main_doc.get('aliases', []))
        entities_to_remove = []

        for alias in aliases:
            if alias == canonical:
                continue
            alias_doc = db.entities_v3.find_one({
                'type': entity_type,
                'canonical_name': alias
            })
            if alias_doc:
                total_mentions += alias_doc['stats']['mention_count']
                all_aliases.add(alias)
                all_aliases.update(alias_doc.get('aliases', []))
                entities_to_remove.append(alias_doc['_id'])

        # 更新主实体
        all_aliases.discard(canonical)
        db.entities_v3.update_one(
            {'_id': main_doc['_id']},
            {'$set': {
                'aliases': list(all_aliases),
                'stats.mention_count': total_mentions,
                'stats.merged_from': len(entities_to_remove)
            }}
        )

        # 删除被合并的实体
        if entities_to_remove:
            db.entities_v3.delete_many({'_id': {'$in': entities_to_remove}})
            print(f"      ✅ 合并 {len(entities_to_remove)} 个实体到 {canonical}")


def main():
    print('='*60)
    print('🧠 智能实体聚类 (vLLM)')
    print('='*60)

    # 1. 处理公司 - Vulcan/VSG 相关
    print('\n📊 Step 1: 聚类 Vulcan/VSG 相关公司...')
    vulcan_variants = []
    for doc in db.entities_v3.find({'type': 'COMPANY'}):
        name = doc['canonical_name'].lower()
        if 'vulcan' in name or 'vsg' in name:
            vulcan_variants.append({
                'name': doc['canonical_name'],
                'count': doc['stats']['mention_count']
            })

    vulcan_variants.sort(key=lambda x: -x['count'])
    # 只取前20个高频变体，避免prompt过长
    top_variants = vulcan_variants[:20]
    print(f'   找到 {len(vulcan_variants)} 个变体，取前 {len(top_variants)} 个:')
    for v in top_variants[:10]:
        print(f"      [{v['count']:5d}] {v['name']}")

    if top_variants:
        print('\n   调用vLLM聚类...')
        result = cluster_company_variants([v['name'] for v in top_variants])
        print('   AI聚类结果:')
        for cluster in result.get('clusters', []):
            print(f"      标准名: {cluster.get('canonical_name')}")
            print(f"      别名: {cluster.get('aliases', [])[:5]}")

        # 应用聚类
        print('\n   应用聚类结果...')
        apply_clustering(result.get('clusters', []), 'COMPANY')

    # 2. 处理人名 - Barry 相关
    print('\n📊 Step 2: 聚类 Barry 相关人名...')
    barry_variants = []
    for doc in db.entities_v3.find({'type': 'PERSON'}):
        name = doc['canonical_name'].lower()
        if 'barry' in name:
            barry_variants.append({
                'name': doc['canonical_name'],
                'count': doc['stats']['mention_count']
            })

    barry_variants.sort(key=lambda x: -x['count'])
    # 只取高频的前15个
    high_freq = [v for v in barry_variants if v['count'] >= 3][:15]
    print(f'   找到 {len(high_freq)} 个高频变体:')
    for v in high_freq[:10]:
        print(f"      [{v['count']:5d}] {v['name']}")

    if high_freq:
        print('\n   调用vLLM聚类...')
        result = cluster_person_variants([v['name'] for v in high_freq])
        print('   AI聚类结果:')
        for cluster in result.get('clusters', []):
            print(f"      标准名: {cluster.get('canonical_name')}")
            print(f"      别名: {cluster.get('aliases', [])[:5]}")

        # 应用聚类
        print('\n   应用聚类结果...')
        apply_clustering(result.get('clusters', []), 'PERSON')

    # 3. 统计结果
    print('\n' + '='*60)
    print('📈 聚类后统计')
    print('='*60)

    for etype in ['COMPANY', 'PERSON', 'PRODUCT', 'LOCATION']:
        count = db.entities_v3.count_documents({'type': etype})
        print(f'   {etype}: {count}')


if __name__ == '__main__':
    main()
